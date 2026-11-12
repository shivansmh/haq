# Flagged record schema (`haq.flag.v1`)

Every flagged payment, card debit, ATM withdrawal or business invoice becomes **one**
structured record. Related emails (debit alert, failure notice, cancellation, refund,
duplicate bank alert) are clustered into that record instead of becoming separate claims.

The machine-readable schemas are:

- [`docs/schemas/haq.flag.v1.schema.json`](schemas/haq.flag.v1.schema.json) — one transaction/invoice.
- [`docs/schemas/haq.email.v1.schema.json`](schemas/haq.email.v1.schema.json) — one compact row per flagged email.

Both are generated from the Pydantic models in `ledger/models.py`.

## Why a ledger instead of one row per email

A single refund normally arrives in a *later* sweep than the debit. The session ledger keys
records on a stable `record_id` plus `identity_keys`, so a later refund updates the record
the user already saw. The ledger is session-scoped and in memory only: no email body, token
or record is written to disk.

## Top-level fields

| Field | Meaning |
|---|---|
| `record_id` | Stable `hf_…` hash derived from claim type, reference, amount, merchant and origin date. |
| `identity_keys` | Matching hints (`ref:…`, `amt:…|merchant:…`) used by the session store to reunite later emails. |
| `case_id` | The grouped case this record came from. |
| `title` / `category_label` | Taxonomy name and a short human label. |
| `claim_type` | One of the five live taxonomy claim types. |
| `segment` | `consumer` or `business`. |
| `vertical` | `gaming`, `ecommerce`, `food_delivery`, `travel`, `utilities`, `business`, `finance`, `other`. |
| `status` | `action_needed`, `tracking`, `resolved`, `reference_only`. |
| `status_label` | Short, resolution-aware label such as “Payment received” or “Waiting for cash reversal”. |
| `amount` | `{ value_paise, currency, display }`; never inferred if not present in an email. |
| `transaction` | Reference, channel, merchant, origin date and origin email id. |
| `resolution` | Whether a refund / reversal / cash / invoice payment was seen, when, and how many days it took. |
| `legal` | Rule stamp, deadline, compliance and compensation assessment (see below). |
| `labels` | Deterministic tags such as `refund-received`, `gaming`, `business`, `rule-seeded`, `merchant:steam`. |
| `risk_flags` | Machine-readable warnings: `rule_not_verified`, `refund_not_received`, `refund_late`, `amount_missing`, `reference_missing`, `duplicate_emails`, `ai_conflict`. |
| `evidence` | Every related email with its role (`debit`, `failure`, `refund`, `payment`, `cancellation`, `atm_failure`, `invoice`) and duplicate markers. |
| `timeline` | Dated, ordered events for the UI. |
| `recommended_actions` | Plain next steps; never a promise of compensation. |
| `ai` | Optional Groq labels. Advisory only. |
| `tracking` | `first_seen_at`, `last_seen_at`, `sweep_count`. |
| `needs_review` | True when the amount is missing, a duplicate exists, or AI disagrees. |
| `safety_note` | Explicit statement that this is an evidence record, not legal advice. |

## Refund and rule compliance

`resolution.received` answers **“did the money come back?”**. `legal.compliance` answers
**“did it arrive within the linked rule's turnaround time?”**:

| Value | Meaning |
|---|---|
| `on_time` | Refund/payment received on or before the verified deadline. |
| `late` | Received after the verified deadline; compensation may be computed. |
| `received_rule_unverified` | Received, but the linked rule is `Seeded`/`Parked`, so no legal conclusion is drawn. |
| `not_due_yet` | Verified rule deadline has not passed and no refund is seen. |
| `not_received_past_deadline` | Verified rule deadline passed and no refund is seen. |
| `not_received_rule_unverified` | No refund seen and the linked rule is not verified. |
| `unknown` | No rule and/or no usable dates. |

Only a `Verified` registry entry produces a `deadline_date` and `compensation.computed = true`.
Seeded rules may show an `indicative_deadline_date` and `indicative_paise`, always stamped
`UNVERIFIED RULE`. Missing rules produce `NO RULE` and no deadline.

## Compact per-email projection

Every flagged email also carries `structured` (`haq.email.v1`) with the same `record_id`,
its `role`, `duplicate`/`duplicate_of`, `cluster_size`, amount, reference, segment, vertical
and labels. This lets a UI or export treat each email as a row without losing the cluster.

## Example (abridged)

```json
{
  "schema_version": "haq.flag.v1",
  "record_id": "hf_8e299d587078bcb5",
  "identity_keys": ["claim:upi_failed_debited|ref:UPIREF-DEMO-002"],
  "title": "Card/net-banking/wallet debited, order not confirmed",
  "segment": "consumer",
  "vertical": "gaming",
  "status": "resolved",
  "amount": { "value_paise": 129900, "currency": "INR", "display": "₹1,299.00" },
  "transaction": { "merchant": "Steam", "reference": "UPIREF-DEMO-002", "channel": "UPI" },
  "resolution": {
    "kind": "refund",
    "received": true,
    "received_on": "2026-11-12",
    "days_to_resolution": 7,
    "label": "Refund received"
  },
  "legal": {
    "rule_id": "R-004",
    "rule_status": "Seeded",
    "rule_verified": false,
    "stamp": "UNVERIFIED RULE",
    "compliance": "received_rule_unverified",
    "compliance_label": "Refund received; the linked rule is not verified",
    "days_overdue": null
  },
  "labels": ["card_debited_order_unconfirmed", "gaming", "consumer", "refund-received", "rule-seeded"],
  "evidence": [
    { "email_id": "msg-011", "role": "debit", "duplicate": false },
    { "email_id": "msg-012", "role": "failure", "duplicate": false },
    { "email_id": "msg-013", "role": "refund", "duplicate": false }
  ]
}
```

## Product boundary

Haq reports what the linked rule says. It does **not** present seeded research as a legal
conclusion, does not file claims, and does not store email content. A `late` result is a
prompt to ask the bank or payment app for a written explanation, not a guarantee of money.
