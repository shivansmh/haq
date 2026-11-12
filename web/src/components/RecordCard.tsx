import { useState } from "react";
import {
  Check,
  ChevronDown,
  Clock,
  Copy,
  Scale,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  inr,
  RECORD_STATUS_LABELS,
  VERTICAL_LABELS,
  type EvidenceRole,
  type FlaggedRecord,
} from "@/lib/haq-types";

const ROLE_LABELS: Record<EvidenceRole, string> = {
  debit: "Debit alert",
  failure: "Payment failure",
  refund: "Refund credit",
  payment: "Payment received",
  cancellation: "Cancellation",
  atm_failure: "ATM failure",
  invoice: "Invoice",
  duplicate: "Duplicate",
  other: "Related email",
};

const STATUS_STYLES: Record<FlaggedRecord["status"], string> = {
  action_needed: "bg-destructive/15 text-destructive",
  tracking: "bg-warning/15 text-warning",
  resolved: "bg-primary/15 text-primary",
  reference_only: "bg-secondary text-muted-foreground",
};

const COMPLIANCE_STYLES: Record<FlaggedRecord["legal"]["compliance"], string> = {
  on_time: "text-primary",
  late: "text-destructive",
  received_rule_unverified: "text-warning",
  not_due_yet: "text-muted-foreground",
  not_received_past_deadline: "text-destructive",
  not_received_rule_unverified: "text-warning",
  unknown: "text-muted-foreground",
};

