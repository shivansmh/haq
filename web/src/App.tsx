import { useState } from 'react';
import {
  api,
  mockRegistry,
  type ClassifyResult,
  type EmailAuditItem,
  type MsmeResult,
  type PaymentResult,
  type Step,
  type Transaction,
} from './api';
import {
  Button,
  ConfidenceBadge,
  DisclaimerBanner,
  EmptyState,
  ErrorState,
  PrivacyNote,
  RangeAmount,
  SourceChip,
  StepHeader,
  TraceViewer,
  UnverifiedStamp,
} from './components';

export default function App() {
  const [screen, setScreen] = useState<Step>('home');
  const [chatPrompt, setChatPrompt] = useState('');
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [classification, setClassification] = useState<ClassifyResult | null>(null);

  // Airfairness-style Sweep Modal & Auth State
  const [showSweepModal, setShowSweepModal] = useState(false);
  const [customToken, setCustomToken] = useState('');
  const [isLiveToken, setIsLiveToken] = useState(false);

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [candidates, setCandidates] = useState<Transaction[]>([]);
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [result, setResult] = useState<PaymentResult | null>(null);
  const [draft, setDraft] = useState<{ draft: string; evidence_checklist: string[]; escalation_ladder: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Gmail Scanner State
  const [scanProgress, setScanProgress] = useState({
    total: 0,
    noise: 0,
    financial: 0,
    candidates: 0,
    currentItem: 'Connecting to Google OAuth 2.0 API...',
  });
  const [scannedEmails, setScannedEmails] = useState<EmailAuditItem[]>([]);

  // MSME State
  const [msmeData, setMsmeData] = useState<MsmeResult | null>(null);
  const [msmeForm, setMsmeForm] = useState({
    amount: 142800,
    invoiceDate: '2026-09-01',
    acceptanceDate: '2026-09-03',
    hasWrittenAgreement: true,
    agreedDays: 45,
  });

  const go = (next: Step) => {
    setError('');
    setScreen(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const reset = () => {
    setScreen('home');
    setChatPrompt('');
    setAttachedFile(null);
    setClassification(null);
    setShowSweepModal(false);
    setTransactions([]);
    setCandidates([]);
    setSelected(null);
    setResult(null);
    setDraft(null);
    setError('');
  };

  // 1. Submit Single Omni-Prompt (Auto-Classify Intent & File)
  const handleSubmitPrompt = async (textToClassify?: string) => {
    const text = textToClassify !== undefined ? textToClassify : chatPrompt;
    if (!text.trim() && !attachedFile) return;

    setLoading(true);
    setError('');
    try {
      const res = await api.classify(text, attachedFile?.name);
      setClassification(res);

      if (res.category === 'msme_dues') {
        const amt = res.extracted_entities.amount_inr || 142800;
        setMsmeForm((prev) => ({ ...prev, amount: amt }));
        setMsmeData(api.computeMsme({ ...msmeForm, amount: amt }));
      } else if (res.category === 'failed_payment') {
        const amtPaise = res.extracted_entities.amount_paise || 200000;
        const candidate: Transaction = {
          txn_id: 'auto-classified-01',
          date: '2026-11-03',
          narration_raw: text,
          narration_clean: `${res.extracted_entities.counterparty || 'UPI'} Payment (Debited, Delayed Reversal)`,
          debit: amtPaise,
          credit: 0,
          balance: 1842000,
          channel: text.toLowerCase().includes('atm') ? 'ATM' : 'UPI',
          ref: res.extracted_entities.ref || '431209845123',
          parse_confidence: 0.96,
        };
        setCandidates([candidate]);
        setSelected(candidate);
      }
    } catch {
      setError('Classification failed. Try another prompt or scan your Gmail directly.');
    } finally {
      setLoading(false);
    }
  };

  // 2. Launch Airfairness-style Gmail Sweep
  const handleStartGmailSweep = async (tokenToUse?: string) => {
    setShowSweepModal(false);
    go('gmail-sweep');
    setLoading(true);
    try {
      const token = tokenToUse || customToken;
      const res = await api.scanGmail((p) => {
        setScanProgress(p);
      }, token);
      setIsLiveToken(res.isLiveToken);
      setScannedEmails(res.emails);
      setTransactions(res.transactions);
      setCandidates(res.candidates);
      setSelected(res.candidates[0] || null);
    } catch {
      setError('Gmail sweep encountered an authorization error. Please check your token or run in demo mode.');
    } finally {
      setLoading(false);
    }
  };

  const handleCompute = async () => {
    setLoading(true);
    try {
      const res = await api.computePayment(selected || undefined);
      setResult(res);
      go('result');
    } catch {
      setError('Statutory compensation could not be computed.');
    } finally {
      setLoading(false);
    }
  };

  const handleMakeDraft = async () => {
    setLoading(true);
    try {
      const res = await api.draft(selected || undefined, result || undefined);
      setDraft(res);
      go('claim');
    } catch {
      setError('Formal claim draft could not be generated.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileAttach = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setAttachedFile(file);
      if (!chatPrompt.trim()) {
        setChatPrompt(`Review attached document: ${file.name}`);
      }
    }
  };

  return (
    <div className="radiant-canvas">
      <div className="radiant-beams" />
      <div className="vinyl-rings" />

      {/* Top Navbar */}
      <nav className="topbar">
        <div className="topbar-container">
          <button className="brand-button" onClick={reset} aria-label="Go to Haq home">
            <span className="brand-glyph">H</span>
            <span className="brand-text">haq</span>
            <span className="brand-badge">India</span>
          </button>

          <div className="nav-links">
            <button className="nav-item" onClick={() => setShowSweepModal(true)}>
              ⚡ Sweep Gmail
            </button>
            <button className="nav-item" onClick={() => go('sources')}>
              Rights Registry & Rules
            </button>
          </div>

          <div className="header-actions">
            <button className="btn-reset" onClick={reset} title="Purge all in-memory data">
              Clear My Data
            </button>
          </div>
        </div>
      </nav>

      <DisclaimerBanner />

      {error && (
        <div className="flow-container">
          <ErrorState message={error} />
        </div>
      )}

      {/* Airfairness-style Sweep Consent & Auth Modal */}
      {showSweepModal && (
        <GmailSweepModal
          onClose={() => setShowSweepModal(false)}
          onStartSweep={handleStartGmailSweep}
          customToken={customToken}
          setCustomToken={setCustomToken}
        />
      )}

      {/* Main Screen Router */}
      {screen === 'home' && (
        <HomeScreen
          chatPrompt={chatPrompt}
          setChatPrompt={setChatPrompt}
          attachedFile={attachedFile}
          setAttachedFile={setAttachedFile}
          onFileAttach={handleFileAttach}
          onSubmit={handleSubmitPrompt}
          onOpenSweepModal={() => setShowSweepModal(true)}
          loading={loading}
          classification={classification}
          onProceed={(cat) => {
            if (cat === 'msme_dues') go('msme');
            else if (cat === 'unclaimed_wealth') go('unclaimed');
            else go('candidates');
          }}
        />
      )}

      {screen === 'gmail-sweep' && (
        <GmailSweepScreen
          loading={loading}
          progress={scanProgress}
          emails={scannedEmails}
          isLiveToken={isLiveToken}
          onReview={() => go('candidates')}
          onRetry={() => setShowSweepModal(true)}
        />
      )}

      {screen === 'candidates' && (
        <CandidatesScreen
          candidates={candidates}
          selected={selected}
          setSelected={setSelected}
          onNext={handleCompute}
          loading={loading}
          onBack={() => go('home')}
        />
      )}

      {screen === 'result' && result && (
        <ResultScreen
          result={result}
          onNext={handleMakeDraft}
          loading={loading}
          onSources={() => go('sources')}
          onBack={() => go('candidates')}
        />
      )}

      {screen === 'claim' && <ClaimScreen draft={draft} onBack={() => go('result')} />}

      {screen === 'msme' && (
        <MsmeScreen
          form={msmeForm}
          setForm={setMsmeForm}
          result={msmeData}
          onCalculate={() => setMsmeData(api.computeMsme(msmeForm))}
          onBack={() => go('home')}
        />
      )}

      {screen === 'unclaimed' && <UnclaimedScreen onBack={() => go('home')} />}

      {screen === 'sources' && <SourcesScreen onBack={() => go('home')} />}

      {/* Footer */}
      <footer className="footer-wrap">
        <div className="footer-inner">
          <span>Haq · All-in-One Legal Empowerment Platform for Indian Consumers & Businesses</span>
          <PrivacyNote light />
          <span>Zero Server Storage · 100% In-Memory Ephemeral Session</span>
        </div>
      </footer>
    </div>
  );
}

/* =========================================================================
   AIRFAIRNESS-STYLE GMAIL SWEEP AUTHENTICATION & CONSENT MODAL
   ========================================================================= */
function GmailSweepModal({
  onClose,
  onStartSweep,
  customToken,
  setCustomToken,
}: {
  onClose: () => void;
  onStartSweep: (token?: string) => void;
  customToken: string;
  setCustomToken: (v: string) => void;
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        background: 'rgba(0,0,0,0.75)',
        backdropFilter: 'blur(16px)',
        display: 'grid',
        placeItems: 'center',
        padding: '20px',
      }}
    >
      <div
        style={{
          background: 'rgba(18, 22, 34, 0.95)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          borderRadius: '24px',
          maxWidth: '560px',
          width: '100%',
          padding: '32px',
          boxShadow: '0 24px 70px rgba(0,0,0,0.8), 0 0 50px rgba(99, 102, 241, 0.25)',
          position: 'relative',
        }}
      >
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            background: 'none',
            border: 'none',
            color: '#94a3b8',
            fontSize: '18px',
            cursor: 'pointer',
          }}
        >
          ✕
        </button>

        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '4px 12px', borderRadius: '9999px', background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.3)', color: '#c7d2fe', fontSize: '11px', fontWeight: 700, marginBottom: '16px' }}>
          <span>✦ OFFICIAL GOOGLE OAUTH 2.0 PROTOCOL</span>
        </div>

        <h2 style={{ fontSize: '24px', fontWeight: 800, color: '#fff', marginBottom: '10px' }}>
          Sweep Your Inbox for Delayed Payments & Dues
        </h2>

        <p style={{ fontSize: '13.5px', color: '#94a3b8', lineHeight: 1.6, marginBottom: '20px' }}>
          Like <strong>Airfairness Sweep</strong> for flights, Haq securely scans your email for financial debit alerts, failed UPI receipts, and overdue invoices to detect money owed to you under Indian law.
        </p>

        {/* Security / Scope Reassurance Card */}
        <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '14px', padding: '16px', marginBottom: '22px', fontSize: '12px', color: '#cbd5e1' }}>
          <div style={{ fontWeight: 700, color: '#fff', marginBottom: '6px' }}>How your privacy is protected:</div>
          <ul style={{ paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <li><strong>Restricted Scope:</strong> Only read-only permission (<code>gmail.readonly</code>) is requested.</li>
            <li><strong>Noise Filter:</strong> Personal emails, OTPs, and promotional spam are filtered in memory and never stored.</li>
            <li><strong>Transient Session:</strong> No refresh tokens, email bodies, or personal data are stored on any server.</li>
            <li><strong>Revocable Anytime:</strong> Remove access whenever you want in your Google Account Security tab.</li>
          </ul>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <Button
            variant="primary"
            onClick={async () => {
              // If live OAuth client is configured, open Google OAuth URL
              try {
                const info = await api.getGmailAuthUrl();
                if (info.client_id_configured) {
                  window.location.href = info.auth_url;
                  return;
                }
              } catch {
                // ignore
              }
              onStartSweep();
            }}
          >
            <svg className="google-icon" viewBox="0 0 24 24" width="18" height="18" style={{ marginRight: '6px' }}>
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
            </svg>
            Connect with Google & Sweep My Inbox
          </Button>

          <Button
            variant="secondary"
            onClick={() => onStartSweep()}
          >
            ⚡ Run Instant Demo Sweep (Zero Setup)
          </Button>

          {/* Advanced Custom Token Toggle */}
          <div style={{ marginTop: '8px', textAlign: 'center' }}>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{ background: 'none', border: 'none', color: '#64748b', fontSize: '11px', cursor: 'pointer', textDecoration: 'underline' }}
            >
              {showAdvanced ? 'Hide Custom Google Token Input' : 'Advanced: Paste Google OAuth Access Token directly'}
            </button>
          </div>

          {showAdvanced && (
            <div style={{ marginTop: '10px' }}>
              <input
                className="form-control"
                placeholder="Paste Bearer Access Token (ya29...)"
                value={customToken}
                onChange={(e) => setCustomToken(e.target.value)}
                style={{ fontSize: '12px' }}
              />
              <span style={{ fontSize: '11px', color: '#94a3b8', display: 'block', marginTop: '4px' }}>
                If provided, Haq sweeps your real live Gmail using this token.
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
   1. HOME SCREEN (Single Chat Prompt + Auto-Classification + Floating Cards)
   ========================================================================= */
function HomeScreen({
  chatPrompt,
  setChatPrompt,
  attachedFile,
  setAttachedFile,
  onFileAttach,
  onSubmit,
  onOpenSweepModal,
  loading,
  classification,
  onProceed,
}: {
  chatPrompt: string;
  setChatPrompt: (v: string) => void;
  attachedFile: File | null;
  setAttachedFile: (f: File | null) => void;
  onFileAttach: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (text?: string) => void;
  onOpenSweepModal: () => void;
  loading: boolean;
  classification: ClassifyResult | null;
  onProceed: (cat: string) => void;
}) {
  const suggestions = [
    'Swiggy debited ₹2,000 via UPI 5 days ago and failed',
    'Client has not paid my invoice of ₹1,42,800 for 50 days',
    'How do I trace grandfather’s unclaimed bank deposits on UDGAM?',
    'SBI ATM debited ₹5,000 but cash was not dispensed',
  ];

  return (
    <section className="hero-stage">
      <div className="hero-pill">
        <span className="hero-pill-icon">✦</span>
        <span>ONE-PROMPT LEGAL EMPOWERMENT ENGINE</span>
      </div>

      <h1 className="hero-headline">
        Every Rupee You’re Owed.
        <br />
        Claimed in Seconds.
      </h1>

      <p className="hero-subhead">
        Type what happened, attach any bank statement or invoice, or sweep your Gmail. Haq automatically classifies the legal violation, checks turnaround deadlines, and calculates what you are owed under RBI and MSMED laws.
      </p>

      {/* THE SINGLE CHAT PROMPT (CENTERPIECE) */}
      <div className="prompt-hero-container">
        <div className="omni-prompt-card">
          {attachedFile && (
            <div className="attached-file-badge">
              <span>📎 {attachedFile.name}</span>
              <button
                className="btn-remove-file"
                onClick={() => setAttachedFile(null)}
                title="Remove attached file"
              >
                ✕
              </button>
            </div>
          )}

          <textarea
            className="omni-textarea"
            placeholder="Describe what happened, paste an alert, or attach an invoice (e.g. 'Swiggy debited ₹2,000 via UPI 5 days ago', 'Buyer owes ₹1.4L for 2 months')..."
            value={chatPrompt}
            onChange={(e) => setChatPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                onSubmit();
              }
            }}
          />

          <div className="omni-toolbar">
            <div className="toolbar-left">
              <button className="gmail-instant-btn" onClick={onOpenSweepModal} type="button">
                <svg className="google-icon" viewBox="0 0 24 24" width="16" height="16">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                Sweep Gmail (Airfairness Mode)
              </button>

              <label className="attach-btn-label">
                📎 Attach Any Document
                <input
                  type="file"
                  accept=".pdf,.csv,.xlsx,.txt,.png,.jpg"
                  onChange={onFileAttach}
                />
              </label>
            </div>

            <button
              className="submit-arrow-btn"
              onClick={() => onSubmit()}
              disabled={loading || (!chatPrompt.trim() && !attachedFile)}
              title="Autoclassify & Compute Rights"
              aria-label="Autoclassify & Compute Rights"
            >
              {loading ? '…' : '→'}
            </button>
          </div>
        </div>

        {/* Quick Suggestion Pills */}
        <div className="prompt-suggestions">
          {suggestions.map((text, i) => (
            <button
              key={i}
              className="suggestion-pill"
              onClick={() => {
                setChatPrompt(text);
                onSubmit(text);
              }}
            >
              {text}
            </button>
          ))}
        </div>

        {/* AUTO-CLASSIFICATION PREVIEW CARD */}
        {classification && (
          <div className="classification-result-card">
            <div className="classification-header">
              <span className="class-badge">
                ✓ AUTOCLASSIFIED AS:{' '}
                {classification.category === 'failed_payment'
                  ? 'FAILED PAYMENT (RBI TAT)'
                  : classification.category === 'msme_dues'
                  ? 'MSME DELAYED INVOICE (SEC 15 & 16)'
                  : 'UNCLAIMED ASSETS TRACING'}
              </span>
              <span className="class-confidence">
                {Math.round(classification.confidence * 100)}% Confidence
              </span>
            </div>

            <h3 className="class-title">{classification.title}</h3>
            <p className="class-summary">{classification.summary}</p>

            <div className="entities-row">
              {classification.extracted_entities.amount_inr && (
                <span className="entity-pill">
                  Amount: ₹{classification.extracted_entities.amount_inr.toLocaleString('en-IN')}
                </span>
              )}
              {classification.extracted_entities.counterparty && (
                <span className="entity-pill">
                  Entity: {classification.extracted_entities.counterparty}
                </span>
              )}
              {classification.extracted_entities.days && (
                <span className="entity-pill">
                  Delay: ~{classification.extracted_entities.days} Days
                </span>
              )}
              <span className="entity-pill" style={{ color: '#38bdf8' }}>
                Legal Basis: {classification.statutory_law.split('(')[0]}
              </span>
            </div>

            <div className="class-action-row">
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                Statutory calculations ready based on verified regulations.
              </span>
              <Button
                variant="primary"
                onClick={() => onProceed(classification.category)}
              >
                Proceed to Calculated Rights & Claim Pack →
              </Button>
            </div>
          </div>
        )}
      </div>

      <PrivacyNote />

      {/* Orbiting Showcase Vignettes (Luma-style) */}
      <div className="vignettes-wrapper">
        <div
          className="vignette-card highlight"
          onClick={() => {
            const prompt = 'Swiggy UPI payment of ₹2,000 debited and reversal delayed by 5 days';
            setChatPrompt(prompt);
            onSubmit(prompt);
          }}
          role="button"
          tabIndex={0}
        >
          <div className="vignette-header">
            <span className="vignette-tag tag-upi">⚡ UPI Failed Reversal</span>
            <span className="vignette-icon">↗</span>
          </div>
          <div className="vignette-amount">₹500 Compensation</div>
          <div className="vignette-title">Swiggy ₹2,000 Debited · Delayed Reversal</div>
          <div className="vignette-desc">
            Reversal took 5 days. Mandated statutory penalty is ₹100 per day beyond T+1.
          </div>
          <div className="vignette-rule">RBI DPSS Circular No. 629 · Auto-Credit Mandate</div>
        </div>

        <div
          className="vignette-card"
          onClick={() => {
            const prompt = 'Client overdue on ₹1,42,800 MSME invoice for 52 days';
            setChatPrompt(prompt);
            onSubmit(prompt);
          }}
          role="button"
          tabIndex={0}
        >
          <div className="vignette-header">
            <span className="vignette-tag tag-msme">💼 MSME Delayed Dues</span>
            <span className="vignette-icon">□</span>
          </div>
          <div className="vignette-amount">₹1,42,800 + 3x Interest</div>
          <div className="vignette-title">Invoice #441 Overdue by 52 Days</div>
          <div className="vignette-desc">
            Statutory 45-day limit breached. Eligible for 3× RBI Bank Rate compound monthly.
          </div>
          <div className="vignette-rule">MSMED Act 2006, Sec 15 & 16 · Samadhaan Filing</div>
        </div>

        <div
          className="vignette-card"
          onClick={() => {
            const prompt = 'Trace my grandfather’s unclaimed bank deposit of ₹38,450 on UDGAM';
            setChatPrompt(prompt);
            onSubmit(prompt);
          }}
          role="button"
          tabIndex={0}
        >
          <div className="vignette-header">
            <span className="vignette-tag tag-unclaimed">🏦 UDGAM Bank Deposit</span>
            <span className="vignette-icon">○</span>
          </div>
          <div className="vignette-amount">₹38,450 Unclaimed</div>
          <div className="vignette-title">10-Year Dormant Savings Account</div>
          <div className="vignette-desc">
            Transferred to RBI DEA Fund. 100% principal recoverable with interest via official portal.
          </div>
          <div className="vignette-rule">RBI DEA Fund Scheme · Official Portal Route</div>
        </div>
      </div>
    </section>
  );
}

/* =========================================================================
   2. GMAIL LIVE SWEEP SCREEN (Airfairness-Inspired Noise Reduction View)
   ========================================================================= */
function GmailSweepScreen({
  loading,
  progress,
  emails,
  isLiveToken,
  onReview,
  onRetry,
}: {
  loading: boolean;
  progress: { total: number; noise: number; financial: number; candidates: number; currentItem: string };
  emails: EmailAuditItem[];
  isLiveToken: boolean;
  onReview: () => void;
  onRetry: () => void;
}) {
  return (
    <div className="flow-container">
      <div className="flow-card">
        <StepHeader
          kicker="Airfairness-Style Gmail Sweep Engine"
          title="Extracting Financial Signals from Inbox Noise"
        >
          {isLiveToken
            ? 'Connected live to Google Gmail API via OAuth 2.0. Sweeping your messages with zero permanent storage.'
            : 'Sweeping financial notifications and stripping marketing emails, OTPs, and newsletters in memory.'}
        </StepHeader>

        <div className="scanner-status-card">
          <div className="scanner-progress-header">
            <div className="scanner-badge">
              <span className="pulse-spinner" />
              <span>{loading ? 'Inbox Sweep in Progress...' : 'Inbox Sweep Complete'}</span>
            </div>
            <span style={{ fontSize: '12px', color: '#94a3b8' }}>
              {loading ? `${Math.round((progress.total / 1280) * 100)}%` : '100%'}
            </span>
          </div>

          <div className="scanner-progress-bar">
            <div
              className="scanner-progress-fill"
              style={{ width: `${loading ? Math.max(10, Math.round((progress.total / 1280) * 100)) : 100}%` }}
            />
          </div>

          <p className="scanner-current-task">{progress.currentItem}</p>

          <div className="scanner-stats-grid">
            <div className="stat-tile">
              <span className="stat-number">{progress.total.toLocaleString()}</span>
              <span className="stat-label">Emails Swept</span>
            </div>
            <div className="stat-tile">
              <span className="stat-number" style={{ color: '#94a3b8' }}>
                {progress.noise.toLocaleString()}
              </span>
              <span className="stat-label">Noise Stripped</span>
            </div>
            <div className="stat-tile">
              <span className="stat-number" style={{ color: '#38bdf8' }}>
                {progress.financial}
              </span>
              <span className="stat-label">Financial Alerts</span>
            </div>
            <div className="stat-tile" style={{ background: 'rgba(99, 102, 241, 0.12)', borderColor: '#818cf8' }}>
              <span className="stat-number" style={{ color: '#c7d2fe' }}>
                {progress.candidates}
              </span>
              <span className="stat-label" style={{ color: '#a5b4fc', fontWeight: 700 }}>
                Violations Found
              </span>
            </div>
          </div>
        </div>

        {/* Live Filter Stream */}
        <div className="email-stream-section">
          <div className="section-label-row">
            <span className="section-label">Real-Time Noise Reduction Stream</span>
            <span style={{ fontSize: '12px', color: '#64748b' }}>
              Showing {emails.length} categorized messages
            </span>
          </div>

          <div className="email-list">
            {emails.map((email) => (
              <div
                key={email.id}
                className={`email-row ${
                  email.status === 'violation_detected'
                    ? 'violation'
                    : email.status === 'financial_alert'
                    ? 'alert'
                    : 'noise'
                }`}
              >
                <div style={{ flexShrink: 0 }}>
                  <span
                    className={`email-filter-pill ${
                      email.status === 'violation_detected'
                        ? 'pill-violation'
                        : email.status === 'financial_alert'
                        ? 'pill-alert'
                        : 'pill-noise'
                    }`}
                  >
                    {email.filterTag}
                  </span>
                </div>

                <div className="email-content">
                  <div className="email-meta">
                    <span className="email-sender">{email.sender}</span>
                    <span className="email-date">{email.date}</span>
                  </div>
                  <div className="email-subject">{email.subject}</div>
                  <div className="email-snippet">{email.snippet}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="action-bar">
          <Button variant="quiet" onClick={onRetry} disabled={loading}>
            Configure / Resweep
          </Button>

          <Button variant="primary" onClick={onReview} disabled={loading}>
            Inspect Actionable Violations ({progress.candidates}) →
          </Button>
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
   3. CANDIDATE CONFIRMATION SCREEN
   ========================================================================= */
function CandidatesScreen({
  candidates,
  selected,
  setSelected,
  onNext,
  loading,
  onBack,
}: {
  candidates: Transaction[];
  selected: Transaction | null;
  setSelected: (row: Transaction) => void;
  onNext: () => void;
  loading: boolean;
  onBack: () => void;
}) {
  const money = (p: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(p / 100);

  return (
    <div className="flow-container">
      <div className="flow-card">
        <StepHeader
          kicker="Statutory Candidate Review"
          title="Select Transaction & Confirm Event Facts"
        >
          A debit in a statement or email does not always mean a failed payment. Your confirmation converts a candidate into an enforceable claim.
        </StepHeader>

        <div className="candidate-selection-list">
          {candidates.map((cand, idx) => (
            <div
              key={cand.txn_id}
              className={`candidate-item ${selected?.txn_id === cand.txn_id ? 'selected' : ''}`}
              onClick={() => setSelected(cand)}
              role="button"
              tabIndex={0}
            >
              <div className="candidate-radio">{selected?.txn_id === cand.txn_id ? '✓' : idx + 1}</div>

              <div className="candidate-info">
                <div className="candidate-amount-row">
                  <span className="candidate-amount">{money(cand.debit)}</span>
                  <span className="candidate-channel">{cand.channel}</span>
                  <span style={{ fontSize: '12px', color: '#94a3b8' }}>Txn Date: {cand.date}</span>
                </div>
                <div className="candidate-narration">{cand.narration_clean}</div>

                {cand.email_source && (
                  <div className="candidate-source-snippet">
                    <strong>Email Evidence:</strong> "{cand.email_source.snippet}"
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {selected ? (
          <div className="confirmation-box">
            <h3 className="confirmation-title">
              Confirming Details for {money(selected.debit)} ({selected.channel})
            </h3>
            <p className="confirmation-desc">
              Did the beneficiary / merchant receive the money on the transaction date ({selected.date})?
            </p>

            <div className="choice-options">
              <button className="choice-btn active">No, payment failed / money was delayed</button>
              <button className="choice-btn">Yes, payment arrived on time</button>
            </div>

            <div style={{ marginTop: '14px', fontSize: '12px', color: '#94a3b8' }}>
              ✓ Backed by RBI DPSS Circular No. 629. Haq will compute the turnaround time delay and daily penalty.
            </div>
          </div>
        ) : (
          <EmptyState title="Select a candidate above">
            Choose a flagged transaction to see what compensation is legally owed to you.
          </EmptyState>
        )}

        <div className="action-bar">
          <Button variant="quiet" onClick={onBack}>
            Back
          </Button>
          <Button variant="primary" onClick={onNext} disabled={!selected || loading}>
            {loading ? 'Calculating Statutory Rules...' : 'Compute Legal Compensation →'}
          </Button>
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
   4. RESULT SCREEN (Show Working, Trace, Range & Statutory Penalties)
   ========================================================================= */
function ResultScreen({
  result,
  onNext,
  loading,
  onSources,
  onBack,
}: {
  result: PaymentResult;
  onNext: () => void;
  loading: boolean;
  onSources: () => void;
  onBack: () => void;
}) {
  return (
    <div className="flow-container">
      <div className="flow-card">
        <StepHeader
          kicker="Statutory Legal Calculation"
          title="Here is the Mathematical Working, Not a Guess"
        >
          Under primary Reserve Bank of India circulars, banks are legally mandated to compensate customers for delayed reversals.
        </StepHeader>

        <div className="result-overview-grid">
          <div className="metric-card">
            <span className="metric-label">Statutory Deadline (TAT)</span>
            <span className="metric-value">{result.deadline}</span>
            <span className="metric-sub">Mandated auto-reversal by T+1 calendar day</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Statutory Delay</span>
            <span className="metric-value">
              {result.delay_days.low === result.delay_days.high
                ? `${result.delay_days.high} Days`
                : `${result.delay_days.low} to ${result.delay_days.high} Days`}
            </span>
            <span className="metric-sub">Calculated beyond mandated window</span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', alignItems: 'center' }}>
          <UnverifiedStamp label="STATUTORY RBI MANDATE" />
          <ConfidenceBadge value={result.confidence} />
          <SourceChip id={result.right_id} label="RBI Harmonised TAT" />
        </div>

        {/* Dynamic Compensation Range Box */}
        <RangeAmount result={result} />

        {/* Step-by-Step Mathematical & Legal Trace */}
        <TraceViewer trace={result.trace} />

        {/* Legal Citation Pill */}
        <div style={{ marginTop: '20px', padding: '16px', borderRadius: '12px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <span style={{ fontSize: '12.5px', color: '#cbd5e1' }}>
            <strong>Primary Legal Instrument:</strong> {result.source_citation}
          </span>
          <button
            onClick={onSources}
            style={{ background: 'none', border: 'none', color: '#818cf8', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
          >
            Inspect in Rights Registry →
          </button>
        </div>

        <div className="action-bar">
          <Button variant="quiet" onClick={onBack}>
            Back
          </Button>
          <Button variant="glow" onClick={onNext} disabled={loading}>
            {loading ? 'Drafting Formal Pack...' : 'Generate Ready-to-File Claim Pack →'}
          </Button>
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
   5. CLAIM PACK SCREEN
   ========================================================================= */
function ClaimScreen({
  draft,
  onBack,
}: {
  draft: { draft: string; evidence_checklist: string[]; escalation_ladder: string[] } | null;
  onBack: () => void;
}) {
  const [copied, setCopied] = useState(false);

  if (!draft) {
    return (
      <div className="flow-container">
        <EmptyState title="No claim draft ready">Return to results to generate a claim.</EmptyState>
      </div>
    );
  }

  const handleCopy = () => {
    navigator.clipboard?.writeText(draft.draft);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="flow-container">
      <div className="flow-card">
        <StepHeader
          kicker="Enforcement Action"
          title="Your Ready-to-File Statutory Claim Pack"
        >
          Review and copy this formal claim letter. Submit it to your bank’s Principal Nodal Officer or escalate to the RBI Integrated Ombudsman.
        </StepHeader>

        <div className="claim-grid">
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#a5b4fc' }}>
                Formal Claim Letter (Editable)
              </span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <Button variant="secondary" onClick={handleCopy} className="btn-sm">
                  {copied ? '✓ Copied to Clipboard' : 'Copy Text'}
                </Button>
                <Button variant="secondary" onClick={() => window.print()} className="btn-sm">
                  Print Letter
                </Button>
              </div>
            </div>

            <textarea className="draft-box" defaultValue={draft.draft} />
          </div>

          <div>
            <div className="claim-side-card">
              <span className="side-card-title">Evidence Checklist</span>
              {draft.evidence_checklist.map((item, idx) => (
                <label className="checklist-item" key={idx}>
                  <input type="checkbox" defaultChecked={idx < 2} />
                  <span>{item}</span>
                </label>
              ))}
            </div>

            <div className="claim-side-card">
              <span className="side-card-title">Statutory Escalation Ladder</span>
              {draft.escalation_ladder.map((step, idx) => (
                <div className="ladder-step" key={idx}>
                  <span className="ladder-num">{idx + 1}</span>
                  <p>{step}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="action-bar">
          <Button variant="quiet" onClick={onBack}>
            Back to Calculation
          </Button>
          <Button variant="primary" onClick={() => window.location.reload()}>
            Start Another Review
          </Button>
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
   6. MSME DELAYED DUES SCREEN
   ========================================================================= */
function MsmeScreen({
  form,
  setForm,
  result,
  onCalculate,
  onBack,
}: {
  form: { amount: number; invoiceDate: string; acceptanceDate: string; hasWrittenAgreement: boolean; agreedDays: number };
  setForm: (f: any) => void;
  result: MsmeResult | null;
  onCalculate: () => void;
  onBack: () => void;
}) {
  return (
    <div className="flow-container">
      <div className="flow-card">
        <StepHeader
          kicker="MSMED Act 2006 Statutory Rights"
          title="MSME Delayed Invoices & Statutory Interest"
        >
          For micro & small businesses, suppliers, and freelancers. Sections 15 & 16 mandate payment within 15–45 days, with compound monthly interest at 3× the RBI Bank Rate.
        </StepHeader>

        <div className="form-row">
          <div className="form-group">
            <label>Invoice Amount (₹)</label>
            <input
              className="form-control"
              type="number"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })}
            />
          </div>

          <div className="form-group">
            <label>Invoice Acceptance Date</label>
            <input
              className="form-control"
              type="date"
              value={form.acceptanceDate}
              onChange={(e) => setForm({ ...form, acceptanceDate: e.target.value })}
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Written Payment Agreement?</label>
            <select
              className="form-control"
              value={form.hasWrittenAgreement ? 'yes' : 'no'}
              onChange={(e) => setForm({ ...form, hasWrittenAgreement: e.target.value === 'yes' })}
            >
              <option value="yes">Yes — Agreement exists (max 45 days)</option>
              <option value="no">No Agreement — Strict 15-day limit applies</option>
            </select>
          </div>

          <div className="form-group">
            <label>Agreed Credit Period (Days)</label>
            <input
              className="form-control"
              type="number"
              max={45}
              disabled={!form.hasWrittenAgreement}
              value={form.agreedDays}
              onChange={(e) => setForm({ ...form, agreedDays: Number(e.target.value) })}
            />
          </div>
        </div>

        <div style={{ marginBottom: '24px' }}>
          <Button variant="glow" onClick={onCalculate}>
            Recalculate MSME Interest & Notice →
          </Button>
        </div>

        {result && (
          <div>
            <div className="result-overview-grid">
              <div className="metric-card">
                <span className="metric-label">Statutory Due Date</span>
                <span className="metric-value">{result.statutoryDeadline}</span>
                <span className="metric-sub">{result.daysOverdue} days overdue beyond deadline</span>
              </div>

              <div className="metric-card">
                <span className="metric-label">Compounded Statutory Interest</span>
                <span className="metric-value" style={{ color: '#f59e0b' }}>
                  ₹{result.interestOwed.toLocaleString('en-IN')}
                </span>
                <span className="metric-sub">3× RBI Bank Rate (19.5% p.a. monthly rests)</span>
              </div>
            </div>

            <div className="amount-hero-card">
              <div className="amount-label-row">
                <span className="amount-label">TOTAL STATUTORY ENFORCEABLE CLAIM</span>
                <span className="amount-sublabel">MSMED Act 2006, Section 16</span>
              </div>
              <div className="amount-figure">
                <span className="amount-val">₹{result.totalClaim.toLocaleString('en-IN')}</span>
              </div>
              <div className="amount-note">
                <strong>Buyer Tax Consequence Note:</strong> {result.taxImplicationNotice}
              </div>
            </div>

            <TraceViewer trace={result.trace} />
          </div>
        )}

        <div className="action-bar">
          <Button variant="quiet" onClick={onBack}>
            Back Home
          </Button>
          <Button variant="primary" onClick={() => window.print()}>
            Print Formal Demand Notice
          </Button>
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
   7. UNCLAIMED ASSETS SCREEN
   ========================================================================= */
function UnclaimedScreen({ onBack }: { onBack: () => void }) {
  const assets = [
    {
      name: 'Unclaimed Bank Deposits (10+ Years)',
      portal: 'UDGAM Portal (RBI)',
      url: 'https://udgam.rbi.org.in',
      desc: 'Transferred to the Depositor Education & Awareness (DEA) Fund. Search across 30+ major banks covering ~90% of unclaimed deposits.',
      docs: ['Identity proof (PAN/Aadhaar)', 'Original passbook or FD certificate', 'Cancelled cheque for active account'],
    },
    {
      name: 'Unclaimed Corporate Shares & Dividends',
      portal: 'IEPF Authority (Ministry of Corporate Affairs)',
      url: 'https://www.iepf.gov.in',
      desc: 'Dividends and shares unpaid for 7 consecutive years are transferred to IEPF. Recoverable via e-Form IEPF-5.',
      docs: ['Client Master List (CML)', 'Original dividend warrants or indemnity bond', 'Aadhaar & PAN verification'],
    },
    {
      name: 'Unclaimed Life & General Insurance Proceeds',
      portal: 'Bima Bharosa Portal (IRDAI)',
      url: 'https://bimabharosa.irdai.gov.in',
      desc: 'Matured policies, death claims, or unclaimed premium refunds held by insurers for over 6 months.',
      docs: ['Policy bond copy', 'Bank mandate & cancelled cheque', 'Claimant KYC documents'],
    },
    {
      name: 'Dormant Provident Fund (EPFO)',
      portal: 'EPFO Unified Member Portal',
      url: 'https://unifiedportal-mem.epfindia.gov.in',
      desc: 'Inoperative accounts continue earning interest until age 58. Claimable directly using Universal Account Number (UAN).',
      docs: ['UAN active credentials', 'Aadhaar-linked mobile OTP', 'Bank account seeded with EPFO'],
    },
  ];

  return (
    <div className="flow-container">
      <div className="flow-card">
        <StepHeader
          kicker="Asset Recovery Wizard"
          title="Official Government Portals for Unclaimed Wealth"
        >
          Over ₹1.08 lakh crore lies unclaimed across Indian banks, insurers, and funds. Haq provides the direct, verified official routes without third-party fees.
        </StepHeader>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '24px' }}>
          {assets.map((item, idx) => (
            <div
              key={idx}
              style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '16px',
                padding: '20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>{item.name}</h3>
                  <span style={{ fontSize: '12px', color: '#818cf8', fontWeight: 600 }}>{item.portal}</span>
                </div>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary"
                  style={{ fontSize: '11px', padding: '6px 14px' }}
                >
                  Open Official Portal ↗
                </a>
              </div>

              <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '14px' }}>
                {item.desc}
              </p>

              <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
                <strong style={{ color: '#a5b4fc' }}>Required Documents: </strong>
                {item.docs.join(' · ')}
              </div>
            </div>
          ))}
        </div>

        <div className="action-bar">
          <Button variant="quiet" onClick={onBack}>
            Back Home
          </Button>
        </div>
      </div>
    </div>
  );
}

/* =========================================================================
   8. SOURCES & RIGHTS REGISTRY SCREEN
   ========================================================================= */
function SourcesScreen({ onBack }: { onBack: () => void }) {
  return (
    <div className="flow-container">
      <div className="flow-card">
        <StepHeader
          kicker="Research Ledger & Primary Sources"
          title="Verified Rights Registry (Statutes & Regulations)"
        >
          Every rule, clock, and compensation rate in Haq is derived from published primary instruments.
        </StepHeader>

        <table className="registry-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Right & Name</th>
              <th>Category</th>
              <th>Primary Legal Source</th>
              <th>Statutory Formula</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {mockRegistry.map((reg) => (
              <tr key={reg.id}>
                <td className="reg-id">{reg.id}</td>
                <td>
                  <span className="reg-name">{reg.name}</span>
                </td>
                <td style={{ fontSize: '12px', color: '#94a3b8' }}>{reg.category}</td>
                <td style={{ fontSize: '12px', color: '#cbd5e1' }}>{reg.source}</td>
                <td style={{ fontSize: '12px', color: '#38bdf8' }}>{reg.formula}</td>
                <td>
                  <span className="conf-badge conf-high">{reg.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ marginTop: '28px', padding: '20px', borderRadius: '16px', background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
          <h4 style={{ color: '#fbbf24', fontSize: '14px', marginBottom: '8px' }}>Open Research Conflict C5</h4>
          <p style={{ fontSize: '12.5px', color: '#fef3c7', lineHeight: 1.5 }}>
            Under RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20, does the reversal day itself count towards the delay penalty?
            Haq surfaces this transparently as a range (e.g. ₹400 to ₹500) rather than making a silent legal assumption.
          </p>
        </div>

        <div className="action-bar">
          <Button variant="quiet" onClick={onBack}>
            Back Home
          </Button>
        </div>
      </div>
    </div>
  );
}
