import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Inbox, Mail, RotateCcw } from "lucide-react";
import { runDemoSweep } from "@/lib/haq.functions";
import { sweepStore, useSweepState } from "@/lib/sweep-store";
import { API_BASE, claimableCases, claimableTotal, inr, type SweepResult } from "@/lib/haq-types";
import { CaseCard } from "@/components/CaseCard";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/dashboard/sweep")({
  head: () => ({
    meta: [
      { title: "Sweep your inbox — Haq" },
      { name: "description", content: "Run a read-only sweep of your Gmail or a sample inbox to find money you may be owed." },
      { property: "og:title", content: "Sweep your inbox — Haq" },
      { property: "og:description", content: "Find failed payments and overdue dues in your inbox." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: SweepPage,
});

const STAGES = ["Reading inbox headers", "Filtering out promotions and noise", "Spotting debits, failures and invoices", "Grouping related emails into cases", "Matching each case to a rule"];

function SweepPage() {
  const { result } = useSweepState();
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState(0);
  const [pct, setPct] = useState(0);
  const [label, setLabel] = useState("");
  const [notice, setNotice] = useState("");
  const started = useRef(false);

  async function animate(work: Promise<SweepResult>) {
    setRunning(true); setStage(0); setPct(4);
    let s = 0;
    const timer = setInterval(() => { s = Math.min(s + 1, STAGES.length - 1); setStage(s); setPct((p) => Math.min(p + 17, 90)); }, 900);
    try {
      const [data] = await Promise.all([work, new Promise((r) => setTimeout(r, 4200))]);
      sweepStore.setResult(data);
      sweepStore.log(`Sweep finished: ${data.emails_scanned} emails read, ${claimableCases(data.cases).length} possible claims`);
      setPct(100);
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "The sweep failed. Please try again.");
    } finally { clearInterval(timer); setRunning(false); }
  }

  const startDemo = () => { setNotice(""); sweepStore.log("Started a sweep of the sample inbox"); animate(runDemoSweep()); };

  const connectGmail = async () => {
    setNotice("");
    try {
      const r = await fetch(`${API_BASE}/v1/gmail/auth-url`, { credentials: "include" });
      const auth = await r.json();
      if (!auth.client_id_configured) throw new Error("not configured");
      window.location.href = auth.auth_url;
    } catch {
      setNotice("Gmail sign-in isn't available from this site yet. Try the sample inbox for now.");
    }
  };

  // Returning from Google sign-in: run a live sweep on the connected inbox.
  useEffect(() => {
    if (started.current) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("gmail") === "denied") setNotice("Google access was not granted. Nothing was scanned.");
    if (params.get("gmail") === "error") setNotice("Gmail could not be connected. Nothing was scanned — please try again.");
    if (params.get("gmail") !== "connected") return;
    started.current = true;
    window.history.replaceState({}, "", window.location.pathname);
    sweepStore.log("Connected Gmail and started a live sweep");
    animate(liveSweep(setLabel));
  }, []);

  if (running) {
    return (
      <div className="mx-auto max-w-xl pt-10 text-center">
        <div className="relative mx-auto grid size-24 place-items-center overflow-hidden rounded-3xl border border-border bg-card">
          <Mail className="size-9 text-primary" />
          <span className="animate-scanline absolute inset-x-0 h-0.5 bg-primary shadow-[0_0_16px_var(--primary)]" />
        </div>
        <h1 className="mt-8 font-display text-4xl">Sweeping your inbox…</h1>
        <p className="mt-2 text-sm text-muted-foreground">{label || STAGES[stage]}</p>
        <div className="mt-6 h-2 overflow-hidden rounded-full bg-secondary"><div className="h-full rounded-full bg-primary transition-all duration-700" style={{ width: `${pct}%` }} /></div>
        <ul className="mt-8 space-y-2 text-left text-sm">
          {STAGES.map((s, i) => <li key={s} className={cn("flex items-center gap-3 transition-opacity", i > stage && "opacity-30")}><span className={cn("size-2 rounded-full", i < stage ? "bg-primary" : i === stage ? "animate-pulse bg-primary" : "bg-muted-foreground")} />{s}</li>)}
        </ul>
      </div>
    );
  }

  if (result) {
    const packs = result.claim_packs ?? [];
    return (
      <div className="mx-auto max-w-3xl">
        {notice && <Notice text={notice} />}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Possibly owed to you</p>
            <p className="font-display text-6xl">{inr(claimableTotal(result.cases))}</p>
            <p className="mt-1 text-sm text-muted-foreground">{claimableCases(result.cases).length} possible claims from {result.emails_scanned} emails</p>
          </div>
          <button onClick={() => sweepStore.clear()} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-secondary"><RotateCcw className="size-4" />New sweep</button>
        </div>
        <div className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[["Emails read", result.emails_scanned], ["Noise filtered", result.noise_filtered], ["Money signals", result.financial_alerts_found], ["Possible issues", result.violations_detected]].map(([k, v]) => (
            <div key={k} className="rounded-xl border border-border bg-card p-4"><p className="font-display text-3xl">{v}</p><p className="text-xs text-muted-foreground">{k}</p></div>
          ))}
        </div>
        <h2 className="mt-10 text-lg font-semibold">Cases</h2>
        <div className="mt-4 space-y-3">
          {(result.cases ?? []).map((c) => <CaseCard key={c.case_id} c={c} pack={packs.find((p) => p.case_id === c.case_id)} />)}
          {!result.cases?.length && <p className="text-sm text-muted-foreground">No claimable cases found in this inbox.</p>}
        </div>
        <Link to="/dashboard/claims" className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-primary">Go to my claims <ArrowRight className="size-4" /></Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl">
      {notice && <Notice text={notice} />}
      <h1 className="font-display text-5xl">See what's hiding in your inbox.</h1>
      <p className="mt-4 text-muted-foreground">Haq asks Google for read-only access, scans only for payment and dues signals, and keeps nothing after your session.</p>
      <div className="mt-8 space-y-3">
        <button onClick={connectGmail} className="flex w-full items-center justify-between rounded-2xl bg-primary p-5 text-left text-primary-foreground hover:opacity-90">
          <span className="flex items-center gap-3"><Mail className="size-5" /><span><span className="block font-semibold">Connect Gmail</span><span className="text-xs opacity-80">Read-only · revoke anytime</span></span></span><ArrowRight className="size-5" />
        </button>
        <button onClick={startDemo} className="flex w-full items-center justify-between rounded-2xl border border-border bg-card p-5 text-left hover:border-primary/50">
          <span className="flex items-center gap-3"><Inbox className="size-5 text-primary" /><span><span className="block font-semibold">Try the sample inbox</span><span className="text-xs text-muted-foreground">No sign-in · see how a sweep works</span></span></span><ArrowRight className="size-5" />
        </button>
      </div>
    </div>
  );
}

