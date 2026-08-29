#!/usr/bin/env python3
"""把 frontend/public 底下的靜態資產同步到 Cloudflare R2。

  python3 scripts/publish_assets.py --dry-run     # 先看會傳什麼，不動遠端
  python3 scripts/publish_assets.py               # 實際同步
  python3 scripts/publish_assets.py --only images

為什麼用 rclone 而不是 wrangler：`wrangler r2 object put` 一次只傳一個物件，
這裡有 1,950 個檔；rclone sync 有平行、續傳、checksum 比對，而且**99% 的路徑含中文**
（`pdf-assets/` 全部、`images/` 710/727），rclone 的 S3 key 編碼在這方面是驗證過的。

需要的憑證（放 .env 或 shell 環境）——都在 Cloudflare Dashboard → R2 → Manage R2 API Tokens 取得：

  R2_ACCOUNT_ID          Cloudflare 帳號 ID
  R2_ACCESS_KEY_ID       R2 API token 的 Access Key ID
  R2_SECRET_ACCESS_KEY   R2 API token 的 Secret Access Key
  R2_BUCKET              bucket 名稱（預設 ipas-assets）

**這支腳本只上傳，不刪遠端。** 用 `sync` 而不是 `copy` 會刪掉遠端多出來的物件——
對一個「資料 JSON 裡有 2000 筆 URL 指著它」的 bucket，那是不可逆的踩雷方式。
真的要清理遠端孤兒，明確加 `--prune` 並自己看清楚 dry-run 的輸出。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from asset_paths import BASE, asset_root

# 要發佈的目錄，key 是遠端的 prefix（與資料 JSON 裡的根相對路徑一致）
ASSET_DIRS = {
    'pdf-assets': 'pdf-assets',
    'images': 'images',
}

REQUIRED_ENV = ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY')


def load_dotenv() -> None:
    """讀專案根的 .env（gitignored），不覆蓋已存在的環境變數。"""
    path = BASE / '.env'
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def rclone_flags() -> list[str]:
    """把 R2 憑證直接當 rclone 的 inline remote 參數，不寫 rclone.conf。

    憑證留在環境變數裡，不會多出一份躺在磁碟上的設定檔。
    """
    account = os.environ['R2_ACCOUNT_ID']
    return [
        '--s3-provider', 'Cloudflare',
        '--s3-access-key-id', os.environ['R2_ACCESS_KEY_ID'],
        '--s3-secret-access-key', os.environ['R2_SECRET_ACCESS_KEY'],
        '--s3-endpoint', f'https://{account}.r2.cloudflarestorage.com',
        '--s3-region', 'auto',
        # R2 不支援 S3 的 multipart ETag 語意，用大小+修改時間比對即可
        '--s3-no-check-bucket',
        '--checksum=false',
        '--size-only',
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true', help='只顯示會做什麼，不動遠端')
    parser.add_argument('--only', choices=sorted(ASSET_DIRS), help='只發佈其中一個目錄')
    parser.add_argument('--bucket', default=os.environ.get('R2_BUCKET', 'ipas-assets'))
    parser.add_argument('--transfers', type=int, default=16, help='平行上傳數（預設 16）')
    parser.add_argument('--prune', action='store_true',
                        help='危險：連同刪除遠端多餘物件（預設只上傳不刪）')
    args = parser.parse_args()

    load_dotenv()

    if shutil.which('rclone') is None:
        print('ERROR: 找不到 rclone。安裝：curl https://rclone.org/install.sh | sudo bash',
              file=sys.stderr)
        return 1

    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f'ERROR: 缺少環境變數 {", ".join(missing)}\n'
              f'到 Cloudflare Dashboard → R2 → Manage R2 API Tokens 建立，'
              f'再寫進專案根的 .env。', file=sys.stderr)
        return 1

    root = asset_root()
    if root is None:
        print('ERROR: IPAS_ASSET_ROOT 設成空值，代表資產不在本機，沒有東西可以發佈。',
              file=sys.stderr)
        return 1

    targets = {args.only: ASSET_DIRS[args.only]} if args.only else ASSET_DIRS
    verb = 'sync' if args.prune else 'copy'
    failed = 0

    for local_name, remote_prefix in targets.items():
        src = root / local_name
        if not src.exists():
            print(f'SKIP {local_name}：{src} 不存在')
            continue
        count = sum(1 for _ in src.rglob('*') if _.is_file())
        dest = f':s3:{args.bucket}/{remote_prefix}'
        print(f'\n=== {verb} {local_name} → {dest}（{count} 檔）===')

        cmd = ['rclone', verb, str(src), dest,
               *rclone_flags(),
               '--transfers', str(args.transfers),
               '--progress', '--stats-one-line', '--stats', '5s']
        if args.dry_run:
            cmd.append('--dry-run')

        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f'ERROR: {local_name} 發佈失敗（rclone exit {result.returncode}）',
                  file=sys.stderr)
            failed += 1

    if failed:
        return 1
    if args.dry_run:
        print('\n（dry-run，遠端未變動）')
    else:
        print('\n完成。下一步跑 scripts/verify_r2_assets.py 做全量 HEAD 檢查——'
              '99% 的路徑含中文，抽樣驗不出編碼問題。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
