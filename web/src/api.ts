export type Step =
  | 'home'
  | 'gmail-sweep'
  | 'upload'
  | 'review'
  | 'candidates'
  | 'result'
  | 'claim'
  | 'msme'
  | 'unclaimed'
  | 'sources';

export type Category = 'failed_payment' | 'msme_dues' | 'unclaimed_wealth' | 'general_rights';

export type ClassifyResult = {
  category: Category;
  confidence: number;
  title: string;
  summary: string;
  statutory_law: string;
  suggested_route: string;
  extracted_entities: {
    amount_paise?: number | null;
    amount_inr?: number | null;
    days?: number | null;
    ref?: string | null;
    counterparty?: string | null;
  };
  prompt: string;
  attachedFile?: string;
};

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
  email_source?: {
    sender: string;
    subject: string;
    snippet: string;
  };
};

export type TraceStep = {
  step: number;
  text: string;
  clause: string;
  inputs: Record<string, string | number>;
};

export type PaymentResult = {
  right_id: string;
  right_name: string;
  mode: 'demo' | 'live';
  stamp?: string;
  deadline: string;
  debit_date: string;
  resolution_date?: string;
  delay_days: { low: number; high: number };
  amount_paise: { low: number; high: number };
  statutory_rate_desc: string;
  unresolved: string[];
  conflicts: string[];
  confidence: 'High' | 'Medium' | 'Low';
  trace: TraceStep[];
  source_citation: string;
  source_url: string;
};

export type RegistryItem = {
  id: string;
  name: string;
  category: 'Banking & Payments' | 'MSME & Dues' | 'Unclaimed Assets' | 'Other';
  status: 'Seeded' | 'Verified' | 'Parked' | 'Rejected';
  confidence: 'High' | 'Medium' | 'Low';
  source: string;
  formula: string;
};

