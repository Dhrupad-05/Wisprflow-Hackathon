"""Evaluate deterministic/production routing against the reviewed JSONL fixture."""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from services.api.router import route

ROOT = Path(__file__).parents[2]


def evaluate(split: str | None = None) -> dict:
    rows = [json.loads(line) for line in (Path(__file__).parent / "utterances.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if split:
        rows = [row for row in rows if row["split"] == split]
    matrix = defaultdict(Counter)
    domain_total, domain_ok = Counter(), Counter()
    language_total, language_ok = Counter(), Counter()
    named_total = named_ok = 0
    for row in rows:
        result = route(row["text"])
        got = f"{result['domain']}.{result['service']}"
        expected = row["label"]
        matrix[expected][got] += 1
        domain = expected.split(".")[0]
        domain_total[domain] += 1
        domain_ok[domain] += got.split(".")[0] == domain
        language_total[row["language"]] += 1
        language_ok[row["language"]] += got == expected
        if row.get("named_entity"):
            named_total += 1
            named_ok += got == expected
    exact = sum(language_ok.values()) / len(rows) if rows else 0
    return {"split": split or "all", "count": len(rows), "accuracy": exact, "domain_accuracy": {k: domain_ok[k] / domain_total[k] for k in sorted(domain_total)}, "language_accuracy": {k: language_ok[k] / language_total[k] for k in sorted(language_total)}, "named_entity_accuracy": named_ok / named_total if named_total else 1.0, "named_entity_count": named_total, "confusion_matrix": {k: dict(v) for k, v in sorted(matrix.items())}}


def write_reports(metrics: dict) -> None:
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    stem = f"eval-{metrics['split']}"
    (reports / f"{stem}.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"# Phase 7 evaluation ({metrics['split']})", "", f"- Rows: {metrics['count']}", f"- Exact accuracy: {metrics['accuracy']:.1%}", f"- Named-entity accuracy: {metrics['named_entity_accuracy']:.1%} ({metrics['named_entity_count']} rows)", "", "## Per domain", "", "| Domain | Accuracy |", "|---|---:|"]
    lines += [f"| {k} | {v:.1%} |" for k, v in metrics["domain_accuracy"].items()]
    lines += ["", "## Per language", "", "| Language | Accuracy |", "|---|---:|"]
    lines += [f"| {k} | {v:.1%} |" for k, v in metrics["language_accuracy"].items()]
    (reports / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    labels = sorted(metrics["confusion_matrix"])
    with (reports / f"{stem}-confusion.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["expected\\predicted", *labels])
        for label in labels:
            writer.writerow([label, *[metrics["confusion_matrix"][label].get(pred, 0) for pred in labels]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"])
    args = parser.parse_args()
    result = evaluate(args.split)
    write_reports(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
