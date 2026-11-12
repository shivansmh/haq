import { useState } from "react";
import { Check, ChevronDown, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { claimLabel, inr, STATUS_LABELS, type Case, type ClaimPack } from "@/lib/haq-types";

export function CaseCard({ c, pack }: { c: Case; pack?: ClaimPack | undefined }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const resolved = c.status === "resolved_on_time";
  const copy = async () => { if (!pack) return; await navigator.clipboard.writeText(pack.draft); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  return (
    <div className={cn("rounded-2xl border border-border bg-card", resolved && "opacity-70")}>
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-4 p-5 text-left">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">{claimLabel(c.claim_type)}</p>
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", resolved ? "bg-secondary text-muted-foreground" : "bg-primary/20 text-primary")}>{STATUS_LABELS[c.status]}</span>
            <span className="rounded-full bg-warning/15 px-2 py-0.5 text-[10px] font-semibold text-warning">Rule {c.rule_id ?? "—"} · {c.rule_status}</span>
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground">Ref {c.reference ?? "not found"} · {c.events.length} email{c.events.length > 1 ? "s" : ""}</p>
        </div>
        <p className="font-display text-2xl">{inr(c.amount_paise)}</p>
        <ChevronDown className={cn("size-4 shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="animate-rise space-y-5 border-t border-border p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Evidence from your inbox</p>
            <ul className="mt-2 space-y-2">
              {c.events.map((e) => (
                <li key={e.event_id} className="rounded-lg bg-secondary p-3 text-sm">
                  {e.subject && <p className="font-medium">{e.subject}</p>}
                  <p className="mt-1 text-xs text-muted-foreground">“{e.quote}”</p>
                </li>
              ))}
            </ul>
          </div>
          {c.rule_status !== "Verified" && <p className="text-xs text-muted-foreground">This rule isn't fully verified yet, so Haq shows the evidence without claiming a deadline or compensation amount.</p>}
          {pack && (
            <>
              <div>
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Draft message</p>
                  <button onClick={copy} className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs font-semibold hover:bg-secondary">{copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{copied ? "Copied" : "Copy"}</button>
                </div>
                <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-secondary p-4 font-sans text-sm">{pack.draft}</pre>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Evidence checklist</p><ul className="mt-2 space-y-1 text-sm">{pack.evidence_checklist.map((x) => <li key={x} className="flex gap-2"><Check className="mt-0.5 size-3.5 text-primary" />{x}</li>)}</ul></div>
                <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">If they don't respond</p><ol className="mt-2 space-y-1 text-sm">{pack.escalation.map((x, i) => <li key={x}>{i + 1}. {x}</li>)}</ol></div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