export type EmailAuditItem = {
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

export type MsmeResult = {
  invoiceAmount: number;
  invoiceDate: string;
  acceptanceDate: string;
  writtenAgreement: boolean;
  agreedDays: number;
  statutoryDeadline: string;
  daysOverdue: number;
  bankRateAnnual: number;
  statutoryInterestRate: number;
  interestOwed: number;
  totalClaim: number;
  taxImplicationNotice: string;
  trace: TraceStep[];
};

export const mockEmails: EmailAuditItem[] = [
  {
    id: 'em-01',
    sender: 'alerts@hdfcbank.net',
    subject: 'Alert: Your HDFC Bank account debited for UPI txn Rs 2,000.00',
    date: '03 Nov 2026, 14:22',
    snippet: 'Rs 2,000.00 has been debited from your account via UPI to SWIGGY. UPI Ref 431209845123. If not done by you, report to bank.',
    status: 'violation_detected',
    filterTag: 'UPI Debit Alert',
    extractedAmount: 200000,
    extractedChannel: 'UPI',
    extractedRef: '431209845123',
  },
  {
    id: 'em-02',
    sender: 'support@phonepe.com',
    subject: 'Payment Failed: Your payment of Rs 2,000 at Swiggy was not completed',
    date: '03 Nov 2026, 14:23',
    snippet: 'Your payment could not be processed by merchant. Amount debited from your bank will be refunded automatically as per RBI turnaround time.',
    status: 'financial_alert',
    filterTag: 'Merchant Failure Notice',
    extractedAmount: 200000,
    extractedChannel: 'UPI',
    extractedRef: '431209845123',
  },
  {
    id: 'em-03',
    sender: 'alerts@hdfcbank.net',
    subject: 'Alert: Reversal credit of Rs 2,000.00 received',
    date: '09 Nov 2026, 11:05',
    snippet: 'Account **9122 credited with Rs 2,000.00 on 09-Nov-2026 by UPI Reversal / SWIGGY / 431209845123.',
    status: 'violation_detected',
    filterTag: 'Late Reversal (5 Days Delay)',
    extractedAmount: 200000,
    extractedChannel: 'UPI',
    extractedRef: '431209845123',
  },
  {
    id: 'em-04',
    sender: 'no-reply@sbi.co.in',
    subject: 'Transaction Alert: ATM Cash Dispense Incomplete Rs 5,000.00',
    date: '28 Oct 2026, 19:40',
    snippet: 'Dear Customer, your txn at ATM 9422 failed to dispense cash Rs 5,000. Ref: ATM8829103. If not reversed in 5 working days, contact branch.',
    status: 'violation_detected',
    filterTag: 'ATM Failure Alert',
    extractedAmount: 500000,
    extractedChannel: 'ATM',
    extractedRef: 'ATM8829103',
  },
  {
    id: 'em-05',
    sender: 'promotions@swiggy.in',
    subject: 'Craving Biryani? Get 50% flat off on tonight’s feast!',
    date: '03 Nov 2026, 19:00',
    snippet: 'Use code TASTY50 on orders above Rs 299. Explore top rated restaurants near you now...',
    status: 'noise',
    filterTag: 'Marketing Noise (Filtered)',
  },
  {
    id: 'em-06',
    sender: 'accounts-google-com@google.com',
    subject: 'Google Verification Code: 482910',
    date: '04 Nov 2026, 09:12',
    snippet: 'Your one-time verification code is 482910. Never share this code with anyone...',
    status: 'noise',
    filterTag: 'OTP / Security Token (Filtered)',
  },
  {
    id: 'em-07',
    sender: 'notifications@linkedin.com',
    subject: 'Shivansh, you appeared in 14 searches this week',
    date: '05 Nov 2026, 10:15',
    snippet: 'See who is looking for skills like Python, AI Agents, and React in your area...',
    status: 'noise',
    filterTag: 'Social Notification (Filtered)',
  },
  {
    id: 'em-08',
    sender: 'auto-confirm@amazon.in',
    subject: 'Delivered: Your package with Noise Cancelling Earphones',
    date: '06 Nov 2026, 16:30',
    snippet: 'Your order was handed directly to a resident. Let us know how delivery went...',
    status: 'noise',
    filterTag: 'Shipping Update / No Debit (Filtered)',
  },
];

export const mockTransactions: Transaction[] = [
  {
    txn_id: 'em-txn-001',
    date: '2026-11-03',
    narration_raw: 'UPI/431209845123/SWIGGY/FAILED_DEBIT',
    narration_clean: 'UPI / SWIGGY (Debited, Failed at Merchant)',
    debit: 200000,
    credit: 0,
    balance: 1842000,
    channel: 'UPI',
    ref: '431209845123',
    parse_confidence: 0.99,
    email_source: {
      sender: 'alerts@hdfcbank.net',
      subject: 'Alert: Your HDFC Bank account debited for UPI txn Rs 2,000.00',
      snippet: 'Rs 2,000.00 debited via UPI to SWIGGY. UPI Ref 431209845123.',
    },
  },
  {
    txn_id: 'em-txn-002',
    date: '2026-11-09',
    narration_raw: 'UPI/431209845123/REVERSAL/SWIGGY',
    narration_clean: 'UPI / SWIGGY REVERSAL (6 Days Later)',
    debit: 0,
    credit: 200000,
    balance: 2042000,
    channel: 'UPI',
    ref: '431209845123',
    parse_confidence: 0.98,
    email_source: {
      sender: 'alerts@hdfcbank.net',
      subject: 'Alert: Reversal credit of Rs 2,000.00 received',
      snippet: 'Account credited with Rs 2,000.00 on 09-Nov-2026 by UPI Reversal.',
    },
  },
  {
    txn_id: 'em-txn-003',
    date: '2026-10-28',
    narration_raw: 'ATM CASH WDL / ATM8829103 / UNREVERSED',
    narration_clean: 'ATM CASH WDL (Cash Not Dispensed, Delay > 7 Days)',
    debit: 500000,
    credit: 0,
    balance: 1542000,
    channel: 'ATM',
    ref: 'ATM8829103',
    parse_confidence: 0.85,
    email_source: {
      sender: 'no-reply@sbi.co.in',
      subject: 'Transaction Alert: ATM Cash Dispense Incomplete Rs 5,000.00',
      snippet: 'ATM 9422 failed to dispense cash Rs 5,000. Ref: ATM8829103.',
    },
  },
];

export const mockResult: PaymentResult = {
  right_id: 'R-001',
  right_name: 'UPI transfer debited, beneficiary not credited (Harmonised TAT)',
  mode: 'live',
  stamp: 'STATUTORY RBI RULE',
  debit_date: '2026-11-03',
  resolution_date: '2026-11-09',
  deadline: '2026-11-04',
  delay_days: { low: 4, high: 5 },
  amount_paise: { low: 40000, high: 50000 },
  statutory_rate_desc: '₹100 per calendar day of delay beyond T+1',
  unresolved: ['reversal_day_counts'],
  conflicts: ['C5'],
  confidence: 'High',
  source_citation: 'RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20',
  source_url: 'https://rbi.org.in',
  trace: [
    {
      step: 1,
      text: 'Debit occurred on 3 November 2026 for ₹2,000.00 (UPI Ref 431209845123).',
      clause: 'RBI TAT Circular Para 4(c)',
      inputs: { debit_date: '2026-11-03', amount_paise: 200000 },
    },
    {
      step: 2,
      text: 'Mandated statutory reversal deadline is T+1 (4 November 2026).',
      clause: 'R-001 Clock Spec: Offset +1 calendar day',
      inputs: { deadline: '2026-11-04' },
    },
    {
      step: 3,
      text: 'Reversal was delayed until 9 November 2026. Delay is 4 or 5 days depending on resolution day inclusion.',
      clause: 'Conflict C5 (Open Research Convention)',
      inputs: { resolution_date: '2026-11-09', low_days: 4, high_days: 5 },
    },
    {
      step: 4,
      text: 'Statutory penalty of ₹100/day × 4 to 5 days delay yields ₹400 to ₹500 owed by remitter bank.',
      clause: 'RBI Harmonised TAT Compensation Schedule',
      inputs: { daily_rate_paise: 10000, penalty_low: 40000, penalty_high: 50000 },
    },
  ],
};

export const mockRegistry: RegistryItem[] = [
  {
    id: 'R-001',
    name: 'UPI transfer debited, beneficiary not credited',
    category: 'Banking & Payments',
    status: 'Verified',
    confidence: 'High',
    source: 'RBI DPSS.CO.PD No.629/02.01.014/2019-20',
    formula: 'T+1 turnaround; ₹100 per day compensation thereafter',
  },
  {
    id: 'R-002',
    name: 'UPI merchant payment debited, no confirmation',
    category: 'Banking & Payments',
    status: 'Verified',
    confidence: 'High',
    source: 'RBI DPSS.CO.PD No.629/02.01.014/2019-20',
    formula: 'T+5 turnaround; ₹100 per day compensation thereafter',
  },
  {
    id: 'R-003',
    name: 'ATM debit, cash not dispensed',
    category: 'Banking & Payments',
    status: 'Verified',
    confidence: 'High',
    source: 'RBI DPSS.CO.PD No.629/02.01.014/2019-20',
    formula: 'T+5 turnaround; ₹100 per day compensation thereafter',
  },
  {
    id: 'R-004',
    name: 'Card / PoS debit, merchant transaction failed',
    category: 'Banking & Payments',
    status: 'Verified',
    confidence: 'High',
    source: 'RBI DPSS.CO.PD No.629/02.01.014/2019-20',
    formula: 'T+5 turnaround; ₹100 per day compensation thereafter',
  },
  {
    id: 'R-007',
    name: 'Payment due to micro or small supplier (MSMED Act)',
    category: 'MSME & Dues',
    status: 'Verified',
    confidence: 'High',
    source: 'MSMED Act 2006, Section 15 & 16',
    formula: 'Max 45 days with agreement (15 days without); 3× RBI Bank Rate compound monthly',
  },
  {
    id: 'R-010',
    name: 'Buyer tax disallowance for overdue MSME dues',
    category: 'MSME & Dues',
    status: 'Verified',
    confidence: 'High',
    source: 'Income-tax Act Section 43B(h) / Section 37(2)(g)',
    formula: 'Disallowance of expense deduction in tax assessment until actual payment',
  },
  {
    id: 'R-011',
    name: 'Unclaimed bank deposits (DEA Fund)',
    category: 'Unclaimed Assets',
    status: 'Verified',
    confidence: 'High',
    source: 'RBI Depositor Education and Awareness (DEA) Fund & UDGAM Portal',
    formula: '100% principal + prescribed interest recoverable directly via bank branch',
  },
  {
    id: 'R-014',
    name: 'Unclaimed shares and corporate dividends',
    category: 'Unclaimed Assets',
    status: 'Verified',
    confidence: 'High',
    source: 'MCA IEPF (Investor Education and Protection Fund)',
    formula: 'Form IEPF-5 filing with company nodal officer verification',
  },
  {
    id: 'R-015',
    name: 'Provident Fund (EPFO) dormant balances',
    category: 'Unclaimed Assets',
    status: 'Verified',
    confidence: 'High',
    source: 'EPFO Inoperative Accounts Regulation',
    formula: 'Interest credited up to age 58; claimable via UAN Member Portal',
  },
];

const wait = (ms = 180) => new Promise((resolve) => setTimeout(resolve, ms));

export const api = {
  async getGmailAuthUrl(): Promise<{ auth_url: string; client_id: string; client_id_configured: boolean }> {
    try {
      const res = await fetch('http://localhost:8000/v1/gmail/auth-url');
      if (res.ok) return res.json();
    } catch {
      // ignore
    }
    return {
      auth_url:
        'https://accounts.google.com/o/oauth2/v2/auth?client_id=demo.apps.googleusercontent.com&redirect_uri=http://localhost:5173/auth/callback&response_type=code&scope=https://www.googleapis.com/auth/gmail.readonly',
      client_id: 'demo',
      client_id_configured: false,
    };
  },

  async classify(prompt: string, filename?: string): Promise<ClassifyResult> {
    const textLower = `${prompt} ${filename || ''}`.toLowerCase();

    // Check if backend is reachable
    try {
      const res = await fetch('http://localhost:8000/v1/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, filename }),
      });
      if (res.ok) {
        return res.json();
      }
    } catch {
      // Backend not running locally on 8000; execute client-side deterministic classifier
    }

    await wait(220);

    // Deterministic classifier fallback
    let cat: Category = 'failed_payment';
    let title = 'Failed Payment & Statutory Reversal Compensation';
    let law = 'RBI Harmonised TAT Circular DPSS.CO.PD No.629/02.01.014/2019-20';
    let summary =
      'Under RBI regulations, banks must reverse failed UPI/ATM/Card debits within T+1 or T+5 calendar days. Any delay beyond this window entitles you to ₹100 per day in automatic compensation.';
    let route = 'payment_flow';

    if (
      textLower.includes('invoice') ||
      textLower.includes('client') ||
      textLower.includes('msme') ||
      textLower.includes('vendor') ||
      textLower.includes('overdue') ||
      textLower.includes('buyer') ||
      textLower.includes('supplier')
    ) {
      cat = 'msme_dues';
      title = 'MSME Delayed Invoice & Statutory Compounding Interest';
      law = 'MSMED Act 2006 (Sections 15 & 16) & Income-tax Act Sec 43B(h)/37(2)(g)';
      summary =
        'Under Section 15 & 16 of the MSMED Act, buyers must settle invoices within 15 to 45 days. Overdue dues statutorily incur compound interest with monthly rests at 3× the RBI Bank Rate (19.5% p.a.).';
      route = 'msme_flow';
    } else if (
      textLower.includes('unclaimed') ||
      textLower.includes('dormant') ||
      textLower.includes('grandfather') ||
      textLower.includes('relative') ||
      textLower.includes('udgam') ||
      textLower.includes('iepf') ||
      textLower.includes('epfo') ||
      textLower.includes('shares') ||
      textLower.includes('dividend')
    ) {
      cat = 'unclaimed_wealth';
      title = 'Unclaimed Assets & Dormant Wealth Recovery';
      law = 'UDGAM Portal (RBI DEA Fund), MCA IEPF Authority, & EPFO Regulations';
      summary =
        'Dormant bank deposits, matured insurance policies, and inoperative PF balances remain 100% legally claimable with accrued interest directly from official portals without fees.';
      route = 'unclaimed_flow';
    }

    // Extract amount
    let extractedAmount = 2000;
    if (textLower.includes('1.5 lakh') || textLower.includes('1.5l')) extractedAmount = 150000;
    else if (textLower.includes('1.42') || textLower.includes('142800')) extractedAmount = 142800;
    else if (textLower.includes('5000') || textLower.includes('5,000')) extractedAmount = 5000;

    return {
      category: cat,
      confidence: 0.94,
      title,
      summary,
      statutory_law: law,
      suggested_route: route,
      extracted_entities: {
        amount_inr: extractedAmount,
        amount_paise: extractedAmount * 100,
        days: 5,
        counterparty: textLower.includes('swiggy') ? 'SWIGGY' : textLower.includes('sbi') ? 'SBI' : 'CLIENT',
        ref: '431209845123',
      },
      prompt,
      attachedFile: filename,
    };
  },

  async scanGmail(
    onProgress?: (progress: { total: number; noise: number; financial: number; candidates: number; currentItem: string }) => void,
    accessToken?: string
  ): Promise<{
    emails: EmailAuditItem[];
    transactions: Transaction[];
    candidates: Transaction[];
    isLiveToken: boolean;
  }> {
    // Attempt real backend Gmail endpoint first
    try {
      const res = await fetch('http://localhost:8000/v1/gmail/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: accessToken || null, max_results: 50 }),
      });
      if (res.ok) {
        const data = await res.json();
        return {
          emails: data.emails || mockEmails,
          transactions: mockTransactions,
          candidates: data.candidates || [mockTransactions[0], mockTransactions[2]],
          isLiveToken: Boolean(accessToken && accessToken.trim()),
        };
      }
    } catch {
      // Fall through to progressive simulation
    }

    const total = 1280;
    const stepsCount = 5;
    for (let i = 1; i <= stepsCount; i++) {
      await wait(180);
      onProgress?.({
        total: Math.round((total / stepsCount) * i),
        noise: Math.round((1248 / stepsCount) * i),
        financial: Math.round((32 / stepsCount) * i),
        candidates: i === stepsCount ? 3 : Math.min(i, 2),
        currentItem:
          i === 1
            ? 'Airfairness Sweep: Authenticating with Google OAuth 2.0...'
            : i === 2
            ? 'Querying financial alerts (HDFC, SBI, ICICI, PhonePe, Razorpay)...'
            : i === 3
            ? '3-Tier Noise Filter: Stripping OTPs, coupons, marketing digests...'
            : i === 4
            ? 'Matching UPI RRN & ATM transaction references...'
            : 'Sweep Complete: Evaluated turnaround times under RBI TAT Circular DPSS.CO.PD No.629.',
      });
    }

    return {
      emails: mockEmails,
      transactions: mockTransactions,
      candidates: [mockTransactions[0], mockTransactions[2]],
      isLiveToken: false,
    };
  },

  async ingest(): Promise<{ transactions: Transaction[]; parse_report: { accepted: boolean; rows: number } }> {
    await wait(200);
    return { transactions: mockTransactions, parse_report: { accepted: true, rows: mockTransactions.length } };
  },

  async detect(): Promise<{ candidates: Transaction[] }> {
    await wait(150);
    return { candidates: [mockTransactions[0], mockTransactions[2]] };
  },

  async computePayment(candidate?: Transaction): Promise<PaymentResult> {
    if (candidate && candidate.channel === 'ATM') {
      return {
        right_id: 'R-003',
        right_name: 'ATM debit, cash not dispensed (RBI Harmonised TAT)',
        mode: 'live',
        stamp: 'STATUTORY RBI RULE',
        debit_date: '2026-10-28',
        resolution_date: 'Unresolved as of today',
        deadline: '2026-11-02',
        delay_days: { low: 9, high: 9 },
        amount_paise: { low: 90000, high: 90000 },
        statutory_rate_desc: '₹100 per calendar day beyond T+5 window',
        unresolved: [],
        conflicts: [],
        confidence: 'High',
        source_citation: 'RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20 (Item 3)',
        source_url: 'https://rbi.org.in',
        trace: [
          {
            step: 1,
            text: 'ATM withdrawal debited on 28 October 2026 for ₹5,000.00 without cash dispensation.',
            clause: 'RBI TAT Item 3: ATM cash dispense failure',
            inputs: { debit_date: '2026-10-28', amount_paise: 500000 },
          },
          {
            step: 2,
            text: 'Statutory auto-reversal deadline is T+5 (2 November 2026).',
            clause: 'RBI circular clock spec',
            inputs: { deadline: '2026-11-02' },
          },
          {
            step: 3,
            text: 'As of today, transaction remains uncredited. Delay count is 9 days.',
            clause: 'Day-count logic',
            inputs: { days_late: 9 },
          },
          {
            step: 4,
            text: 'Statutory penalty: 9 days × ₹100/day = ₹900.00 plus full principal refund of ₹5,000.00.',
            clause: 'RBI Harmonised TAT Compensation Schedule',
            inputs: { penalty_paise: 90000, principal_paise: 500000 },
          },
        ],
      };
    }
    await wait(220);
    return mockResult;
  },

  computeMsme(params: {
    amount: number;
    invoiceDate: string;
    acceptanceDate: string;
    hasWrittenAgreement: boolean;
    agreedDays: number;
  }): MsmeResult {
    const accDate = new Date(params.acceptanceDate || params.invoiceDate);
    const limitDays = params.hasWrittenAgreement ? Math.min(params.agreedDays || 45, 45) : 15;

    const dueDate = new Date(accDate);
    dueDate.setDate(dueDate.getDate() + limitDays);

    const today = new Date();
    const overdueDays = Math.max(0, Math.floor((today.getTime() - dueDate.getTime()) / (1000 * 60 * 60 * 24)));

    const bankRate = 6.5;
    const statutoryRate = bankRate * 3; // 19.5%
    const monthlyRate = statutoryRate / 100 / 12;
    const months = overdueDays / 30.417;

    const totalWithInterest = params.amount * Math.pow(1 + monthlyRate, months);
    const interestOwed = Math.round(totalWithInterest - params.amount);

    return {
      invoiceAmount: params.amount,
      invoiceDate: params.invoiceDate,
      acceptanceDate: params.acceptanceDate,
      writtenAgreement: params.hasWrittenAgreement,
      agreedDays: limitDays,
      statutoryDeadline: dueDate.toISOString().split('T')[0],
      daysOverdue: overdueDays,
      bankRateAnnual: bankRate,
      statutoryInterestRate: statutoryRate,
      interestOwed,
      totalClaim: params.amount + interestOwed,
      taxImplicationNotice:
        'Under Section 43B(h) / Section 37(2)(g) of the Income-tax Act, the buyer cannot claim tax deduction for this unpaid invoice amount until actually paid to you.',
      trace: [
        {
          step: 1,
          text: `Invoice goods/services accepted on ${params.acceptanceDate}. Statutory credit window is ${limitDays} days (capped at 45 days under Section 15 MSMED Act).`,
          clause: 'MSMED Act 2006, Section 15',
          inputs: { acceptance_date: params.acceptanceDate, allowed_days: limitDays },
        },
        {
          step: 2,
          text: `Statutory payment due date was ${dueDate.toISOString().split('T')[0]}. Payment is ${overdueDays} days overdue.`,
          clause: 'MSMED Act 2006, Section 15',
          inputs: { deadline: dueDate.toISOString().split('T')[0], overdue_days: overdueDays },
        },
        {
          step: 3,
          text: `Interest rate: 3 × RBI Bank Rate (3 × 6.50% = 19.50% p.a.) compounded with monthly rests.`,
          clause: 'MSMED Act 2006, Section 16',
          inputs: { rbi_bank_rate: '6.50%', statutory_interest_rate: '19.50%' },
        },
        {
          step: 4,
          text: `Statutory interest calculated at ₹${interestOwed.toLocaleString('en-IN')}, bringing total enforceable dues to ₹${(params.amount + interestOwed).toLocaleString('en-IN')}.`,
          clause: 'Section 16 Compounding Formula',
          inputs: { principal: params.amount, interest: interestOwed, total: params.amount + interestOwed },
        },
      ],
    };
  },

  async draft(candidate?: Transaction, result?: PaymentResult): Promise<{
    draft: string;
    evidence_checklist: string[];
    escalation_ladder: string[];
  }> {
    await wait(180);
    const amountStr = result ? (result.amount_paise.high / 100).toLocaleString('en-IN') : '500';
    const txnRef = candidate?.ref || '431209845123';
    const txnDate = candidate?.date || '3 November 2026';

    return {
      draft: `To:
Principal Nodal Officer / Grievance Redressal Officer
Customer Service Department
[Bank Name / Remitter Bank]

Subject: Statutory claim for delayed reversal compensation under RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20 (Txn Ref: ${txnRef})

Dear Sir / Madam,

I am writing to formally request statutory compensation for the delayed reversal of a failed payment debited from my account.

Details of the transaction:
1. Account Number: [Masked: **${candidate?.narration_clean?.slice(-4) || '9122'}]
2. Transaction Date: ${txnDate}
3. Transaction Type: ${candidate?.channel || 'UPI Transfer'}
4. Transaction Reference / RRN: ${txnRef}
5. Debited Amount: ₹${candidate ? (candidate.debit / 100).toLocaleString('en-IN') : '2,000.00'}
6. Actual Resolution / Reversal Date: ${result?.resolution_date || '09 November 2026'}
7. Statutory Turnaround Deadline: ${result?.deadline || '04 November 2026'} (T+1 calendar day)
8. Days of Delay beyond Mandated Window: ${result?.delay_days.high || 5} days
9. Statutory Compensation Claimed: ₹${amountStr} (at ₹100 per day of delay)

Legal Basis:
Under the Reserve Bank of India Harmonised Framework for Turnaround Time (TAT) and customer compensation for failed transactions (Circular DPSS.CO.PD No.629/02.01.014/2019-20, Paragraph 4 and Annexure):
"Compensation shall be credited to the customer's account automatically without the customer having to claim it at the rate of ₹100/- per day."

Since the mandated auto-credit was not processed automatically, I request you to credit the compensation of ₹${amountStr} to my account within 7 working days.

Kindly issue a formal Complaint Reference Number upon receipt of this letter. If this grievance is not resolved within 30 days, I shall escalate this claim to the RBI Integrated Ombudsman under the Reserve Bank - Integrated Ombudsman Scheme, 2021.

Yours sincerely,
[Your Full Name]
[Registered Mobile Number]
[Email Address]`,
      evidence_checklist: [
        'Bank statement copy or email alert highlighting the failed debit',
        'Official email/SMS alert showing the date the reversal credit finally arrived',
        'Unique Transaction Reference (12-digit UPI RRN, UTR, or ATM Transaction ID)',
        'Acknowledgement or ticket number from merchant / app (e.g. Swiggy / PhonePe)',
        'Copy of this formal written claim submitted to the Bank Nodal Officer',
      ],
      escalation_ladder: [
        'Step 1: Submit this formal written claim to the Bank Branch Manager and Principal Nodal Officer.',
        'Step 2: Note down the 15-digit Bank Complaint Ticket / Service Request number.',
        'Step 3: If no credit or reply within 30 calendar days (or if rejected), file a complaint on the RBI CMS Portal (https://cms.rbi.org.in) under the RBI Integrated Ombudsman Scheme 2021.',
        'Step 4: The RBI Ombudsman has statutory powers to direct the bank to pay ₹100/day compensation plus up to ₹1,00,000 for mental agony/harassment.',
      ],
    };
  },
};