function formatDate(value: string | null | undefined) {
  if (!value) return "date not found";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function riskLabel(flag: string) {
  return flag.replace(/_/g, " ");
}

function cleanEvidenceQuote(value: string) {
  return value
    .replace(/#outlook\s+a\s*\{[^}]*\}/gi, "")
    .replace(/\.ReadMsgBody\s*\{[^}]*\}/gi, "")
    .replace(/\.ExternalClass(?:\s+\*)?\s*\{[^}]*\}/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function RecordCard({ record }: { record: FlaggedRecord }) {
  const [open, setOpen] = useState(false);
  const [showJson, setShowJson] = useState(false);
  const [copied, setCopied] = useState(false);
  const legal = record.legal;
  const evidence = record.evidence ?? [];
  const timeline = record.timeline ?? [];
  const labels = record.labels ?? [];
  const unmatchedResolution =
    record.resolution.received && !record.transaction.origin_email_id;
  const resolutionNoun =
    record.resolution.kind === "payment"
      ? "Payment"
      : record.resolution.kind === "cash"
        ? "Cash reversal"
        : "Refund";
  const actions = unmatchedResolution
    ? [
        `${resolutionNoun} confirmation was found, but the original transaction was not. Check it against your records before treating it as resolved. No legal timing or compensation is assessed until the transaction is matched.`,
      ]
    : record.resolution.received && !legal.rule_verified
      ? [
          `${resolutionNoun} appears received. Haq could not assess legal timing, so no compensation is calculated. Keep the confirmation with the transaction evidence.`,
        ]
      : (record.recommended_actions ?? []);
  const verticalLabel = VERTICAL_LABELS[record.vertical];
  const legalStampClass = unmatchedResolution
    ? "bg-secondary text-muted-foreground"
    : legal.stamp === "VERIFIED RULE"
      ? "bg-primary/15 text-primary"
      : legal.stamp === "UNVERIFIED RULE"
        ? "bg-warning/15 text-warning"
        : "bg-secondary text-muted-foreground";
  const legalTimingText = unmatchedResolution
    ? `No legal deadline is assessed for an unmatched ${resolutionNoun.toLowerCase()}.`
    : legal.deadline_date
      ? `Deadline ${formatDate(legal.deadline_date)}`
      : legal.rule_verified
        ? "No deadline is asserted for this record."
        : "Timing and compensation are not assessed for an unverified rule.";

  const copyJson = async () => {
    await navigator.clipboard.writeText(JSON.stringify(record, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(record, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `haq-${record.record_id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex w-full flex-wrap items-start gap-3 p-4 text-left transition-colors hover:bg-secondary/40 sm:items-center sm:gap-4 sm:p-5"
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">{record.category_label}</p>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                STATUS_STYLES[record.status],
              )}
            >
              {record.status_label || RECORD_STATUS_LABELS[record.status]}
            </span>
            {record.needs_review && (
              <span className="rounded-full border border-warning/30 px-2 py-0.5 text-[10px] font-semibold text-warning">
                Review needed
              </span>
            )}
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {verticalLabel !== "Other" && (
              <>
                {record.segment === "business" && verticalLabel !== "Business" && "Business · "}
                {verticalLabel} ·{" "}
              </>
            )}
            {record.transaction.merchant ?? "Counterparty not identified"}
            {record.transaction.reference ? ` · Ref ${record.transaction.reference}` : " · no reference"}
            {` · ${evidence.length} email${evidence.length === 1 ? "" : "s"}`}
            {record.tracking.sweep_count > 1
              ? ` · seen in ${record.tracking.sweep_count} sweeps`
              : ""}
          </p>
          <p className={cn("mt-1 text-xs font-medium", COMPLIANCE_STYLES[legal.compliance])}>
            {record.resolution.received && !legal.rule_verified
              ? `${resolutionNoun} received · legal timing not assessed`
              : legal.compliance_label}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-display text-2xl">{inr(record.amount.value_paise)}</p>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {unmatchedResolution ? `${resolutionNoun} received` : "Transaction amount"}
          </p>
          {record.transaction.origin_date && !unmatchedResolution && (
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              {formatDate(record.transaction.origin_date)}
            </p>
          )}
        </div>
        <ChevronDown className={cn("size-4 shrink-0 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="animate-rise space-y-6 border-t border-border p-4 sm:p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl bg-secondary p-4">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Clock className="size-3.5" /> Resolution
              </p>
              <p className="mt-2 text-sm">
                {record.resolution.received
                  ? `Received ${formatDate(record.resolution.received_on)}${
                      !unmatchedResolution && record.resolution.days_to_resolution != null
                        ? ` · ${record.resolution.days_to_resolution} day${record.resolution.days_to_resolution === 1 ? "" : "s"} after the transaction`
                        : ""
                    }`
                  : "Not seen in the swept emails yet"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {unmatchedResolution
                  ? `This ${resolutionNoun.toLowerCase()} could not be matched to an original transaction.`
                  : record.status_label}
                {legal.days_overdue != null && legal.days_overdue > 0
                  ? ` · ${legal.days_overdue} day${legal.days_overdue === 1 ? "" : "s"} beyond the rule's timeline`
                  : ""}
              </p>
            </div>
            <div className="rounded-xl bg-secondary p-4">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Scale className="size-3.5" /> Legal rule
              </p>
              <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                    unmatchedResolution
                      ? "bg-secondary text-muted-foreground"
                      : legal.stamp === "VERIFIED RULE"
                      ? "bg-primary/15 text-primary"
                      : legal.stamp === "UNVERIFIED RULE"
                        ? "bg-warning/15 text-warning"
                        : "bg-secondary text-muted-foreground",
                  )}
                >
                  {unmatchedResolution ? "TRANSACTION NOT MATCHED" : legal.stamp}
                </span>
                {!unmatchedResolution && <span>{legal.rule_id ?? "No linked rule"}</span>}
                {!unmatchedResolution && legal.rule_id && (
                  <span className="text-xs text-muted-foreground">({legal.rule_status})</span>
                )}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {unmatchedResolution
                  ? `A ${resolutionNoun.toLowerCase()} email was found without the original transaction evidence. No legal timeline or compensation assessment is applied.`
                  : legal.note}
              </p>
              <p className="mt-2 text-xs">
                {legalTimingText}
              </p>
              {legal.compensation.note && legal.rule_verified && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {legal.compensation.computed && legal.compensation.amount_paise != null
                    ? `Compensation: ${inr(legal.compensation.amount_paise)}. ${legal.compensation.note}`
                    : legal.compensation.note}
                </p>
              )}
              {legal.citation && legal.rule_verified && (
                <p className="mt-1 text-[10px] text-muted-foreground">Source: {legal.citation}</p>
              )}
            </div>
          </div>

          {legal.compliance === "late" && (
            <div className="flex gap-3 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm">
              <ShieldAlert className="mt-0.5 size-4 shrink-0 text-destructive" />
              <p>
                The refund arrived after the linked rule's turnaround time. Ask the bank or payment
                app to confirm any compensation in writing.
              </p>
            </div>
          )}

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Timeline
              </p>
              <ol className="mt-2 space-y-2">
                {timeline.map((item) => (
                  <li key={`${item.email_id}-${item.event}`} className="flex gap-3 text-sm">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
                    <span>
                      <span className="block">{item.event}</span>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(item.date)}
                        {item.amount_paise != null ? ` · ${inr(item.amount_paise)}` : ""}
                      </span>
                    </span>
                  </li>
                ))}
                {!timeline.length && (
                  <li className="text-sm text-muted-foreground">No dated events.</li>
                )}
              </ol>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Emails in this record
              </p>
              <ul className="mt-2 space-y-2">
                {evidence.map((item) => (
                  <li key={item.email_id} className="rounded-lg bg-secondary p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-border px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground">
                        {ROLE_LABELS[item.role] ?? item.role}
                      </span>
                      {item.duplicate && (
                        <span className="rounded-full bg-warning/15 px-1.5 py-0.5 text-[10px] font-semibold text-warning">
                          Duplicate
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground">{formatDate(item.date)}</span>
                    </div>
                    <p className="mt-1 font-medium">{item.subject}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                      “{cleanEvidenceQuote(item.quote)}”
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {record.risk_flags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {record.risk_flags.map((flag) => (
                <span
                  key={flag}
                  className="rounded-full border border-border px-2 py-0.5 text-[10px] font-semibold text-muted-foreground"
                >
                  {flag === "original_transaction_not_matched"
                    ? "original transaction not matched"
                    : riskLabel(flag)}
                </span>
              ))}
            </div>
          )}

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              What to do next
            </p>
            <ul className="mt-2 space-y-1.5 text-sm">
              {actions.map((action) => (
                <li key={action} className="flex gap-2">
                  <Check className="mt-0.5 size-3.5 shrink-0 text-primary" />
                  {action}
                </li>
              ))}
            </ul>
          </div>

          {record.ai.status === "ok" && record.ai.summary && (
            <div className="flex gap-3 rounded-xl border border-border bg-secondary/60 p-4 text-sm">
              <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
              <div>
                <p>{record.ai.summary}</p>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  Advisory label from {record.ai.model ?? "the model"}; amounts and rule status stay
                  deterministic.
                </p>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {labels.map((label) => (
              <span
                key={label}
                className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-muted-foreground"
              >
                #{label}
              </span>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <button
              onClick={() => setShowJson((value) => !value)}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-semibold hover:bg-secondary"
            >
              {showJson ? "Hide JSON" : "View JSON"}
            </button>
            <button
              onClick={copyJson}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold hover:bg-secondary"
            >
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? "Copied" : "Copy record"}
            </button>
            <button
              onClick={downloadJson}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-semibold hover:bg-secondary"
            >
              Download JSON
            </button>
            <span className="text-[10px] text-muted-foreground">
              {record.schema_version} · {record.record_id}
            </span>
          </div>

          {showJson && (
            <pre className="max-h-96 overflow-auto rounded-xl bg-secondary p-4 text-[11px] leading-relaxed">
              {JSON.stringify(record, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function RecordSummaryStrip({
  summary,
}: {
  summary: {
    total_records: number;
    refunds_received: number;
    refunds_pending: number;
    refunds_late: number;
    action_needed: number;
    business_records: number;
    gaming_records: number;
  };
}) {
  const cells = [
    ["Tracked records", summary.total_records],
    ["Resolved", summary.refunds_received],
    ["Pending", summary.refunds_pending],
    ["Late", summary.refunds_late],
    ["Action needed", summary.action_needed],
    ["Business records", summary.business_records],
    ["Gaming records", summary.gaming_records],
  ];
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-3 lg:grid-cols-7">
      {cells.map(([label, value]) => (
        <div key={label} className="bg-card px-3 py-3">
          <p className="font-display text-xl">{value}</p>
          <p className="text-[11px] leading-tight text-muted-foreground">{label}</p>
        </div>
      ))}
    </div>
  );
}
