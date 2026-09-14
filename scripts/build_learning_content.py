"""Build an immutable learning release or a clearly separate local preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from learning.publication import build_learning_content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--preview", action="store_true", help="Local candidate only; never updates production current.json")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="Validate and prepare bytes without writing")
    modes.add_argument("--dry-run", action="store_true", help="Report candidate and review gaps without writing")
    parser.add_argument("--assessment-at", help="Explicit UTC timestamp for source freshness checks")
    parser.add_argument("--lab-assets-manifest", help="Repository-relative staged Lab asset manifest")
    parser.add_argument("--without-assessment", action="store_true", help="Validate only content sources, without the reviewed MVP assessment adapter")
    args = parser.parse_args()
    additional = {}
    if not args.without_assessment and (args.repo_root / "content/learning/evidence/assessment/reviewed-diagnostic-source.json").exists():
        from build_learning_assessment import assessment_inputs
        try:
            prepared = assessment_inputs(args.repo_root)
        except (ValueError, OSError, KeyError) as exc:
            print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False, indent=2))
            return 1
        additional = {key: prepared[key] for key in ("additional_documents", "additional_artifacts", "additional_inputs")}
        # The default derives from committed sources, independent of staging presence.
        args.lab_assets_manifest = args.lab_assets_manifest or ""
    report = build_learning_content(args.repo_root, preview=args.preview, check=args.check,
                                    dry_run=args.dry_run, assessment_at=args.assessment_at,
                                    lab_assets_manifest=args.lab_assets_manifest, **additional)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
