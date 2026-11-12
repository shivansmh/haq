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
};

export type CaseEvent = { event_id: string; event_type: string; amount_paise?: number | null; reference?: string | null; event_date?: string | null; quote: string; sender?: string; subject?: string };

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

export type SweepResult = {
  status: string;
  emails_scanned: number;
  noise_filtered: number;
  financial_alerts_found: number;
  violations_detected: number;
  emails: SweepEmail[];
  cases?: Case[];
  claim_packs?: ClaimPack[] | null;
  coverage?: { listed: number; triaged: number; analysed: number; relevant: number; not_analysed: number };
};

export const API_BASE = (import.meta.env["VITE_API_BASE_URL"] || "https://haq-api-u3pz.onrender.com").replace(/\/$/, "");

export const inr = (paise?: number | null) =>
  paise == null ? "—" : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);

export const CLAIM_LABELS: Record<string, string> = {
  atm_cash_not_dispensed: "ATM cash not dispensed",
  msme_invoice_overdue: "Overdue MSME invoice",
  upi_failed_debited: "Failed UPI, money debited",
};
export const claimLabel = (t: string) => CLAIM_LABELS[t] ?? t.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export const STATUS_LABELS: Record<Case["status"], string> = {
  open: "Open",
  resolved_on_time: "Resolved on time",
  resolved_late: "Resolved late",
  unresolved_past_deadline: "Past deadline",
};

/** Cases that may still be worth claiming (not already resolved on time). */
export const claimableCases = (cases: Case[] = []) => cases.filter((c) => c.status !== "resolved_on_time");
export const claimableTotal = (cases: Case[] = []) => claimableCases(cases).reduce((sum, c) => sum + (c.amount_paise ?? 0), 0);
