#!/usr/bin/env python3
"""Execute the MVP learning lab in clean kernels and verify L0-L3 evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import shutil
import signal
import tempfile
import time
from pathlib import Path
from typing import Any

import nbformat
import numpy as np
import pandas as pd
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError, CellTimeoutError
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
LAB_ID = "lab-imbalanced-classification"
SOURCE = ROOT / "notebooks" / "labs" / f"{LAB_ID}.ipynb"
FIXTURE_DIR = ROOT / "notebooks" / "labs" / LAB_ID / "fixtures"
CANDIDATE_DIR = ROOT / "data" / "learning" / "pipeline" / "mvp-authoring" / "labs" / LAB_ID
REPORT = CANDIDATE_DIR / "execution-report.json"


class TotalTimeout(RuntimeError):
    pass


def blob_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_notebook(source: Path | Any, workdir: Path, *, phases: set[str] | None = None) -> tuple[Any, float]:
    notebook = nbformat.read(source, as_version=4) if isinstance(source, Path) else nbformat.from_dict(json.loads(json.dumps(source)))
    nbformat.validate(notebook)
    if phases is not None:
        notebook.cells = [cell for cell in notebook.cells if cell.metadata["learning"]["phase"] in phases]
    started = time.monotonic()

    def timeout_handler(_signum, _frame):
        raise TotalTimeout("notebook exceeded 300 seconds")

    previous = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(300)
    try:
        client = NotebookClient(
            notebook,
            timeout=60,
            kernel_name="python3",
            allow_errors=False,
            resources={"metadata": {"path": str(workdir)}},
        )
        executed = client.execute()
    except (CellExecutionError, CellTimeoutError) as exc:
        raise RuntimeError(f"notebook execution failed: {exc}") from exc
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
    return executed, time.monotonic() - started


def derive_variant(variant: str) -> Any:
    """Derive a variant in memory so verification works in a fresh checkout."""
    if variant not in {"starter", "solution"}:
        raise ValueError(f"unknown lab variant: {variant}")
    notebook = nbformat.read(SOURCE, as_version=4)
    kept = []
    for cell in notebook.cells:
        learning = cell.metadata["learning"]
        if variant == "starter" and learning["audience"] == "solution":
            continue
        if variant == "starter" and "starterSource" in learning:
            cell.source = learning.pop("starterSource")
        else:
            learning.pop("starterSource", None)
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
        kept.append(cell)
    notebook.cells = kept
    nbformat.validate(notebook)
    return notebook


def prepare_workspace(path: Path, *, root_upload: bool) -> None:
    destination = path if root_upload else path / "fixtures"
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("equipment_alerts_v1.csv", "split_manifest_v1.json"):
        shutil.copy2(FIXTURE_DIR / name, destination / name)


def _metric_row(y_true, predictions, threshold: float | None, fn_cost: int, fp_cost: int) -> dict[str, Any]:
    tn, fp, fn, tp = (int(value) for value in confusion_matrix(y_true, predictions, labels=[0, 1]).ravel())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    row: dict[str, Any] = {
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
        "accuracy": (tn + tp) / len(y_true),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "average_cost": (fn_cost * fn + fp_cost * fp) / len(y_true),
    }
    if threshold is not None:
        row["threshold"] = float(threshold)
    return row


def _assert_metric_row(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    assert set(actual) == set(expected), f"metric fields differ: {set(actual) ^ set(expected)}"
    for key, value in expected.items():
        if isinstance(value, float):
            assert math.isfinite(actual[key])
            assert abs(actual[key] - value) <= 1e-12, f"{key} differs"
        else:
            assert actual[key] == value, f"{key} differs"


def independently_check_metrics(metrics: dict[str, Any], split: dict[str, Any], data_path: Path) -> None:
    """Rebuild every result from the immutable fixture, independent of notebook claims."""
    sets = {name: set(ids) for name, ids in split["splits"].items()}
    assert set(metrics["fitRowIds"]) == sets["train"]
    assert len(metrics["fitRowIds"]) == len(sets["train"])
    assert set(metrics["dummyFitRowIds"]) == sets["train"]
    assert set(metrics["thresholdSelectionRowIds"]) == sets["validation"]
    assert not (set(metrics["thresholdSelectionRowIds"]) & sets["test"])

    data = pd.read_csv(data_path)
    assert data["row_id"].is_unique and set(data["row_id"]) == set().union(*sets.values())
    parts = {
        name: data[data["row_id"].isin(row_ids)].sort_values("row_id").reset_index(drop=True)
        for name, row_ids in sets.items()
    }
    feature_cols = [f"feature_{index}" for index in range(1, 9)]
    preprocessor = ColumnTransformer([
        ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), feature_cols)
    ])
    model = Pipeline([
        ("preprocess", preprocessor),
        ("classifier", LogisticRegression(max_iter=500, random_state=42)),
    ])
    dummy = DummyClassifier(strategy="most_frequent")
    train, validation, expected_test = parts["train"], parts["validation"], parts["test"]
    model.fit(train[feature_cols], train["is_anomaly"])
    dummy.fit(train[feature_cols], train["is_anomaly"])

    thresholds = np.round(np.arange(0.05, 1.0, 0.05), 2)
    validation_scores = model.predict_proba(validation[feature_cols])[:, 1]

    def expected_table(fn_cost: int) -> list[dict[str, Any]]:
        return [
            _metric_row(
                validation["is_anomaly"],
                (validation_scores >= threshold).astype(int),
                float(threshold), fn_cost, 1,
            )
            for threshold in thresholds
        ]

    primary_table = expected_table(20)
    assert len(metrics["validationTable"]) == len(primary_table) == 19
    for actual, expected in zip(metrics["validationTable"], primary_table, strict=True):
        _assert_metric_row(actual, expected)
    selected = min(primary_table, key=lambda row: (row["average_cost"], -row["recall"], row["threshold"]))
    assert metrics["threshold"] == selected["threshold"]

    sensitivity = metrics["sensitivityFn5"]
    assert set(sensitivity["thresholdSelectionRowIds"]) == sets["validation"]
    sensitivity_table = expected_table(5)
    assert len(sensitivity["validationTable"]) == len(sensitivity_table) == 19
    for actual, expected in zip(sensitivity["validationTable"], sensitivity_table, strict=True):
        _assert_metric_row(actual, expected)
    expected_sensitivity = min(sensitivity_table, key=lambda row: (row["average_cost"], -row["recall"], row["threshold"]))
    assert sensitivity["threshold"] == expected_sensitivity["threshold"]

    test = metrics["test"]
    expected_ids = expected_test["row_id"].tolist()
    expected_y = expected_test["is_anomaly"].astype(int).tolist()
    assert test["rowIds"] == expected_ids and len(test["rowIds"]) == 400
    assert test["yTrue"] == expected_y and len(test["yTrue"]) == 400
    test_scores = model.predict_proba(expected_test[feature_cols])[:, 1]
    expected_predictions = (test_scores >= metrics["threshold"]).astype(int).tolist()
    assert test["yPred"] == expected_predictions and len(test["yPred"]) == 400
    expected_logistic = _metric_row(expected_y, expected_predictions, metrics["threshold"], 20, 1)
    actual_logistic = {key: test[key] for key in expected_logistic}
    _assert_metric_row(actual_logistic, expected_logistic)
    expected_dummy_predictions = dummy.predict(expected_test[feature_cols]).astype(int).tolist()
    assert test["dummy"]["yPred"] == expected_dummy_predictions
    expected_dummy = _metric_row(expected_y, expected_dummy_predictions, None, 20, 1)
    actual_dummy = {key: test["dummy"][key] for key in expected_dummy}
    _assert_metric_row(actual_dummy, expected_dummy)


def verify_structure() -> dict[str, Any]:
    source = nbformat.read(SOURCE, as_version=4)
    nbformat.validate(source)
    ids = []
    phases = {"setup", "worked", "guided", "independent", "check", "reflection"}
    starter_cells = 0
    for cell in source.cells:
        meta = cell.metadata.get("learning", {})
        assert meta.get("labId") == LAB_ID and meta.get("revision") == 1
        assert meta.get("cellId") == cell.id and meta.get("phase") in phases
        assert meta.get("audience") in {"both", "solution"}
        ids.append(cell.id)
        if "starterSource" in meta:
            starter_cells += 1
    assert len(ids) == len(set(ids)) and starter_cells == 1
    by_id = {cell.id: cell for cell in source.cells}
    assert "test_scores" not in by_id["fit-train-only"].source
    assert "frozen_threshold" in by_id["threshold-and-artifacts"].source
    starter_source = by_id["threshold-and-artifacts"].metadata["learning"]["starterSource"]
    assert 'Path("metrics.json").write_text' in starter_source
    assert "assert_result(result)" in by_id["invariant-and-fault-checks"].source
    assert "starterSource" not in by_id["invariant-and-fault-checks"].metadata["learning"]
    return {"cells": len(ids), "starterReplacementCells": starter_cells}


def verify(*, write_report: bool) -> dict[str, Any]:
    structure = verify_structure()
    split_path = FIXTURE_DIR / "split_manifest_v1.json"
    data_path = FIXTURE_DIR / "equipment_alerts_v1.csv"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    assert split["rowCount"] == 2000 and split["positiveCount"] == 100
    assert {name: len(ids) for name, ids in split["splits"].items()} == {"train": 1200, "validation": 400, "test": 400}

    with tempfile.TemporaryDirectory(prefix="ipas-lab-solution-") as raw:
        workspace = Path(raw)
        prepare_workspace(workspace, root_upload=False)
        executed, solution_seconds = run_notebook(derive_variant("solution"), workspace)
        metrics = json.loads((workspace / "metrics.json").read_text(encoding="utf-8"))
        independently_check_metrics(metrics, split, data_path)
        output_text = "\n".join(
            str(output.get("text", ""))
            for cell in executed.cells for output in cell.get("outputs", [])
            if output.get("output_type") == "stream"
        )
        assert "3 個 fault injections 全部通過" in output_text
        assert (workspace / "decision.md").is_file()

    with tempfile.TemporaryDirectory(prefix="ipas-lab-starter-") as raw:
        workspace = Path(raw)
        prepare_workspace(workspace, root_upload=True)
        _, starter_seconds = run_notebook(derive_variant("starter"), workspace, phases={"setup", "worked"})

    with tempfile.TemporaryDirectory(prefix="ipas-lab-starter-blocked-") as raw:
        workspace = Path(raw)
        prepare_workspace(workspace, root_upload=True)
        try:
            run_notebook(derive_variant("starter"), workspace)
        except RuntimeError as exc:
            assert "NotImplementedError" in str(exc) and "待完成 evaluate_scores" in str(exc)
        else:
            raise AssertionError("unfinished starter must stop at the TODO implementation")

    with tempfile.TemporaryDirectory(prefix="ipas-lab-upload-") as raw:
        workspace = Path(raw)
        prepare_workspace(workspace, root_upload=True)
        _, upload_seconds = run_notebook(derive_variant("solution"), workspace)

    report = {
        "schemaVersion": 1,
        "labId": LAB_ID,
        "revision": 1,
        "authorId": "/root/p0_baseline",
        "automatedScope": "L0-L3 implementation evidence; not an independent publication review",
        "environment": {
            "kernel": "python3", "python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scikit-learn", "matplotlib", "nbformat", "nbclient", "ipykernel")},
            "network": "not used by notebook", "maxCellSeconds": 60, "maxTotalSeconds": 300,
        },
        "inputs": {"sourceNotebook": blob_hash(SOURCE), "fixture": blob_hash(data_path), "splitManifest": blob_hash(split_path)},
        "structure": structure,
        "runs": {"solutionCleanKernelSeconds": round(solution_seconds, 3), "starterSetupWorkedSeconds": round(starter_seconds, 3), "manualUploadSimulationSeconds": round(upload_seconds, 3)},
        "checks": {"L0":"pass","L1":"pass","L2":"pass","L3":"pass","starterIncomplete":"blocked_at_TODO","faultInjections":{"allDataFit":"rejected","testAsValidation":"rejected","precisionRecallSwap":"rejected"}},
        "publicationGate": {"status":"blocked","L4":"not_run","L5":"not_run","missing":["independent semantic review","human Colab smoke","immutable Git commit URL"]}
    }
    if write_report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab", default=LAB_ID, choices=[LAB_ID])
    parser.add_argument("--profile", default="cpu", choices=["cpu"])
    parser.add_argument("--check", action="store_true", help="Validate without writing execution evidence")
    args = parser.parse_args()
    print(json.dumps(verify(write_report=not args.check), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
