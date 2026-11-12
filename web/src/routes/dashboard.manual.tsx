import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, Loader2, Scale } from "lucide-react";
import { classifyClaim, type Classification } from "@/lib/haq.functions";
import { sweepStore } from "@/lib/sweep-store";

export const Route = createFileRoute("/dashboard/manual")({
  head: () => ({ meta: [
    { title: "Manual claim — Haq" },
    { name: "description", content: "Describe a failed payment or overdue due in your own words and Haq finds the rule that applies." },
    { property: "og:title", content: "Manual claim — Haq" },
    { property: "og:description", content: "Describe your problem and Haq finds the rule that applies." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  component: Manual,
});

const EXAMPLES = [
  "I paid ₹2,000 by UPI to Swiggy on 3 March, the payment failed but my HDFC account was debited.",
  "SBI ATM didn't give me ₹5,000 cash but my account was charged last week.",
  "A buyer hasn't paid my MSME invoice of ₹1,42,800 for 61 days.",
];
const CATEGORY: Record<Classification["category"], string> = {
  failed_payment: "Failed payment", msme_dues: "Overdue MSME dues", unclaimed_wealth: "Unclaimed money", general_rights: "General consumer right",
};

const ROUTES: Record<string, string> = { payment_flow: "Your bank first, then the RBI Ombudsman", msme_flow: "Buyer demand notice, then MSME Samadhaan", unclaimed_flow: "The holding institution or IEPF / RBI UDGAM" };

function Manual() {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState<Classification | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError(""); setRes(null);
    try {
      const r = await classifyClaim({ prompt });
      setRes(r); sweepStore.log(`Manual claim checked: ${CATEGORY[r.category] ?? r.category}`);
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong."); }
    finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-5xl">Manual claim</h1>
      <p className="mt-2 text-muted-foreground">Tell us what happened, in your own words. No email access needed.</p>
      <form onSubmit={submit} className="mt-8 space-y-3">
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={5} maxLength={4000} placeholder="What happened, when, how much, and which bank or business?" className="w-full rounded-2xl border border-input bg-card p-4 text-sm outline-none focus:border-primary" />
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((x) => <button type="button" key={x} onClick={() => setPrompt(x)} className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:border-primary/60 hover:text-foreground">{x.slice(0, 38)}…</button>)}
        </div>
        <button disabled={busy || prompt.trim().length < 10} className="inline-flex items-center gap-2 rounded-lg bg-gold px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50">
          {busy ? <Loader2 className="size-4 animate-spin" /> : <Scale className="size-4" />}{busy ? "Checking the rules…" : "Find my right"}
        </button>
      </form>
      {error && <p className="mt-6 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">{error}</p>}
      {res && (
        <div className="animate-rise mt-8 rounded-2xl border border-primary/40 bg-card p-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-primary/20 px-2 py-0.5 text-[10px] font-semibold text-primary">{CATEGORY[res.category] ?? res.category}</span>
            <span className="text-xs text-muted-foreground">{Math.round(res.confidence * 100)}% match</span>
          </div>
          <h2 className="mt-3 text-xl font-semibold">{res.title}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{res.summary}</p>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2 text-sm">
            <div><dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">The rule</dt><dd className="mt-1">{res.statutory_law}</dd></div>
            <div><dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Where to go</dt><dd className="mt-1">{ROUTES[res.suggested_route] ?? res.suggested_route.replace(/_/g, " ")}</dd></div>
          </dl>
          {Object.keys(res.extracted_entities ?? {}).length > 0 && (
            <div className="mt-5 flex flex-wrap gap-2">{Object.entries(res.extracted_entities).filter(([k, v]) => v != null && v !== "" && k !== "amount_paise").map(([k, v]) => <span key={k} className="rounded-md bg-secondary px-2 py-1 text-xs"><span className="text-muted-foreground">{k.replace(/_/g, " ")}:</span> {String(v)}</span>)}</div>
          )}
          <p className="mt-5 text-xs text-muted-foreground">This isn't legal advice. Want the emails as evidence? <Link to="/dashboard/sweep" className="inline-flex items-center gap-1 font-semibold text-primary">Run a sweep <ArrowRight className="size-3" /></Link></p>
        </div>
      )}
    </div>
  );
}
