export type Step = 'home' | 'upload' | 'review' | 'candidates' | 'result' | 'claim' | 'msme' | 'unclaimed' | 'sources';

export type Transaction = {
  txn_id: string;
  date: string;
  narration_raw: string;
  narration_clean: string;
  debit: number;
  credit: number;
  balance: number;
  channel: string;
  ref: string | null;
  parse_confidence: number;
};

export type TraceStep = { step: number; text: string; clause: string; inputs: Record<string, string | number> };

export type PaymentResult = {
  right_id: string;
  mode: 'demo' | 'live';
  stamp?: string;
  deadline: string;
  delay_days: { low: number; high: number };
  amount_paise: { low: number; high: number };
  unresolved: string[];
  conflicts: string[];
  confidence: 'High' | 'Medium' | 'Low';
  trace: TraceStep[];
};

export type RegistryItem = { id: string; name: string; status: 'Seeded' | 'Verified' | 'Parked' | 'Rejected'; confidence: 'High' | 'Medium' | 'Low' };

const mockTransactions: Transaction[] = [
  { txn_id: 'demo-001', date: '2026-11-03', narration_raw: 'UPI/123456789012/SHOP MART', narration_clean: 'UPI / SHOP MART', debit: 200000, credit: 0, balance: 1842000, channel: 'UPI', ref: '123456789012', parse_confidence: 0.99 },
  { txn_id: 'demo-002', date: '2026-11-05', narration_raw: 'UPI/123456789012/REVERSAL', narration_clean: 'UPI / REVERSAL', debit: 0, credit: 200000, balance: 2042000, channel: 'UPI', ref: '123456789012', parse_confidence: 0.96 },
  { txn_id: 'demo-003', date: '2026-11-08', narration_raw: 'ATM CASH WDL / 445566778899', narration_clean: 'ATM CASH WDL', debit: 500000, credit: 0, balance: 1542000, channel: 'ATM', ref: null, parse_confidence: 0.62 },
];

const mockResult: PaymentResult = {
  right_id: 'R-001', mode: 'demo', stamp: 'UNVERIFIED RULE', deadline: '2026-11-04',
  delay_days: { low: 4, high: 5 }, amount_paise: { low: 40000, high: 50000 },
  unresolved: ['reversal_day_counts'], conflicts: ['C5'], confidence: 'Low',
  trace: [
    { step: 1, text: 'The reported rule uses T+1 from the debit date.', clause: 'RBI DPSS circular, clause to be confirmed', inputs: { debit_date: '2026-11-03' } },
    { step: 2, text: 'The deadline is 4 November 2026.', clause: 'R-001 clock', inputs: { offset: 1, deadline: '2026-11-04' } },
    { step: 3, text: 'The reversal arrived on 9 November, so the delay is 4 or 5 days depending on whether that day counts.', clause: 'Conflict C5', inputs: { reversal_date: '2026-11-09' } },
    { step: 4, text: '₹100 per day × 4 or 5 days gives ₹400 to ₹500.', clause: 'R-001 amount formula', inputs: { daily_rate_paise: 10000 } },
  ],
};

export const mockRegistry: RegistryItem[] = [
  { id: 'R-001', name: 'UPI transfer debited, beneficiary not credited', status: 'Seeded', confidence: 'Low' },
  { id: 'R-002', name: 'UPI merchant payment debited, no confirmation', status: 'Seeded', confidence: 'Low' },
  { id: 'R-003', name: 'ATM debit, cash not dispensed', status: 'Seeded', confidence: 'Low' },
  { id: 'R-007', name: 'Payment due to a micro or small supplier', status: 'Seeded', confidence: 'Medium' },
  { id: 'R-011', name: 'Unclaimed bank deposits', status: 'Seeded', confidence: 'Medium' },
];

const wait = (ms = 180) => new Promise((resolve) => setTimeout(resolve, ms));

export const api = {
  async ingest(): Promise<{ transactions: Transaction[]; parse_report: { accepted: boolean; rows: number } }> {
    if (import.meta.env.VITE_API_MODE === 'real') {
      const response = await fetch('/v1/ingest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: 'demo statement' }) });
      return response.json();
    }
    await wait();
    return { transactions: mockTransactions, parse_report: { accepted: true, rows: mockTransactions.length } };
  },
  async detect(): Promise<{ candidates: Transaction[] }> {
    await wait();
    return { candidates: [mockTransactions[0], mockTransactions[2]] };
  },
  async computePayment(): Promise<PaymentResult> {
    if (import.meta.env.VITE_API_MODE === 'real') {
      const response = await fetch('/v1/compute/payment', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ right_id: 'R-001', debit_date: '2026-11-03', reversal_date: '2026-11-09', amount_paise: 200000, confirmed: true }) });
      return response.json();
    }
    await wait(220);
    return mockResult;
  },
  async draft(): Promise<{ draft: string; evidence_checklist: string[]; escalation_ladder: string[] }> {
    await wait();
    return {
      draft: 'Subject: Request to review delayed reversal of a UPI transaction\n\nI am writing to ask you to review the UPI debit of ₹2,000 on 3 November 2026. The transaction was reversed on 9 November 2026. Please review the applicable turnaround-time rule and let me know the outcome.\n\nI am submitting this request myself and have attached the statement extract.',
      evidence_checklist: ['Statement page showing the debit', 'Alert or transaction reference', 'Proof of the reversal date', 'Your bank complaint acknowledgement, if any'],
      escalation_ladder: ['Start with your bank’s grievance channel', 'Keep the complaint reference', 'Use the RBI Ombudsman route if the bank does not resolve it'],
    };
  },
};
