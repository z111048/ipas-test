#!/usr/bin/env python3
"""Build the deterministic MVP lab source, fixture, and review candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

import nbformat


ROOT = Path(__file__).resolve().parents[1]
LAB_ID = "lab-imbalanced-classification"
REVISION = 1
LAB_ROOT = ROOT / "notebooks" / "labs"
SOURCE_PATH = LAB_ROOT / f"{LAB_ID}.ipynb"
FIXTURE_DIR = LAB_ROOT / LAB_ID / "fixtures"
DATA_PATH = FIXTURE_DIR / "equipment_alerts_v1.csv"
SPLIT_PATH = FIXTURE_DIR / "split_manifest_v1.json"
LOCK_PATH = LAB_ROOT / LAB_ID / "requirements.lock"
CANDIDATE_DIR = ROOT / "data" / "learning" / "pipeline" / "mvp-authoring" / "labs" / LAB_ID

OBJECTIVES = {
    "split": "unit-split-before-fit::audit-fit-rows",
    "metrics": "unit-imbalanced-classification::compute-metrics",
    "threshold": "unit-threshold-decision::select-threshold",
}


def sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_if_changed(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    path.write_bytes(data)


def build_fixture() -> tuple[str, str]:
    """Create 2,000 stable rows, exactly 8 numeric features and 5% positives."""
    rng = random.Random(42)
    labels = [0] * 1900 + [1] * 100
    rng.shuffle(labels)
    rows: list[list[str]] = []
    for index, label in enumerate(labels):
        latent = 1.25 * label + rng.gauss(0, 1)
        values = [
            latent + rng.gauss(0, 0.75),
            0.7 * latent + rng.gauss(0, 1.0),
            -0.5 * latent + rng.gauss(0, 1.1),
            rng.gauss(0.3 * label, 1.0),
            rng.gauss(-0.2 * label, 1.0),
            rng.gauss(0, 1),
            rng.gauss(0, 1),
            rng.gauss(0, 1),
        ]
        rows.append([f"row-{index:04d}", *(f"{value:.8f}" for value in values), str(label)])

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["row_id", *(f"feature_{i}" for i in range(1, 9)), "is_anomaly"])
        writer.writerows(rows)

    by_label = {0: [], 1: []}
    for row, label in zip(rows, labels, strict=True):
        by_label[label].append(row[0])
    split_rng = random.Random(42)
    for ids in by_label.values():
        split_rng.shuffle(ids)
    splits = {
        "train": by_label[0][:1140] + by_label[1][:60],
        "validation": by_label[0][1140:1520] + by_label[1][60:80],
        "test": by_label[0][1520:] + by_label[1][80:],
    }
    for ids in splits.values():
        ids.sort()
    manifest = {
        "schemaVersion": 1,
        "datasetVersion": "1.0.0",
        "seed": 42,
        "strategy": "stratified-fixed-60-20-20",
        "rowCount": 2000,
        "positiveCount": 100,
        "splits": splits,
    }
    write_if_changed(SPLIT_PATH, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    return sha256_bytes(DATA_PATH.read_bytes()), sha256_bytes(SPLIT_PATH.read_bytes())


def learning_meta(cell_id: str, phase: str, objectives: list[str], *, audience: str = "both", starter: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "labId": LAB_ID,
        "revision": REVISION,
        "cellId": cell_id,
        "phase": phase,
        "objectiveIds": objectives,
        "audience": audience,
    }
    if starter is not None:
        value["starterSource"] = starter
    return {"learning": value}


def build_notebook(data_hash: str, split_hash: str) -> None:
    setup_source = f'''from pathlib import Path
import copy
import hashlib
import json
import math
import sys
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DATA_SHA256 = "{data_hash}"
SPLIT_SHA256 = "{split_hash}"

def locate(filename):
    candidates = [Path("fixtures") / filename, Path(filename), Path("notebooks/labs/{LAB_ID}/fixtures") / filename]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"找不到 {{filename}}；請把 fixture CSV 與 split manifest 上傳到目前工作目錄或 fixtures/。")

def file_hash(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

data_path = locate("equipment_alerts_v1.csv")
split_path = locate("split_manifest_v1.json")
assert file_hash(data_path) == DATA_SHA256, "fixture checksum 不符"
assert file_hash(split_path) == SPLIT_SHA256, "split manifest checksum 不符"
print({{"python": sys.version.split()[0], "pandas": pd.__version__, "sklearn": sklearn.__version__}})
'''
    load_source = '''data = pd.read_csv(data_path)
split_manifest = json.loads(split_path.read_text(encoding="utf-8"))
assert data.shape == (2000, 10)
assert [c for c in data.columns if c.startswith("feature_")] == [f"feature_{i}" for i in range(1, 9)]
assert int(data["is_anomaly"].sum()) == 100
split_ids = {name: set(ids) for name, ids in split_manifest["splits"].items()}
assert {name: len(ids) for name, ids in split_ids.items()} == {"train": 1200, "validation": 400, "test": 400}
assert not (split_ids["train"] & split_ids["validation"])
assert not (split_ids["train"] & split_ids["test"])
assert not (split_ids["validation"] & split_ids["test"])
assert set(data["row_id"]) == set().union(*split_ids.values())
parts = {name: data[data["row_id"].isin(ids)].sort_values("row_id").reset_index(drop=True) for name, ids in split_ids.items()}
feature_cols = [f"feature_{i}" for i in range(1, 9)]
'''
    manual_source = '''def metrics_from_counts(tn, fp, fn, tp):
    total = tn + fp + fn + tp
    accuracy = (tp + tn) / total
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}

def metrics_from_predictions(y_true, predictions, fn_cost, fp_cost):
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    metrics = metrics_from_counts(int(tn), int(fp), int(fn), int(tp))
    metrics.update({"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp), "average_cost": (fn_cost * fn + fp_cost * fp) / len(y_true)})
    return metrics

worked = metrics_from_counts(tn=362, fp=18, fn=8, tp=12)
expected = {"accuracy": 0.935, "precision": 0.4, "recall": 0.6, "f1": 0.48}
assert all(abs(worked[key] - value) <= 1e-6 for key, value in expected.items())
assert 380 / 400 == 0.95  # 全負類 baseline；其異常 recall 為 0
worked
'''
    train_source = '''def make_model():
    preprocessor = ColumnTransformer([("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), feature_cols)])
    return Pipeline([("preprocess", preprocessor), ("classifier", LogisticRegression(max_iter=500, random_state=42))])

def fit_with_audit(estimator, frame):
    """Fit from the supplied frame and return the row IDs actually observed."""
    observed_row_ids = sorted(frame["row_id"].tolist())
    estimator.fit(frame[feature_cols], frame["is_anomaly"])
    return observed_row_ids

model = make_model()
dummy = DummyClassifier(strategy="most_frequent")
train = parts["train"]
validation = parts["validation"]
test = parts["test"]
fit_row_ids = fit_with_audit(model, train)
dummy_fit_row_ids = fit_with_audit(dummy, train)
validation_scores = model.predict_proba(validation[feature_cols])[:, 1]
assert set(fit_row_ids) == split_ids["train"]
assert dummy_fit_row_ids == fit_row_ids
'''
    independent_solution = '''THRESHOLDS = np.round(np.arange(0.05, 1.0, 0.05), 2)

def evaluate_scores(y_true, scores, threshold, fn_cost, fp_cost):
    predictions = (np.asarray(scores) >= threshold).astype(int)
    metrics = metrics_from_predictions(y_true, predictions, fn_cost, fp_cost)
    metrics["threshold"] = float(threshold)
    return metrics, predictions.tolist()

def select_threshold(frame, scores, fn_cost=20, fp_cost=1):
    """Select from the supplied frame and return the row IDs actually observed."""
    assert len(frame) == len(scores), "scores 與選擇資料列數不一致"
    rows = [evaluate_scores(frame["is_anomaly"], scores, threshold, fn_cost, fp_cost)[0] for threshold in THRESHOLDS]
    selected = min(rows, key=lambda row: (row["average_cost"], -row["recall"], row["threshold"]))
    return selected, rows, sorted(frame["row_id"].tolist())

selected, validation_table, threshold_selection_row_ids = select_threshold(validation, validation_scores)
sensitivity_selected, sensitivity_table, sensitivity_row_ids = select_threshold(validation, validation_scores, fn_cost=5, fp_cost=1)
frozen_threshold = float(selected["threshold"])

# The test split is touched only after both validation decisions are complete and frozen.
test_scores = model.predict_proba(test[feature_cols])[:, 1]
test_result, test_predictions = evaluate_scores(test["is_anomaly"], test_scores, frozen_threshold, 20, 1)
dummy_predictions = dummy.predict(test[feature_cols]).astype(int).tolist()
dummy_result = metrics_from_predictions(test["is_anomaly"], dummy_predictions, 20, 1)

result = {
    "schemaVersion": 1,
    "dataChecksum": DATA_SHA256,
    "splitHash": SPLIT_SHA256,
    "seed": 42,
    "modelConfig": {"estimator": "LogisticRegression", "max_iter": 500, "random_state": 42},
    "fitRowIds": fit_row_ids,
    "dummyFitRowIds": dummy_fit_row_ids,
    "thresholdSelectionRowIds": threshold_selection_row_ids,
    "threshold": frozen_threshold,
    "costs": {"fn": 20, "fp": 1},
    "validationTable": validation_table,
    "test": {**test_result, "rowIds": test["row_id"].tolist(), "yTrue": test["is_anomaly"].astype(int).tolist(), "yPred": test_predictions,
             "dummy": {**dummy_result, "yPred": dummy_predictions}},
    "sensitivityFn5": {"threshold": sensitivity_selected["threshold"], "thresholdSelectionRowIds": sensitivity_row_ids, "validationTable": sensitivity_table},
}
Path("metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
Path("decision.md").write_text("# 試點決策草稿\\n\\n此結果來自合成資料，只驗證流程；請依 metrics.json 填入方案比較、限制與試點下一步。\\n", encoding="utf-8")
selected, test_result
'''
    independent_starter = '''THRESHOLDS = np.round(np.arange(0.05, 1.0, 0.05), 2)

def evaluate_scores(y_true, scores, threshold, fn_cost, fp_cost):
    """待完成：回傳 confusion matrix、四項指標與每筆平均成本。"""
    raise NotImplementedError("待完成 evaluate_scores")

def select_threshold(frame, scores, fn_cost=20, fp_cost=1):
    """待完成：成本最低；同成本依 recall 高、threshold 小排序。"""
    raise NotImplementedError("待完成 select_threshold")

selected, validation_table, threshold_selection_row_ids = select_threshold(validation, validation_scores)
sensitivity_selected, sensitivity_table, sensitivity_row_ids = select_threshold(validation, validation_scores, fn_cost=5, fp_cost=1)
frozen_threshold = float(selected["threshold"])

# 保留輸出範本：必須先完成上方兩個函式，凍結 validation 決策後才能讀 test。
test_scores = model.predict_proba(test[feature_cols])[:, 1]
test_result, test_predictions = evaluate_scores(test["is_anomaly"], test_scores, frozen_threshold, 20, 1)
dummy_predictions = dummy.predict(test[feature_cols]).astype(int).tolist()
dummy_result = metrics_from_predictions(test["is_anomaly"], dummy_predictions, 20, 1)
result = {
    "schemaVersion": 1, "dataChecksum": DATA_SHA256, "splitHash": SPLIT_SHA256, "seed": 42,
    "modelConfig": {"estimator": "LogisticRegression", "max_iter": 500, "random_state": 42},
    "fitRowIds": fit_row_ids, "dummyFitRowIds": dummy_fit_row_ids,
    "thresholdSelectionRowIds": threshold_selection_row_ids, "threshold": frozen_threshold,
    "costs": {"fn": 20, "fp": 1}, "validationTable": validation_table,
    "test": {**test_result, "rowIds": test["row_id"].tolist(), "yTrue": test["is_anomaly"].astype(int).tolist(), "yPred": test_predictions,
             "dummy": {**dummy_result, "yPred": dummy_predictions}},
    "sensitivityFn5": {"threshold": sensitivity_selected["threshold"], "thresholdSelectionRowIds": sensitivity_row_ids, "validationTable": sensitivity_table},
}
Path("metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
Path("decision.md").write_text("# 試點決策草稿\\n\\n請填入方案比較、至少兩項限制與試點下一步。\\n", encoding="utf-8")
'''
    check_source = '''def assert_result(candidate):
    assert set(candidate["fitRowIds"]) == split_ids["train"], "fit rows 必須精確等於 train"
    assert set(candidate["dummyFitRowIds"]) == split_ids["train"], "Dummy fit rows 必須精確等於 train"
    assert set(candidate["thresholdSelectionRowIds"]) == split_ids["validation"], "threshold 只能用 validation"
    assert set(candidate["sensitivityFn5"]["thresholdSelectionRowIds"]) == split_ids["validation"], "敏感度分析只能用 validation"
    payload = candidate["test"]
    assert payload["rowIds"] == test["row_id"].tolist(), "test row IDs 必須精確對齊固定 split"
    assert payload["yTrue"] == test["is_anomaly"].astype(int).tolist(), "test labels 必須對齊 fixture"
    tn, fp, fn, tp = confusion_matrix(payload["yTrue"], payload["yPred"], labels=[0, 1]).ravel()
    assert [int(tn), int(fp), int(fn), int(tp)] == [payload[k] for k in ("tn", "fp", "fn", "tp")]
    recalculated = metrics_from_counts(int(tn), int(fp), int(fn), int(tp))
    for key in ("accuracy", "precision", "recall", "f1"):
        assert math.isfinite(payload[key]) and 0 <= payload[key] <= 1
        assert abs(payload[key] - recalculated[key]) <= 1e-6, f"{key} 與 matrix 不一致"
    expected = min(candidate["validationTable"], key=lambda row: (row["average_cost"], -row["recall"], row["threshold"]))
    assert candidate["threshold"] == expected["threshold"], "threshold 未依 validation 成本與 tie-break 選擇"
    assert payload["dummy"]["yPred"] == dummy.predict(test[feature_cols]).astype(int).tolist(), "Dummy predictions 不一致"

assert_result(result)

def must_reject(mutator):
    broken = copy.deepcopy(result)
    mutator(broken)
    try:
        assert_result(broken)
    except AssertionError:
        return True
    raise AssertionError("fault injection 未被檢查攔下")

# Faults execute the wrong operation first; the audit captures its real input rows.
leaky_model = make_model()
leaky_fit_row_ids = fit_with_audit(leaky_model, data)
assert must_reject(lambda x: x.__setitem__("fitRowIds", leaky_fit_row_ids))
_, _, test_selection_row_ids = select_threshold(test, test_scores)
assert must_reject(lambda x: x.__setitem__("thresholdSelectionRowIds", test_selection_row_ids))
assert must_reject(lambda x: x["test"].update({"precision": x["test"]["recall"], "recall": x["test"]["precision"]}))
print("L3 checks 與 3 個 fault injections 全部通過")
'''
    cells = [
        nbformat.v4.new_markdown_cell("# 設備異常告警：不平衡分類與防資料洩漏\n\n本 lab 使用 2,000 列合成資料，不含個資。請先讀三個學習單元；Colab 使用者需手動上傳 CSV 與 split manifest。", metadata=learning_meta("intro", "setup", [])),
        nbformat.v4.new_code_cell(setup_source, metadata=learning_meta("environment-and-fixture", "setup", [OBJECTIVES["split"]])),
        nbformat.v4.new_code_cell(load_source, metadata=learning_meta("load-fixed-splits", "setup", [OBJECTIVES["split"]])),
        nbformat.v4.new_markdown_cell("## Worked example\n\n先預測 accuracy 是否勝過全負類 baseline，再執行手算驗證。矩陣排列固定為 [[TN, FP], [FN, TP]]。", metadata=learning_meta("worked-explanation", "worked", [OBJECTIVES["metrics"]])),
        nbformat.v4.new_code_cell(manual_source, metadata=learning_meta("worked-matrix", "worked", [OBJECTIVES["metrics"]])),
        nbformat.v4.new_markdown_cell("## Guided practice\n\n先確認所有 fit row IDs 都屬 train，再比較 DummyClassifier 與 LogisticRegression。Pipeline 管理轉換 fit 順序，但仍要人工排除預測當下不存在的欄位。", metadata=learning_meta("guided-pipeline", "guided", [OBJECTIVES["split"], OBJECTIVES["metrics"]])),
        nbformat.v4.new_code_cell(train_source, metadata=learning_meta("fit-train-only", "guided", [OBJECTIVES["split"], OBJECTIVES["metrics"]])),
        nbformat.v4.new_markdown_cell("## Independent task\n\n以 validation 選 threshold，FN 成本 20、FP 成本 1；同成本依 recall 高、threshold 小排序。凍結後只讀一次 test。再把 FN 成本改成 5 做敏感度分析。", metadata=learning_meta("independent-instructions", "independent", [OBJECTIVES["threshold"]])),
        nbformat.v4.new_code_cell(independent_solution, metadata=learning_meta("threshold-and-artifacts", "independent", [OBJECTIVES["threshold"]], starter=independent_starter)),
        nbformat.v4.new_markdown_cell("## Solution note\n\n完整解答會生成 `metrics.json` 與 `decision.md`。數字來自固定合成 fixture，不代表真實設備績效。", metadata=learning_meta("solution-note", "reflection", [OBJECTIVES["threshold"]], audience="solution")),
        nbformat.v4.new_code_cell(check_source, metadata=learning_meta("invariant-and-fault-checks", "check", list(OBJECTIVES.values()))),
        nbformat.v4.new_markdown_cell("## Reflection\n\n回答：正類比例改變會影響什麼？低成本是否足以支持上線？若同設備有多次觀測，切分契約要如何改？", metadata=learning_meta("reflection-prompts", "reflection", [OBJECTIVES["threshold"]])),
    ]
    notebook = nbformat.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "learning": {"labId": LAB_ID, "revision": REVISION},
    })
    for cell in notebook.cells:
        cell["id"] = cell["metadata"]["learning"]["cellId"]
    nbformat.validate(notebook)
    SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, SOURCE_PATH)


def derive_variants() -> dict[str, dict[str, Any]]:
    source = nbformat.read(SOURCE_PATH, as_version=4)
    variants: dict[str, dict[str, Any]] = {}
    for variant in ("starter", "solution"):
        candidate = nbformat.from_dict(json.loads(json.dumps(source)))
        kept = []
        for cell in candidate.cells:
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
        candidate.cells = kept
        nbformat.validate(candidate)
        output = CANDIDATE_DIR / f"{variant}.ipynb"
        output.parent.mkdir(parents=True, exist_ok=True)
        nbformat.write(candidate, output)
        raw = output.read_bytes()
        variants[variant] = {"path": str(output.relative_to(ROOT)), "hash": sha256_bytes(raw), "size": len(raw)}
    return variants


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if regeneration changes committed source inputs")
    args = parser.parse_args()
    tracked = [DATA_PATH, SPLIT_PATH, SOURCE_PATH]
    before = {path: path.read_bytes() for path in tracked if path.exists()}
    data_hash, split_hash = build_fixture()
    build_notebook(data_hash, split_hash)
    variants = derive_variants()
    manifest = {
        "schemaVersion": 1,
        "labId": LAB_ID,
        "revision": REVISION,
        "authorId": "/root/p0_baseline",
        "status": "in_review",
        "data": {"path": str(DATA_PATH.relative_to(ROOT)), "hash": data_hash, "bytes": DATA_PATH.stat().st_size},
        "split": {"path": str(SPLIT_PATH.relative_to(ROOT)), "hash": split_hash, "bytes": SPLIT_PATH.stat().st_size},
        "sourceNotebook": {"path": str(SOURCE_PATH.relative_to(ROOT)), "hash": sha256_bytes(SOURCE_PATH.read_bytes()), "bytes": SOURCE_PATH.stat().st_size},
        "assetLocations": {
            name: f"frontend/public/labs/{LAB_ID}/{REVISION}/{name}.ipynb" for name in variants
        },
        "candidateAssets": variants,
        "releaseGate": {
            "status": "blocked",
            "independentL4Review": "review-lab-semantic-20260907-v1",
            "missing": ["human L5 Colab smoke", "immutable Git commit URL"],
        },
    }
    write_if_changed(CANDIDATE_DIR / "authoring-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    staged_sources = {
        "starter.ipynb": CANDIDATE_DIR / "starter.ipynb",
        "solution.ipynb": CANDIDATE_DIR / "solution.ipynb",
        "equipment_alerts_v1.csv": DATA_PATH,
        "split_manifest_v1.json": SPLIT_PATH,
        "uv.lock": ROOT / "uv.lock",
    }
    asset_manifest = {
        "schemaVersion": 1,
        "labId": LAB_ID,
        "revision": REVISION,
        "status": "in_review",
        "authorId": "/root/p0_baseline",
        "assets": [
            {
                "finalPath": f"frontend/public/labs/{LAB_ID}/{REVISION}/{name}",
                "sourcePath": str(path.relative_to(ROOT)),
                "hash": sha256_bytes(path.read_bytes()),
                "bytes": path.stat().st_size,
            }
            for name, path in staged_sources.items()
        ],
        "releaseGate": {
            "status": "blocked",
            "independentL4Review": "review-lab-semantic-20260907-v1",
            "missing": ["human L5 Colab smoke", "immutable Git commit URL"],
        },
    }
    write_if_changed(
        CANDIDATE_DIR.parents[1] / "lab-assets.json",
        json.dumps(asset_manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n",
    )
    if args.check:
        changed = [str(path.relative_to(ROOT)) for path, raw in before.items() if path.read_bytes() != raw]
        missing_before = [str(path.relative_to(ROOT)) for path in tracked if path not in before]
        if changed or missing_before:
            raise SystemExit(f"regeneration drift: changed={changed}, missing_before={missing_before}")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
