"""測試用的 Vite dev server 啟停。

專案沒有既有的測試框架，所以這些測試是「直接跑的腳本」而不是 pytest：

    python3 tests/test_exam_flow.py
    python3 tests/test_routes.py

需要 playwright（`pip install playwright && playwright install chromium`）。
若已經有 dev server 在跑，設 `IPAS_TEST_BASE=http://127.0.0.1:5173` 就會直接用它、不另外啟動。
"""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND = BASE_DIR / 'frontend'
DEFAULT_PORT = 5199


def _port_open(port: int, host: str = '127.0.0.1') -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def _kill_group(proc: subprocess.Popen) -> None:
    """整個 process group 一起收，不然 npm 底下的 vite 會變孤兒。"""
    if proc.poll() is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, PermissionError):
        proc.terminate()
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=8)
            return
        except subprocess.TimeoutExpired:
            continue


@contextlib.contextmanager
def dev_server(port: int = DEFAULT_PORT, timeout: float = 90.0):
    """yield base URL。外部已有 server（或 IPAS_TEST_BASE 指定）就直接用，不重啟。"""
    external = os.environ.get('IPAS_TEST_BASE')
    if external:
        print(f'[devserver] 使用外部 server {external}')
        yield external.rstrip('/')
        return

    if _port_open(port):
        # 沿用既有 server 有一個真實的陷阱：那支可能跑的是**舊的程式碼**
        # （上一輪測試留下的孤兒、或你自己開著的 dev server）。
        # Vite 有 HMR 所以多半會是新的，但孤兒 server 的工作目錄／環境變數不一定對。
        print(f'[devserver] ⚠️  port {port} 已經有 server，直接使用它（不會關它）。\n'
              f'[devserver]     若測試結果不符預期，先確認那支是不是舊的：'
              f'ss -ltnp | grep {port}')
        yield f'http://127.0.0.1:{port}'
        return

    print(f'[devserver] 啟動 vite dev（port {port}）…')
    # start_new_session：npm 會再 spawn 一支 vite 子行程，只 terminate npm
    # 會留下孤兒 server 佔著 port。開新 process group 才能整組收掉。
    proc = subprocess.Popen(
        ['npm', 'run', 'dev', '--', '--host', '--port', str(port)],
        cwd=FRONTEND, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f'dev server 啟動失敗（exit {proc.returncode}），'
                                   f'先確認 frontend/ 有跑過 npm install')
            if _port_open(port):
                time.sleep(1.5)  # 讓第一次 transform 完成
                break
            time.sleep(0.5)
        else:
            raise TimeoutError(f'dev server {timeout}s 內沒有起來')
        print(f'[devserver] ready → http://127.0.0.1:{port}')
        yield f'http://127.0.0.1:{port}'
    finally:
        _kill_group(proc)
        for _ in range(20):
            if not _port_open(port):
                break
            time.sleep(0.5)
        print('[devserver] 已停止' if not _port_open(port)
              else f'[devserver] 警告：port {port} 仍被佔用')


def require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print('需要 playwright：pip install playwright && playwright install chromium',
              file=sys.stderr)
        sys.exit(2)
