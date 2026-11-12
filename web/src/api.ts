export type SweepEmail = {
  id: string;
  sender: string;
  subject: string;
  date: string;
  snippet: string;
  status: 'noise' | 'financial_alert' | 'violation_detected';
  filterTag: string;
  extractedAmount?: number;
  extractedChannel?: string;
  extractedRef?: string;
  signalKind?: string;
  signalReasons?: string[];
  llm_assistance?: {
    status: 'disabled' | 'unavailable' | 'timeout' | 'invalid_output' | 'ok';
    relevance?: string;
    signal_type?: string;
    evidence_summary?: string;
    needs_review?: boolean;
    review_reasons?: string[];
    suggestions?: Record<string, { value: string | number; source_quote: string; trust_tier: 'T-B' }>;
    conflicts?: Array<{ field: string; deterministic_value: string | number; llm_value: string | number; status: 'conflict'; action: 'ask_user' }>;
    trust_tier?: 'T-B';
  };
};

export type Finding = {
  txn_id: string;
  date: string | null;
  reversal_date?: string | null;
  narration_clean: string;
  debit: number;
  channel: string;
  ref: string | null;
  parse_confidence: number;
  evidence_status?: string;
  reversal_seen?: boolean;
  related_sources?: Array<{ sender: string; subject: string; snippet: string }>;
  email_source?: { sender: string; subject: string; snippet: string };
};

export type SweepResult = {
  status: string;
  emails_scanned: number;
  noise_filtered: number;
  financial_alerts_found: number;
  violations_detected: number;
  emails: SweepEmail[];
  candidates: Finding[];
  llm_status?: 'disabled' | 'unavailable' | 'timeout' | 'invalid_output' | 'ok';
  ai_assisted_count?: number;
  coverage?: { listed: number; triaged: number; analysed: number; relevant: number; not_analysed: number };
  cases?: Case[];
  claim_packs?: ClaimPack[];
};

export type Case = {
  case_id: string;
  claim_type: string;
  rule_id: string | null;
  rule_status: string;
  events: Array<{ event_id: string; event_type: string; amount_paise?: number | null; reference?: string | null; event_date?: string | null; quote: string }>;
  amount_paise?: number | null;
  reference?: string | null;
  deadline?: string | null;
  resolved_on?: string | null;
  days_overdue?: number | null;
  status: 'open' | 'resolved_on_time' | 'resolved_late' | 'unresolved_past_deadline';
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
  days_overdue: number | null;
};

export type SweepJob = {
  job_id: string;
  state: string;
  listed: number;
  triaged: number;
  analysed: number;
  relevant: number;
  not_analysed: number;
  stage?: string;
  truncated?: boolean;
  elapsed_seconds: number;
  result?: SweepResult;
  error?: string | null;
};

export type PaymentResult = {
  right_id: string;
  deadline: string;
  delay_days: { low: number; high: number };
  amount_paise: { low: number; high: number };
  confidence: string;
  illustrative?: boolean;
  evidence_status?: string;
  statutory_rate_desc?: string;
  stamp?: string;
  conflicts: string[];
  trace: Array<{ step: number; text: string; clause: string; inputs?: Record<string, string | number> }>;
};

export type TraceStep = PaymentResult['trace'][number];

export type ClaimDraft = {
  draft: string;
  evidence_checklist: string[];
  escalation_ladder: string[];
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');


async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { ...init, credentials: 'include', headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.message || `Request failed: ${response.status}`);
  return response.json();
}

export const api = {
  baseUrl: API_BASE,
  async authUrl() { return request<{ auth_url: string; client_id_configured: boolean }>('/v1/gmail/auth-url'); },
  async status() { return request<{ connected: boolean }>('/v1/gmail/status'); },
  async disconnect() { return request<{ disconnected: boolean }>('/v1/gmail/disconnect', { method: 'POST' }); },
  async demoSweep(onProgress?: (label: string, percent: number) => void): Promise<SweepResult> {
    onProgress?.('Reading the sample inbox', 20);
    const result = await request<SweepResult>('/v1/gmail/demo', { method: 'POST' });
    onProgress?.('Building a source-backed review', 100);
    return result;
  },
  async liveSweep(onProgress?: (label: string, percent: number) => void, onJob?: (jobId: string) => void): Promise<SweepResult> {
    onProgress?.('Starting a background Gmail sweep', 5);
    const started = await request<SweepJob>('/v1/gmail/sweeps', { method: 'POST', body: JSON.stringify({ max_results: 500 }) });
    onJob?.(started.job_id);
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 350));
      const job = await request<SweepJob>(`/v1/gmail/sweeps/${started.job_id}`);
      const percent = Math.min(95, job.listed ? Math.round((job.analysed / job.listed) * 90) + 5 : 10);
      onProgress?.(`${job.stage || 'Scanning'} · ${job.listed} found · ${job.triaged} headers read · ${job.analysed} resolved`, percent);
      if (job.state === 'done' && job.result) {
        onProgress?.('Building a source-backed review', 100);
        return { ...job.result, coverage: { listed: job.listed, triaged: job.triaged, analysed: job.analysed, relevant: job.relevant, not_analysed: job.not_analysed } };
      }
      if (['failed', 'expired', 'cancelled'].includes(job.state)) throw new Error(job.error || `Sweep ${job.state}`);
    }
  },
  async cancelSweep(jobId: string): Promise<SweepJob> {
    return request<SweepJob>(`/v1/gmail/sweeps/${jobId}`, { method: 'DELETE' });
  },
  async computePayment(finding: Finding, mode: 'demo' | 'live' = 'live'): Promise<PaymentResult> {
    if (!finding.date || !finding.debit) throw new Error('This finding does not contain enough dated amount evidence to calculate yet.');
    return request<PaymentResult>('/v1/compute/payment', { method: 'POST', body: JSON.stringify({
      right_id: finding.channel === 'MSME' ? 'R-007' : 'R-001',
      debit_date: finding.date,
      reversal_date: finding.reversal_date || null,
      amount_paise: finding.debit,
      confirmed: true,
      channel: finding.channel,
      mode,
    }) });
  },
  async draft(finding: Finding, result: PaymentResult): Promise<ClaimDraft> {
    return request<ClaimDraft>('/v1/claims/draft', { method: 'POST', body: JSON.stringify({
      right_id: finding.channel === 'MSME' ? 'R-007' : 'R-001',
      confirmed_result: { ...result, ref: finding.ref, date: finding.date, reversal_date: finding.reversal_date },
      claimant_name: 'Your name',
    }) });
  },
};
