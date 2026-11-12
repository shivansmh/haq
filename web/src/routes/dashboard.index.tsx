import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Check, ClipboardList, Eye, Search, ShieldCheck, Sparkles, Undo2 } from "lucide-react";
import { useSweepState } from "@/lib/sweep-store";
import { claimableCases, claimableTotal, inr } from "@/lib/haq-types";

export const Route = createFileRoute("/dashboard/")({
  head: () => ({
    meta: [
      { title: "Dashboard — Haq" },
      { name: "description", content: "Start a Haq inbox sweep or file a claim manually." },
      { property: "og:title", content: "Dashboard — Haq" },
      { property: "og:description", content: "Start a Haq inbox sweep or file a claim manually." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Start,
});

function Start() {
  const { result } = useSweepState();
  const cases = claimableCases(result?.cases);
  return (
    <div className="mx-auto max-w-2xl">
      {result && (
        <Link to="/dashboard/claims" className="mb-8 flex items-center justify-between rounded-2xl border border-border bg-card p-5 hover:border-primary/50">
          <div><p className="text-xs text-muted-foreground">From your last sweep</p><p className="font-display text-3xl">{inr(claimableTotal(result.cases))}</p><p className="text-sm text-muted-foreground">{cases.length} possible claims</p></div>
          <ArrowRight className="size-5 text-primary" />
        </Link>
      )}
      <h1 className="text-2xl font-semibold md:text-3xl">How would you like to find your money?</h1>
      <div className="mt-8 rounded-2xl border border-primary/40 bg-accent/40 p-6">
        <div className="flex items-start gap-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground"><Sparkles className="size-5" /></span>
          <div>
            <p className="flex items-center gap-2 font-semibold">Sweep <span className="rounded-full bg-primary/20 px-2 py-0.5 text-[10px] font-semibold text-primary">Recommended</span></p>
            <p className="text-sm text-muted-foreground">Scan your Gmail for failed payments and overdue dues automatically.</p>
          </div>
        </div>
        <ul className="mt-5 space-y-2 text-sm">
          {["Uncover money stuck in failed transactions", "No manual entry needed", "Read-only Gmail access"].map((t) => <li key={t} className="flex items-center gap-2"><Check className="size-4 text-primary" />{t}</li>)}
        </ul>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <a href="#privacy" className="text-xs text-muted-foreground underline-offset-4 hover:underline">How we protect your privacy</a>
          <Link to="/dashboard/sweep" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:opacity-90">Scan my inbox <ArrowRight className="size-4" /></Link>
        </div>
      </div>
      <div id="privacy" className="mt-5 flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5"><Eye className="size-3.5" />Read only</span>
        <span className="flex items-center gap-1.5"><Undo2 className="size-3.5" />Revoke anytime</span>
        <span className="flex items-center gap-1.5"><Search className="size-3.5" />Payment emails only</span>
        <span className="flex items-center gap-1.5"><ShieldCheck className="size-3.5" />Nothing stored</span>
      </div>
      <div className="my-8 flex items-center gap-4 text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />OR<span className="h-px flex-1 bg-border" /></div>
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5">
        <div className="flex items-center gap-3"><ClipboardList className="size-5 text-muted-foreground" /><div><p className="font-semibold">Manual claim</p><p className="text-xs text-muted-foreground">No email access · enter the details yourself</p></div></div>
        <Link to="/dashboard/manual" className="rounded-lg border border-border px-4 py-2 text-sm font-semibold hover:bg-secondary">Continue manually</Link>
      </div>
    </div>
  );
}
