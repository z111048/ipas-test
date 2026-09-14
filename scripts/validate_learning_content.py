"""Validate authored learning contracts/references; report outstanding reviews."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from learning.publication import load_candidate, validate_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--all", action="store_true", help="Validate the complete candidate (the only supported scope)")
    parser.add_argument("--check", action="store_true", help="Read-only validation; this command never writes")
    parser.add_argument("--assessment-at", help="Explicit UTC timestamp for source freshness checks")
    args = parser.parse_args()
    additional = None
    if (args.repo_root / "content/learning/evidence/assessment/reviewed-diagnostic-source.json").exists():
        from build_learning_assessment import assessment_inputs
        try:
            additional = assessment_inputs(args.repo_root)["additional_documents"]
        except (ValueError, OSError, KeyError) as exc:
            print(json.dumps({"status": "blocked", "reason": str(exc), "publicationApproved": False}, ensure_ascii=False, indent=2))
            return 1
    candidate = load_candidate(args.repo_root, assessment_at=args.assessment_at, additional_documents=additional)
    issues, reviews = validate_candidate(candidate, preview=True)
    print(json.dumps({"status": "blocked" if issues else "validated", "entities": len(candidate.documents),
                      "issues": [asdict(issue) for issue in issues],
                      "unmetReviews": [asdict(issue) for issue in reviews], "publicationApproved": False},
                     ensure_ascii=False, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
