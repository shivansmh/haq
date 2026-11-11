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
};

export type Finding = {
  txn_id: string;
  date: string;
  narration_clean: string;
  debit: number;
  channel: string;
  ref: string | null;
  parse_confidence: number;
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
};

export type PaymentResult = {
  right_id: string;
  deadline: string;
  delay_days: { low: number; high: number };
  amount_paise: { low: number; high: number };
  confidence: string;
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

const mockSweep: SweepResult = {
  status: 'demo', emails_scanned: 1280, noise_filtered: 1248, financial_alerts_found: 32, violations_detected: 3,
  emails: [
    { id: 'demo-1', sender: 'alerts@hdfcbank.net', subject: 'Your account was debited for UPI txn ₹2,000', date: '03 Nov 2026', snippet: '₹2,000 debited via UPI to SWIGGY. UPI Ref 431209845123.', status: 'violation_detected', filterTag: 'UPI debit alert', extractedAmount: 200000, extractedChannel: 'UPI', extractedRef: '431209845123' },
    { id: 'demo-2', sender: 'support@phonepe.com', subject: 'Payment failed at Swiggy', date: '03 Nov 2026', snippet: 'The payment failed at merchant end. The debited amount will be reversed.', status: 'financial_alert', filterTag: 'Merchant failure notice' },
    { id: 'demo-3', sender: 'alerts@hdfcbank.net', subject: 'Reversal credit of ₹2,000 received', date: '09 Nov 2026', snippet: 'Account credited by UPI Reversal / SWIGGY / 431209845123.', status: 'violation_detected', filterTag: 'Late reversal signal', extractedAmount: 200000, extractedChannel: 'UPI', extractedRef: '431209845123' },
    { id: 'demo-4', sender: 'promotions@swiggy.in', subject: '50% off tonight', date: '03 Nov 2026', snippet: 'Use code TASTY50 on orders above ₹299.', status: 'noise', filterTag: 'Marketing filtered' },
    { id: 'demo-5', sender: 'accounts@techbuyer-corp.in', subject: 'Overdue invoice #MSME-2026-441', date: '15 Oct 2026', snippet: 'Invoice ₹1,42,800 remains overdue by 42 days.', status: 'violation_detected', filterTag: 'MSME overdue invoice', extractedAmount: 14280000, extractedChannel: 'MSME', extractedRef: 'MSME-2026-441' },
  ],
  candidates: [
    { txn_id: 'demo-finding-1', date: '2026-11-03', narration_clean: 'UPI / SWIGGY — debit followed by late reversal', debit: 200000, channel: 'UPI', ref: '431209845123', parse_confidence: .99, email_source: { sender: 'alerts@hdfcbank.net', subject: 'Your account was debited for UPI txn ₹2,000', snippet: '₹2,000 debited via UPI to SWIGGY. UPI Ref 431209845123.' } },
    { txn_id: 'demo-finding-2', date: '2026-10-28', narration_clean: 'ATM cash dispense failure — no reversal found', debit: 500000, channel: 'ATM', ref: 'ATM8829103', parse_confidence: .95, email_source: { sender: 'no-reply@sbi.co.in', subject: 'ATM cash dispense incomplete', snippet: 'ATM transaction failed to dispense ₹5,000.' } },
    { txn_id: 'demo-finding-3', date: '2026-09-03', narration_clean: 'MSME invoice #MSME-2026-441 — overdue notice', debit: 14280000, channel: 'MSME', ref: 'MSME-2026-441', parse_confidence: .98, email_source: { sender: 'accounts@techbuyer-corp.in', subject: 'Overdue invoice #MSME-2026-441', snippet: 'Invoice ₹1,42,800 remains overdue by 42 days.' } },
  ],
};

const mockPayment: PaymentResult = { right_id: 'R-001', deadline: '2026-11-04', delay_days: { low: 4, high: 5 }, amount_paise: { low: 40000, high: 50000 }, confidence: 'High', stamp: 'STATUTORY RBI RULE', conflicts: ['C5'], trace: [
  { step: 1, text: 'The debit occurred on 3 November 2026.', clause: 'R-001 trigger' },
  { step: 2, text: 'The reported turnaround window ends on 4 November 2026.', clause: 'RBI TAT circular · R-001 clock' },
  { step: 3, text: 'The reversal arrived on 9 November 2026, making the delay 4 or 5 days.', clause: 'Conflict C5 · reversal-day convention' },
  { step: 4, text: '₹100 per day × 4 or 5 days gives ₹400 to ₹500.', clause: 'RBI compensation schedule' },
] };

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

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
    try { return await request<SweepResult>('/v1/gmail/demo', { method: 'POST' }); } catch {
      const labels = ['Reading the sample inbox', 'Filtering marketing and OTP noise', 'Matching payment references', 'Checking the rights registry'];
      for (let i = 0; i < labels.length; i += 1) { await wait(300); onProgress?.(labels[i], (i + 1) * 25); }
      return mockSweep;
    }
  },
  async liveSweep(onProgress?: (label: string, percent: number) => void): Promise<SweepResult> {
    onProgress?.('Searching connected Gmail messages', 20);
    const result = await request<SweepResult>('/v1/gmail/scan', { method: 'POST', body: JSON.stringify({ max_results: 50 }) });
    onProgress?.('Building a source-backed review', 100);
    return result;
  },
  async computePayment(): Promise<PaymentResult> {
    try { return await request<PaymentResult>('/v1/compute/payment', { method: 'POST', body: JSON.stringify({ right_id: 'R-001', debit_date: '2026-11-03', reversal_date: '2026-11-09', amount_paise: 200000, confirmed: true, channel: 'UPI' }) }); } catch { return mockPayment; }
  },
  async draft(): Promise<ClaimDraft> {
    try { return await request<ClaimDraft>('/v1/claims/draft', { method: 'POST', body: JSON.stringify({ right_id: 'R-001', confirmed_result: { amount_paise: { high: 50000 }, ref: '431209845123' }, claimant_name: 'Your name' }) }); } catch { return { draft: 'Subject: Request to review delayed reversal of a UPI transaction\n\nI am writing to ask you to review the UPI debit of ₹2,000 on 3 November 2026. The transaction was reversed on 9 November 2026. Please review the applicable turnaround-time rule and let me know the outcome.\n\nI am submitting this request myself and have attached the statement extract.', evidence_checklist: ['Statement page showing the debit', 'Transaction reference', 'Proof of the reversal date'], escalation_ladder: ['Start with your bank’s grievance channel', 'Keep the complaint reference', 'Use the RBI Ombudsman route if the bank does not resolve it'] }; }
  },
};

export { mockPayment, mockSweep };
