#!/usr/bin/env python3
"""
Analyse results from SlideGuard ablation experiments.

Reads JSON result files produced by run_ablations.py, computes per-criterion
metrics, and prints a Markdown comparison table.  Optionally compares against
ground-truth annotations when --ground-truth is supplied.

Usage:
    python experiments/analyze_results.py --results-dir experiments/results
    python experiments/analyze_results.py --results-dir experiments/results --ground-truth data/annotations --csv results.csv
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_fallback(eval_data: dict) -> bool:
    """Detect fallback / not-applicable results in serialised evaluation dicts."""
    if eval_data.get("error_message") == "Evaluation failed - fallback result":
        return True
    if eval_data.get("__slideguard_not_applicable__"):
        return True
    if eval_data.get("reason") == "Criterion not applicable to this slide":
        return True
    return False


def _issue_count(eval_data: dict) -> int:
    """Count non-zero-severity items in evaluation_results."""
    results = eval_data.get("evaluation_results", [])
    return sum(1 for r in results if r.get("severity", 0) > 0)


def _score(eval_data: dict) -> Optional[float]:
    return eval_data.get("score")


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------

CriterionMetrics = Dict[str, Any]


def extract_metrics(result: dict) -> Dict[str, CriterionMetrics]:
    """Extract per-criterion metrics from a single FullEvaluation dict.

    Returns {criterion_id: {score, issue_count, is_fallback}} for every
    criterion that was evaluated (slide-level are aggregated across slides).
    """
    metrics: Dict[str, CriterionMetrics] = {}

    for slide_eval in result.get("slide_evaluations", []):
        for crit_id, crit_data in (slide_eval.get("evaluations") or {}).items():
            if crit_data is None:
                continue
            entry = metrics.setdefault(crit_id, {
                "scores": [],
                "issue_counts": [],
                "fallbacks": 0,
                "total": 0,
            })
            entry["total"] += 1
            if _is_fallback(crit_data):
                entry["fallbacks"] += 1
            else:
                s = _score(crit_data)
                if s is not None:
                    entry["scores"].append(s)
                entry["issue_counts"].append(_issue_count(crit_data))

    deck_eval = result.get("deck_evaluations")
    if deck_eval:
        for crit_id, crit_data in (deck_eval.get("evaluations") or {}).items():
            if crit_data is None:
                continue
            entry = metrics.setdefault(crit_id, {
                "scores": [],
                "issue_counts": [],
                "fallbacks": 0,
                "total": 0,
            })
            entry["total"] += 1
            if _is_fallback(crit_data):
                entry["fallbacks"] += 1
            else:
                s = _score(crit_data)
                if s is not None:
                    entry["scores"].append(s)
                entry["issue_counts"].append(_issue_count(crit_data))

    return metrics


def aggregate_metrics(
    all_metrics: List[Dict[str, CriterionMetrics]],
) -> Dict[str, Dict[str, float]]:
    """Aggregate metrics across multiple PDFs.

    Returns {criterion_id: {mean_score, mean_issues, fallback_rate}}.
    """
    combined: Dict[str, CriterionMetrics] = {}
    for per_pdf in all_metrics:
        for crit_id, m in per_pdf.items():
            c = combined.setdefault(crit_id, {
                "scores": [],
                "issue_counts": [],
                "fallbacks": 0,
                "total": 0,
            })
            c["scores"].extend(m["scores"])
            c["issue_counts"].extend(m["issue_counts"])
            c["fallbacks"] += m["fallbacks"]
            c["total"] += m["total"]

    aggregated: Dict[str, Dict[str, float]] = {}
    for crit_id, c in sorted(combined.items()):
        aggregated[crit_id] = {
            "mean_score": round(mean(c["scores"]), 2) if c["scores"] else float("nan"),
            "mean_issues": round(mean(c["issue_counts"]), 2) if c["issue_counts"] else 0.0,
            "fallback_rate": round(c["fallbacks"] / c["total"] * 100, 1) if c["total"] else 0.0,
            "n_slides": c["total"],
        }
    return aggregated


# ---------------------------------------------------------------------------
# Ground-truth comparison (optional)
# ---------------------------------------------------------------------------

def compute_detection_rate(
    result: dict,
    ground_truth: dict,
) -> Dict[str, float]:
    """Compute fraction of ground-truth issues matched by auto-generated ones.

    Both *result* and *ground_truth* are FullEvaluation-shaped dicts.
    Matching is approximate: an auto-generated comment is counted as matching
    a ground-truth comment if the criterion id is the same and the slide id
    overlaps.  Returns {criterion_id: detection_rate_pct}.
    """
    gt_by_crit: Dict[str, Set[int]] = defaultdict(set)
    for slide_eval in ground_truth.get("slide_evaluations", []):
        sid = slide_eval.get("slide_id", -1)
        for crit_id, crit_data in (slide_eval.get("evaluations") or {}).items():
            if crit_data and _issue_count(crit_data) > 0:
                gt_by_crit[crit_id].add(sid)

    gt_deck = ground_truth.get("deck_evaluations")
    if gt_deck:
        for crit_id, crit_data in (gt_deck.get("evaluations") or {}).items():
            if crit_data and _issue_count(crit_data) > 0:
                gt_by_crit[crit_id].add(-1)

    auto_by_crit: Dict[str, Set[int]] = defaultdict(set)
    for slide_eval in result.get("slide_evaluations", []):
        sid = slide_eval.get("slide_id", -1)
        for crit_id, crit_data in (slide_eval.get("evaluations") or {}).items():
            if crit_data and not _is_fallback(crit_data) and _issue_count(crit_data) > 0:
                auto_by_crit[crit_id].add(sid)

    auto_deck = result.get("deck_evaluations")
    if auto_deck:
        for crit_id, crit_data in (auto_deck.get("evaluations") or {}).items():
            if crit_data and not _is_fallback(crit_data) and _issue_count(crit_data) > 0:
                auto_by_crit[crit_id].add(-1)

    rates: Dict[str, float] = {}
    for crit_id, gt_slides in gt_by_crit.items():
        detected = gt_slides & auto_by_crit.get(crit_id, set())
        rates[crit_id] = round(len(detected) / len(gt_slides) * 100, 1) if gt_slides else 0.0
    return rates


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_comparison_table(
    ablation_data: Dict[str, Dict[str, Dict[str, float]]],
    metric: str = "mean_score",
) -> str:
    """Print a Markdown table comparing a single metric across ablations."""
    ablations = list(ablation_data.keys())
    all_criteria: List[str] = sorted({
        c for agg in ablation_data.values() for c in agg
    })

    header = f"| Criterion | {' | '.join(ablations)} |"
    sep = f"|{'---|' * (len(ablations) + 1)}"
    rows = [header, sep]
    for crit in all_criteria:
        vals = []
        for abl in ablations:
            v = ablation_data[abl].get(crit, {}).get(metric, float("nan"))
            vals.append(f"{v:.1f}" if not (v != v) else "—")
        rows.append(f"| {crit} | {' | '.join(vals)} |")

    table = "\n".join(rows)
    return table


def write_csv(
    path: str,
    ablation_data: Dict[str, Dict[str, Dict[str, float]]],
) -> None:
    ablations = sorted(ablation_data.keys())
    all_criteria = sorted({
        c for agg in ablation_data.values() for c in agg
    })
    metrics = ["mean_score", "mean_issues", "fallback_rate", "n_slides"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header = ["criterion"]
        for abl in ablations:
            for m in metrics:
                header.append(f"{abl}_{m}")
        w.writerow(header)
        for crit in all_criteria:
            row = [crit]
            for abl in ablations:
                for m in metrics:
                    v = ablation_data[abl].get(crit, {}).get(m, "")
                    row.append(v)
            w.writerow(row)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse SlideGuard ablation results")
    parser.add_argument(
        "--results-dir", required=True,
        help="Root directory produced by run_ablations.py",
    )
    parser.add_argument(
        "--ground-truth", default=None,
        help="Directory of ground-truth JSON annotations (same naming as results)",
    )
    parser.add_argument(
        "--csv", default=None,
        help="Optional path to write a CSV summary",
    )
    args = parser.parse_args()

    results_root = Path(args.results_dir)
    if not results_root.is_dir():
        parser.error(f"Results directory not found: {results_root}")

    ablation_dirs = sorted(
        d for d in results_root.iterdir() if d.is_dir()
    )
    if not ablation_dirs:
        parser.error("No ablation subdirectories found")

    ablation_agg: Dict[str, Dict[str, Dict[str, float]]] = {}

    for abl_dir in ablation_dirs:
        abl_name = abl_dir.name
        json_files = sorted(abl_dir.glob("*.json"))
        if not json_files:
            print(f"[WARN] No JSON files in {abl_dir}, skipping")
            continue

        all_metrics = []
        for jf in json_files:
            data = _load_json(str(jf))
            all_metrics.append(extract_metrics(data))

        ablation_agg[abl_name] = aggregate_metrics(all_metrics)
        print(f"Loaded {len(json_files)} result(s) for ablation '{abl_name}'")

    print("\n## Mean Score by Criterion\n")
    print(print_comparison_table(ablation_agg, metric="mean_score"))

    print("\n## Mean Issues per Slide by Criterion\n")
    print(print_comparison_table(ablation_agg, metric="mean_issues"))

    print("\n## Fallback (Parse-Failure) Rate (%)\n")
    print(print_comparison_table(ablation_agg, metric="fallback_rate"))

    # Ground-truth detection rates
    if args.ground_truth:
        gt_dir = Path(args.ground_truth)
        if gt_dir.is_dir():
            print("\n## Detection Rate vs Ground Truth (%)\n")
            det_agg: Dict[str, Dict[str, List[float]]] = {}
            for abl_dir in ablation_dirs:
                abl_name = abl_dir.name
                per_crit: Dict[str, List[float]] = defaultdict(list)
                for jf in sorted(abl_dir.glob("*.json")):
                    gt_file = gt_dir / jf.name
                    if not gt_file.exists():
                        continue
                    result = _load_json(str(jf))
                    gt = _load_json(str(gt_file))
                    rates = compute_detection_rate(result, gt)
                    for crit, rate in rates.items():
                        per_crit[crit].append(rate)
                det_agg[abl_name] = {
                    c: round(mean(vals), 1) for c, vals in per_crit.items()
                }

            all_gt_criteria = sorted({c for d in det_agg.values() for c in d})
            ablations = list(det_agg.keys())
            header = f"| Criterion | {' | '.join(ablations)} |"
            sep = f"|{'---|' * (len(ablations) + 1)}"
            rows = [header, sep]
            for crit in all_gt_criteria:
                vals = [f"{det_agg[a].get(crit, 0.0):.1f}" for a in ablations]
                rows.append(f"| {crit} | {' | '.join(vals)} |")
            print("\n".join(rows))
        else:
            print(f"[WARN] Ground-truth path not found: {gt_dir}")

    # Overall summary row
    print("\n## Overall Summary\n")
    ablations = list(ablation_agg.keys())
    header = f"| Metric | {' | '.join(ablations)} |"
    sep = f"|{'---|' * (len(ablations) + 1)}"
    rows = [header, sep]
    for metric_name in ["mean_score", "mean_issues", "fallback_rate"]:
        vals = []
        for abl in ablations:
            all_vals = [
                v[metric_name] for v in ablation_agg[abl].values()
                if not (v[metric_name] != v[metric_name])  # skip NaN
            ]
            avg = round(mean(all_vals), 2) if all_vals else 0.0
            vals.append(f"{avg:.2f}")
        rows.append(f"| {metric_name} | {' | '.join(vals)} |")
    print("\n".join(rows))

    if args.csv:
        write_csv(args.csv, ablation_agg)
        print(f"\nCSV written to {args.csv}")


if __name__ == "__main__":
    main()
