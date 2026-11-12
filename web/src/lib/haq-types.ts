export type SweepEmail = {
  id: string;
  sender: string;
  subject: string;
  date: string;
  snippet: string;
  status: "noise" | "financial_alert" | "violation_detected";
  filterTag: string;
  extractedAmount?: number;
  extractedChannel?: string;
  signalReasons?: string[];
  record_id?: string | null;
  cluster_size?: number;
  duplicate_of?: string | null;
  structured?: EmailFlag;
};

export type CaseEvent = {
  event_id: string;
  event_type: string;
  amount_paise?: number | null;
  reference?: string | null;
  event_date?: string | null;
  quote: string;
  sender?: string;
  subject?: string;
};

export type Case = {
  case_id: string;
  claim_type: string;
  rule_id: string | null;
  rule_status: string;
  events: CaseEvent[];
  amount_paise?: number | null;
  reference?: string | null;
  deadline?: string | null;
  days_overdue?: number | null;
  status: "open" | "resolved_on_time" | "resolved_late" | "unresolved_past_deadline";
};

export type ClaimPack = {
  case_id: string;
  claim_type: string;
  draft: string;
  evidence_checklist: string[];
  escalation: string[];
  rule_id: string | null;
  rule_status: string;
  deadline: string | null;
};

/* ------------------------------------------------------------------ ledger */

export type RecordStatus = "action_needed" | "tracking" | "resolved" | "reference_only";
export type Segment = "consumer" | "business";
export type Vertical =
  | "gaming"
  | "ecommerce"
  | "food_delivery"
  | "travel"
  | "utilities"
  | "business"
  | "finance"
  | "other";

export type EvidenceRole =
  | "debit"
  | "failure"
  | "refund"
  | "payment"
  | "cancellation"
  | "atm_failure"
  | "invoice"
  | "duplicate"
  | "other";

export type Money = { value_paise: number | null; currency: "INR"; display: string };

export type Resolution = {
  kind: "refund" | "reversal" | "cash" | "payment" | "none";
  received: boolean;
  received_on: string | null;
  days_to_resolution: number | null;
  evidence_email_ids: string[];
  label: string;
};

export type LegalAssessment = {
  rule_id: string | null;
  rule_status: string;
  rule_verified: boolean;
  stamp: "VERIFIED RULE" | "UNVERIFIED RULE" | "NO RULE";
  statutory_days: number | null;
  deadline_date: string | null;
  indicative_deadline_date: string | null;
  days_overdue: number | null;
  compliance:
    | "on_time"
    | "late"
    | "received_rule_unverified"
    | "not_due_yet"
    | "not_received_past_deadline"
    | "not_received_rule_unverified"
    | "unknown";
  compliance_label: string;
  compensation: {
    computed: boolean;
    amount_paise: number | null;
    indicative_paise: number | null;
    daily_rate_paise: number | null;
    note: string;
  };
  citation: string | null;
  note: string;
};

export type EvidenceEmail = {
  email_id: string;
  role: EvidenceRole;
  duplicate: boolean;
  duplicate_of: string | null;
  date: string | null;
  sender: string;
  subject: string;
  quote: string;
  amount_paise: number | null;
  reference: string | null;
};

export type TimelineItem = {
  date: string | null;
  event: string;
  email_id: string;
  amount_paise: number | null;
};

export type AiEnrichment = {
  status: string;
  model: string | null;
  summary: string | null;
  merchant: string | null;
  vertical: Vertical | null;
  segment: Segment | null;
  labels: string[];
  conflicts: string[];
  needs_review: boolean;
};

export type FlaggedRecord = {
  schema_version: "haq.flag.v1";
  record_id: string;
  identity_keys: string[];
  case_id: string;
  title: string;
  claim_type: string;
  category_label: string;
  segment: Segment;
  vertical: Vertical;
  status: RecordStatus;
  status_label: string;
  amount: Money;
  transaction: {
    reference: string | null;
    channel: string;
    merchant: string | null;
    origin_date: string | null;
    origin_email_id: string | null;
  };
  resolution: Resolution;
  legal: LegalAssessment;
  labels: string[];
  risk_flags: string[];
  evidence: EvidenceEmail[];
  timeline: TimelineItem[];
  recommended_actions: string[];
  ai: AiEnrichment;
  tracking: { first_seen_at: string; last_seen_at: string; sweep_count: number };
  needs_review: boolean;
  safety_note: string;
};