function Notice({ text }: { text: string }) {
  return <div className="mb-6 rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm">{text}</div>;
}

async function liveSweep(onLabel: (l: string) => void): Promise<SweepResult> {
  const req = async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const r = await fetch(`${API_BASE}${path}`, { ...init, credentials: "include", headers: { "Content-Type": "application/json" } });
    if (!r.ok) throw new Error(`The sweep stopped (${r.status}). Nothing was saved — start a new sweep.`);
    return r.json();
  };
  const job = await req<{ job_id: string }>("/v1/gmail/sweeps", { method: "POST", body: JSON.stringify({ max_results: 500 }) });
  for (;;) {
    await new Promise((r) => setTimeout(r, 600));
    const j = await req<{ state: string; stage?: string; listed: number; triaged: number; analysed: number; relevant: number; not_analysed: number; result?: SweepResult; error?: string }>(`/v1/gmail/sweeps/${job.job_id}`);
    onLabel(`${j.stage || "Scanning"} · ${j.listed} found · ${j.analysed} checked`);
    if (j.state === "done" && j.result) return { ...j.result, coverage: { listed: j.listed, triaged: j.triaged, analysed: j.analysed, relevant: j.relevant, not_analysed: j.not_analysed } };
    if (["failed", "expired", "cancelled"].includes(j.state)) throw new Error(j.error || `The sweep ${j.state}. Nothing was saved — start a new sweep.`);
  }
}
