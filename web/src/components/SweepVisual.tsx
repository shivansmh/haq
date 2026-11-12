import { useEffect, useRef, useState } from "react";
import { Check, Mail, Pause, Play, RotateCcw, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const INBOX = [
  { from: "HDFC Bank", subject: "Rs 2,000.00 debited via UPI to SWIGGY", flag: true },
  { from: "Zomato", subject: "Your weekend offers are here", flag: false },
  { from: "State Bank of India", subject: "ATM cash dispense incomplete — Rs 5,000", flag: true },
  { from: "LinkedIn", subject: "You appeared in 12 searches", flag: false },
  { from: "PhonePe", subject: "Payment failed — amount will be reversed", flag: true },
  { from: "Acme Traders", subject: "Invoice MSME-2026-441 — 61 days overdue", flag: true },
  { from: "Myntra", subject: "Your order has shipped", flag: false },
];

const RESULTS = [
  { ref: "ATM8829103", label: "ATM cash not dispensed", bank: "SBI", amount: 5000, tag: "Ready" },
  { ref: "MSME-2026-441", label: "Overdue MSME invoice", bank: "Acme Traders", amount: 142800, tag: "Ready" },
  { ref: "UPIREF-DEMO-001", label: "Failed UPI, money debited", bank: "HDFC · PhonePe", amount: 2000, tag: "Review" },
];
const TOTAL = RESULTS.reduce((s, r) => s + r.amount, 0);
const SCAN_MS = 5200; // full pass of the beam
const HOLD_MS = 6500;
const fmt = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");
const ease = (t: number) => 1 - Math.pow(1 - t, 3);

export function SweepVisual() {
  const [progress, setProgress] = useState(0); // 0..1 beam position
  const [phase, setPhase] = useState<"scan" | "results">("scan");
  const [paused, setPaused] = useState(false);
  const [count, setCount] = useState(0);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const t0 = useRef(0);
  const elapsed = useRef(0);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (paused) return;
    let raf = 0;
    t0.current = performance.now() - elapsed.current;
    const tick = (now: number) => {
      elapsed.current = now - t0.current;
      const e = elapsed.current;
      if (e < SCAN_MS) { setPhase("scan"); setProgress(e / SCAN_MS); }
      else if (e < SCAN_MS + HOLD_MS) { setPhase("results"); setProgress(1); setCount(TOTAL * ease(Math.min(1, (e - SCAN_MS) / 1400))); }
      else { elapsed.current = 0; t0.current = now; setCount(0); }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [paused]);

  const restart = () => { elapsed.current = 0; t0.current = performance.now(); setCount(0); setPhase("scan"); setProgress(0); setPaused(false); };
  const onMove = (ev: React.PointerEvent) => {
    const r = ref.current?.getBoundingClientRect(); if (!r) return;
    setTilt({ x: ((ev.clientY - r.top) / r.height - 0.5) * -6, y: ((ev.clientX - r.left) / r.width - 0.5) * 8 });
  };

  const rowPos = progress * INBOX.length;
  const found = INBOX.filter((e, i) => e.flag && i < rowPos - 0.5).length;
  const reading = INBOX[Math.min(INBOX.length - 1, Math.floor(rowPos))];

  return (
    <div
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={() => setTilt({ x: 0, y: 0 })}
      style={{ transform: `perspective(1000px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)` }}
      className="relative w-full max-w-md overflow-hidden rounded-2xl border border-panel-border bg-panel text-panel-foreground shadow-panel transition-transform duration-300 ease-out"
      aria-label="Interactive preview of an inbox sweep"
    >
      <div className="flex items-center justify-between border-b border-panel-border px-4 py-3 text-sm">
        <span className="flex items-center gap-2 font-semibold"><Mail className="size-4 text-primary" /> {phase === "scan" ? "Gmail" : "Sweep results"}</span>
        <div className="flex items-center gap-1">
          <span className="mr-2 flex items-center gap-1.5 text-xs text-primary"><span className={cn("size-1.5 rounded-full bg-primary", !paused && "animate-pulse")} />{phase === "scan" ? "Read-only" : "Complete"}</span>
          <button onClick={() => setPaused((p) => !p)} aria-label={paused ? "Play" : "Pause"} className="grid size-7 place-items-center rounded-md hover:bg-panel-raised">{paused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />}</button>
          <button onClick={restart} aria-label="Replay" className="grid size-7 place-items-center rounded-md hover:bg-panel-raised"><RotateCcw className="size-3.5" /></button>
        </div>
      </div>

      <div className="relative h-[480px]">
        {/* Inbox layer */}
        <div className={cn("absolute inset-0 transition-all duration-700 ease-out", phase === "results" && "pointer-events-none -translate-y-4 opacity-0 blur-sm")}>
          <ul className="relative">
            {INBOX.map((e, i) => {
              const local = Math.max(0, Math.min(1, rowPos - i)); // 0 untouched → 1 passed
              const done = local >= 0.5;
              return (
                <li key={e.subject} className={cn("flex items-center gap-3 border-b border-panel-border px-4 py-2.5 transition-[opacity,background-color] duration-500", done && !e.flag && "opacity-30", done && e.flag && "bg-primary/10")}>
                  <span className={cn("grid size-5 shrink-0 place-items-center rounded border transition-all duration-300", done && e.flag ? "scale-100 border-primary bg-primary text-primary-foreground" : "border-panel-border")}>
                    {done && e.flag && <Check className="size-3" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">{e.from}</p>
                    <p className="truncate text-xs text-panel-muted">{e.subject}</p>
                  </div>
                  <span className={cn("rounded-full bg-primary/20 px-2 py-0.5 text-[10px] font-semibold text-primary transition-all duration-500", done && e.flag ? "translate-x-0 opacity-100" : "translate-x-3 opacity-0")}>Claimable?</span>
                </li>
              );
            })}
            {/* Beam */}
            <span className="sweep-beam pointer-events-none absolute inset-x-0 h-16 -translate-y-1/2" style={{ top: `${progress * 100}%` }} />
          </ul>
          <div className="absolute inset-x-0 bottom-0 border-t border-panel-border bg-panel px-4 py-3">
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 font-semibold"><Sparkles className="size-3.5 text-primary" /> Sweeping</span>
              <span className="truncate text-panel-muted">Reading {reading?.from}…</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-panel-raised">
              <div className="h-full rounded-full bg-gold" style={{ width: `${progress * 100}%` }} />
            </div>
            <p className="mt-1.5 text-right text-[11px] text-panel-muted">{found} signals found</p>
          </div>
        </div>

        {/* Results layer */}
        <div className={cn("absolute inset-0 transition-all duration-700 ease-out", phase === "scan" && "pointer-events-none translate-y-4 opacity-0")}>
          <div className="px-4 pt-5">
            <p className="text-gold font-display text-5xl tabular-nums">{fmt(count)}</p>
            <p className="text-xs text-panel-muted">3 possible claims · 2 ready, 1 needs review</p>
          </div>
          <ul className="space-y-2 p-4">
            {RESULTS.map((r, i) => (
              <li key={r.ref} className={cn("rounded-xl border border-panel-border bg-panel-raised p-3 transition-all duration-500 ease-out hover:-translate-y-0.5 hover:border-primary/60", phase === "results" ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0")} style={{ transitionDelay: phase === "results" ? `${200 + i * 140}ms` : "0ms" }}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">{r.label}</span>
                  <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", r.tag === "Ready" ? "bg-primary/20 text-primary" : "bg-warning/20 text-warning")}>{r.tag}</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-xs text-panel-muted">
                  <span>{r.bank} · {r.ref}</span>
                  <span className="font-semibold text-panel-foreground">{fmt(r.amount)}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
