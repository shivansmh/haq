from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from llm.client import FakeClient, LLMClient
from llm.config import LLMSettings
from llm.groq_client import GroqClient
from llm.payload import MessageInput, build_provider_payload
from llm.trust import TrustedValue, assign_tier, value_for_calculation
from llm.verify import verify_quote

ROOT = Path(__file__).parents[1]
CORPUS = ROOT / "data" / "emails"


def _load_cases(split: str) -> list[tuple[dict[str, Any], str]]:
    cases: list[tuple[dict[str, Any], str]] = []
    for label_path in sorted(CORPUS.glob("email-*.json")):
        label = json.loads(label_path.read_text(encoding="utf-8"))
        if split != "all" and label["split"] != split:
            continue
        text = (CORPUS / f"{label['fixture_id']}.txt").read_text(encoding="utf-8")
        cases.append((label, text))
    return cases


def _payload(label: dict[str, Any], text: str):
    lines = text.splitlines()
    subject = next((line.removeprefix("Subject: ") for line in lines if line.startswith("Subject:")), "Synthetic fixture")
    sender = next((line.removeprefix("Sender: ") for line in lines if line.startswith("Sender:")), "synthetic sender")
    body = "\n".join(lines[lines.index("") + 1 :]) if "" in lines else text
    prepared = build_provider_payload(
        MessageInput(
            message_id=label["fixture_id"],
            sender=sender,
            subject=subject,
            snippet=body[:500],
            body_text=body,
            received_at=None,
        ),
        LLMSettings(max_message_chars=8000),
    )
    return prepared.payload


def _percent(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def run(client: LLMClient, *, split: str = "all") -> dict[str, Any]:
    cases = _load_cases(split)
    latencies_ms: list[float] = []
    status_counts: Counter[str] = Counter()
    type_seen: Counter[str] = Counter()
    type_predicted: Counter[str] = Counter()
    type_correct: Counter[str] = Counter()
    template_seen: Counter[str] = Counter()
    template_correct: Counter[str] = Counter()
    field_total = 0
    field_exact = 0
    verified_quotes = 0
    emitted_fields = 0
    fabricated_fields = 0
    review_count = 0
    injection_total = 0
    injection_passed = 0
    confidence_bins: defaultdict[str, list[int]] = defaultdict(list)

    for label, text in cases:
        payload = _payload(label, text)
        started = time.perf_counter()
        triage = client.triage(payload)
        extracted = client.extract(payload)
        latencies_ms.append((time.perf_counter() - started) * 1000)
        status_counts[f"triage:{triage.llm_status.value}"] += 1
        status_counts[f"extract:{extracted.llm_status.value}"] += 1
        if triage.result is not None:
            predicted_type = triage.result.signal_type.value
            if triage.result.needs_review:
                review_count += 1
        else:
            predicted_type = "unknown"
        expected_types = {event["type"] for event in label["events"] if event["type"] not in {"none", "unknown"}}
        for expected in expected_types:
            type_seen[expected] += 1
            template_seen[label["template_id"]] += 1
            if predicted_type == expected:
                type_correct[expected] += 1
                template_correct[label["template_id"]] += 1
        type_predicted[predicted_type] += 1

        if extracted.result is not None:
            result = extracted.result
            for field in ("amount", "transaction_reference", "event_date", "reversal_date"):
                field_total += 1
                expected_status = label["field_status"]["amount" if field == "amount" else "reference" if field == "transaction_reference" else "date"]
                actual_status = result.amount.status.value if field == "amount" else getattr(result, field).status.value
                if actual_status == expected_status:
                    field_exact += 1
                source_quote = result.amount.source_quote if field == "amount" else getattr(result, field).source_quote
                value = result.amount.value_paise if field == "amount" else getattr(result, field).value
                if value is not None:
                    emitted_fields += 1
                    try:
                        kind = "amount" if field == "amount" else "reference" if field == "transaction_reference" else "date"
                        verify_quote(payload.model_dump_json(), source_quote or "", value, kind=kind)
                        verified_quotes += 1
                    except Exception:
                        fabricated_fields += 1
            if result.trust_tier.value == "llm_suggestion":
                tier = assign_tier(source="ai", verified_in_text=verified_quotes > 0)
                try:
                    value_for_calculation(TrustedValue(result.amount.value_paise, tier, "amount"))
                except Exception:
                    pass
        if label["category"] == "injection_adversarial":
            injection_total += 1
            if triage.result is not None and triage.result.needs_review:
                injection_passed += 1
        confidence_bins["mock_or_provider"].append(1 if triage.result is not None else 0)

    per_type = {
        key: {
            "recall": _percent(type_correct[key], type_seen[key]),
            "precision": _percent(type_correct[key], type_predicted[key]),
            "expected": type_seen[key],
            "predicted": type_predicted[key],
        }
        for key in sorted(set(type_seen) | set(type_predicted))
    }
    per_template = {
        key: {"recall": _percent(template_correct[key], template_seen[key]), "expected": template_seen[key]}
        for key in sorted(template_seen)
    }
    latencies_ms.sort()
    p50 = latencies_ms[len(latencies_ms) // 2] if latencies_ms else 0.0
    p95 = latencies_ms[min(len(latencies_ms) - 1, int(len(latencies_ms) * 0.95))] if latencies_ms else 0.0
    return {
        "schema_version": "a5-metrics-v1",
        "synthetic_only": True,
        "split": split,
        "emails": len(cases),
        "event_recall_precision_by_type": per_type,
        "event_recall_by_sender_template": per_template,
        "field_exact_match": _percent(field_exact, field_total),
        "verified_quote_rate": _percent(verified_quotes, emitted_fields),
        "fabricated_field_rate": _percent(fabricated_fields, emitted_fields),
        "fabricated_field_upper_bound": _percent(fabricated_fields + 1, max(emitted_fields, 1)),
        "unknown_rate": _percent(type_predicted["unknown"], len(cases)),
        "review_rate": _percent(review_count, len(cases)),
        "unseen_template_recall": _percent(sum(template_correct.values()), sum(template_seen.values())) if split in {"unseen", "all"} else None,
        "injection_pass_rate": _percent(injection_passed, injection_total),
        "calibration": {
            bucket: {
                "count": len(values),
                "observed_rate": round(statistics.mean(values), 4) if values else 0.0,
            }
            for bucket, values in confidence_bins.items()
        },
        "cost_per_100_emails_usd": 0.0 if isinstance(client, FakeClient) else None,
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
        "status_counts": dict(sorted(status_counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="use FakeClient and never call a provider")
    parser.add_argument("--split", choices=["all", "dev", "held-out", "unseen"], default="all")
    parser.add_argument("--out", type=Path, default=Path("eval/reports/latest.json"))
    args = parser.parse_args()
    if args.mock:
        client: LLMClient = FakeClient()
    else:
        cap = float(__import__("os").environ.get("GROQ_SPEND_CAP_USD", "0"))
        if cap <= 0:
            raise SystemExit("GROQ_SPEND_CAP_USD must be positive for a provider run; use --mock for the current $0 gate")
        client = GroqClient(spend_cap_usd=cap)
    report = run(client, split=args.split)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"emails": report["emails"], "split": report["split"], "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
