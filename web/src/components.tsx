import type { ReactNode } from 'react';
import type { PaymentResult, TraceStep } from './api';

export function DisclaimerBanner() {
  return (
    <div className="disclaimer-banner">
      <div className="disclaimer-inner">
        <span className="disclaimer-badge">STATUTORY RIGHTS NOTICE</span>
        <span className="disclaimer-text">
          Haq computes what primary Indian legal regulations (RBI TAT circulars, MSMED Act 2006, SEBI/UDGAM guidelines) state. Haq is an assistive technology, not a law firm, and does not file claims without your review.
        </span>
      </div>
    </div>
  );
}

export function PrivacyNote({ light = false }: { light?: boolean }) {
  return (
    <div className={`privacy-pill ${light ? 'light' : ''}`}>
      <span className="privacy-dot" />
          <span>Transient processing · server-side session · disconnect and revoke anytime</span>
    </div>
  );
}

export function UnverifiedStamp({ label = 'UNVERIFIED RULE' }: { label?: string }) {
  return <span className="statutory-stamp">{label}</span>;
}

export function ConfidenceBadge({ value }: { value: 'High' | 'Medium' | 'Low' }) {
  return <span className={`conf-badge conf-${value.toLowerCase()}`}>Confidence: {value}</span>;
}

export function RangeAmount({ result }: { result: PaymentResult }) {
  const low = result.amount_paise.low / 100;
  const high = result.amount_paise.high / 100;
  const formatter = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

  return (
    <div className="amount-hero-card">
      <div className="amount-label-row">
        <span className="amount-label">ILLUSTRATIVE WORKING RANGE</span>
        <span className="amount-sublabel">{result.statutory_rate_desc}</span>
      </div>
      <div className="amount-figure">
        {low === high ? (
          <span className="amount-val">₹{formatter.format(high)}</span>
        ) : (
          <span className="amount-val">
            ₹{formatter.format(low)} <span className="amount-sep">to</span> ₹{formatter.format(high)}
          </span>
        )}
      </div>
      <div className="amount-note">
        {result.conflicts.includes('C5') ? (
          <span>
            <strong>Research convention open:</strong> this range is not a legal determination; the lower and upper figures reflect the unresolved day-count convention.
          </span>
        ) : (
          <span>Review the source and transaction evidence before relying on this figure.</span>
        )}
      </div>
    </div>
  );
}

export function TraceViewer({ trace }: { trace: TraceStep[] }) {
  return (
    <details className="trace-accordion" open>
      <summary className="trace-summary">
        <span className="trace-title">
          <span className="trace-icon">✦</span> Mathematical & Legal Trace
        </span>
        <span className="trace-count">{trace.length} working steps</span>
      </summary>
      <div className="trace-steps">
        {trace.map((item) => (
          <div className="trace-item" key={item.step}>
            <div className="trace-step-number">{item.step}</div>
            <div className="trace-body">
              <p className="trace-text">{item.text}</p>
              <span className="trace-clause">Source: {item.clause}</span>
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}

export function SourceChip({ id = 'R-001', label = 'RBI TAT Circular' }: { id?: string; label?: string }) {
  return (
    <div className="source-pill">
      <span className="source-dot">§</span>
      <span className="source-code">{id}</span>
      <span className="source-name">{label}</span>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty-box">
      <div className="empty-glyph">✦</div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="error-card">
      <span className="error-icon">!</span>
      <div className="error-body">
        <strong>Attention Required</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}

export function StepHeader({ kicker, title, children }: { kicker: string; title: string; children?: ReactNode }) {
  return (
    <div className="step-header-block">
      <span className="step-kicker">{kicker}</span>
      <h1 className="step-title">{title}</h1>
      {children && <p className="step-subtitle">{children}</p>}
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  type = 'button',
  disabled = false,
  className = '',
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'quiet' | 'glow' | 'danger';
  type?: 'button' | 'submit';
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      type={type}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