export type EmailFlag = {
  schema_version: "haq.email.v1";
  email_id: string;
  record_id: string;
  role: EvidenceRole;
  duplicate: boolean;
  duplicate_of: string | null;
  cluster_size: number;
  sender: string;
  subject: string;
  date: string | null;
  amount_paise: number | null;
  reference: string | null;
  segment: Segment;
  vertical: Vertical;
  labels: string[];
  needs_review: boolean;
};

export type LedgerSummary = {
  total_records: number;
  total_amount_paise: number;
  refunds_received: number;
  refunds_pending: number;
  refunds_late: number;
  action_needed: number;
  business_records: number;
  gaming_records: number;
};

export type Ledger = {
  schema_version: "haq.ledger.v1";
  records: FlaggedRecord[];
  summary: LedgerSummary;
  ai_status?: string;
  updated_at?: number | null;
};

export type SweepResult = {
  status: string;
  emails_scanned: number;
  noise_filtered: number;
  financial_alerts_found: number;
  violations_detected: number;
  emails: SweepEmail[];
  cases?: Case[];
  claim_packs?: ClaimPack[] | null;
  flagged_records?: FlaggedRecord[];
  ledger?: Ledger;
  ledger_ai_status?: string;
  coverage?: {
    listed: number;
    triaged: number;
    analysed: number;
    relevant: number;
    not_analysed: number;
  };
};

export const API_BASE = (
  import.meta.env["VITE_API_BASE_URL"] || "https://haq-api-u3pz.onrender.com"
).replace(/\/$/, "");

export const inr = (paise?: number | null) =>
  paise == null
    ? "—"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      }).format(paise / 100);

export const CLAIM_LABELS: Record<string, string> = {
  atm_cash_not_dispensed: "ATM cash not dispensed",
  msme_invoice_overdue: "Overdue MSME invoice",
  upi_failed_debited: "Failed UPI, money debited",
};
export const claimLabel = (t: string) =>
  CLAIM_LABELS[t] ?? t.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export const STATUS_LABELS: Record<Case["status"], string> = {
  open: "Open",
  resolved_on_time: "Resolved on time",
  resolved_late: "Resolved late",
  unresolved_past_deadline: "Past deadline",
};

export const RECORD_STATUS_LABELS: Record<RecordStatus, string> = {
  action_needed: "Action needed",
  tracking: "Tracking",
  resolved: "Refund received",
  reference_only: "Evidence saved",
};

export const VERTICAL_LABELS: Record<Vertical, string> = {
  gaming: "Gaming",
  ecommerce: "Shopping",
  food_delivery: "Food delivery",
  travel: "Travel",
  utilities: "Utilities",
  business: "Business",
  finance: "Banking",
  other: "Other",
};

export const SEGMENT_LABELS: Record<Segment, string> = {
  consumer: "Consumer",
  business: "Business",
};

/** Records tracked across sweeps, falling back to this sweep's own list. */
export const ledgerRecords = (result?: SweepResult | null): FlaggedRecord[] =>
  result?.ledger?.records ?? result?.flagged_records ?? [];

export const ledgerSummary = (result?: SweepResult | null): LedgerSummary =>
  result?.ledger?.summary ?? {
    total_records: ledgerRecords(result).length,
    total_amount_paise: ledgerRecords(result).reduce(
      (sum, r) => sum + (r.amount.value_paise ?? 0),
      0,
    ),
    refunds_received: ledgerRecords(result).filter((r) => r.resolution.received).length,
    refunds_pending: ledgerRecords(result).filter((r) => !r.resolution.received).length,
    refunds_late: ledgerRecords(result).filter((r) => r.legal.compliance === "late").length,
    action_needed: ledgerRecords(result).filter((r) => r.status === "action_needed").length,
    business_records: ledgerRecords(result).filter((r) => r.segment === "business").length,
    gaming_records: ledgerRecords(result).filter((r) => r.vertical === "gaming").length,
  };

export const recordAmount = (record: FlaggedRecord): number => record.amount.value_paise ?? 0;

export const recordsForCase = (
  result: SweepResult | null | undefined,
  caseId: string,
): FlaggedRecord | undefined => ledgerRecords(result).find((record) => record.case_id === caseId);

/** Cases that may still be worth claiming (not already resolved on time). */
export const claimableCases = (cases: Case[] = []) =>
  cases.filter((c) => c.status !== "resolved_on_time");
export const claimableTotal = (cases: Case[] = []) =>
  claimableCases(cases).reduce((sum, c) => sum + (c.amount_paise ?? 0), 0);
