import type { ReactNode } from 'react';
import type { PaymentResult, TraceStep } from './api';

export function DisclaimerBanner() {
  return <div className="disclaimer"><span className="eyebrow">Important</span><span>Haq explains what a rule says. It is not legal advice and does not file anything for you.</span></div>;
}

export function PrivacyNote() {
  return <div className="privacy-note"><span className="privacy-dot" /> Your statement is processed for this session only. Haq does not store it.</div>;
}

export function UnverifiedStamp() {
  return <span className="stamp">UNVERIFIED RULE</span>;
}

export function ConfidenceBadge({ value }: { value: string }) {
  return <span className={`badge badge-${value.toLowerCase()}`}>Confidence: {value}</span>;
}

export function RangeAmount({ result }: { result: PaymentResult }) {
  const low = result.amount_paise.low / 100;
  const high = result.amount_paise.high / 100;
  const formatter = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });
  return <div className="amount-box"><span className="eyebrow">Possible amount</span><strong>₹{formatter.format(low)} <em>to</em> ₹{formatter.format(high)}</strong><p>The range stays visible because the reversal-day convention is unresolved.</p></div>;
}

export function TraceViewer({ trace }: { trace: TraceStep[] }) {
  return <details className="trace" open><summary>Show the working <span>({trace.length} steps)</span></summary><div className="trace-list">{trace.map((item) => <div className="trace-step" key={item.step}><span className="trace-number">{item.step}</span><div><p>{item.text}</p><small>{item.clause}</small></div></div>)}</div></details>;
}

export function SourceChip({ id = 'R-001', label = 'RBI turnaround-time circular' }: { id?: string; label?: string }) {
  return <button className="source-chip" type="button" onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })}><span className="source-icon">↗</span><span><strong>{id}</strong> · {label}</span></button>;
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty"><span className="empty-mark">—</span><h3>{title}</h3><p>{children}</p></div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="error-state"><strong>Something needs a second look.</strong><p>{message}</p></div>;
}

export function StepHeader({ kicker, title, children }: { kicker: string; title: string; children?: ReactNode }) {
  return <header className="step-header"><span className="eyebrow">{kicker}</span><h1>{title}</h1>{children && <p>{children}</p>}</header>;
}

export function Button({ children, onClick, variant = 'primary', type = 'button', disabled = false }: { children: ReactNode; onClick?: () => void; variant?: 'primary' | 'secondary' | 'quiet'; type?: 'button' | 'submit'; disabled?: boolean }) {
  return <button className={`button button-${variant}`} type={type} onClick={onClick} disabled={disabled}>{children}<span aria-hidden="true">{variant === 'primary' ? '→' : ''}</span></button>;
}
