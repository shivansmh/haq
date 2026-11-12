import { createFileRoute, Link } from "@tanstack/react-router";
import { useSweepState } from "@/lib/sweep-store";
import { CaseCard } from "@/components/CaseCard";
import { RecordCard, RecordSummaryStrip } from "@/components/RecordCard";
import { ledgerRecords, ledgerSummary } from "@/lib/haq-types";

export const Route = createFileRoute("/dashboard/claims")({
  head: () => ({
    meta: [
      { title: "Records & claims — Haq" },
      {
        name: "description",
        content: "Review tracked money records, evidence, and claim drafts found by Haq.",
      },
      { property: "og:title", content: "Records & claims — Haq" },
      {
        property: "og:description",
        content: "Review tracked money records, evidence, and claim drafts found by Haq.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Claims,
});

function Claims() {
  const { result } = useSweepState();
  const packs = result?.claim_packs ?? [];
  const records = ledgerRecords(result);
  const cases = result?.cases ?? [];
  const summary = ledgerSummary(result);
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="font-display text-5xl">Records & claims</h1>
      {!records.length && !cases.length ? (
        <p className="mt-6 text-muted-foreground">
          No claims yet.{" "}
          <Link to="/dashboard/sweep" className="font-semibold text-primary">
            Run a sweep
          </Link>{" "}
          to find some.
        </p>
      ) : (
        <>
          <p className="mt-3 text-sm text-muted-foreground">
            Every flagged transaction keeps its own record. A refund seen in a later sweep updates
            the same record instead of creating a second claim.
          </p>
          <div className="mt-6">
            <RecordSummaryStrip summary={summary} />
          </div>
          <h2 className="mt-10 text-lg font-semibold">Tracked records</h2>
          <div className="mt-4 space-y-3">
            {records.map((record) => (
              <RecordCard key={record.record_id} record={record} />
            ))}
            {!records.length && (
              <p className="text-sm text-muted-foreground">No structured records in this sweep.</p>
            )}
          </div>
          {!!cases.length && (
            <>
              <h2 className="mt-10 text-lg font-semibold">Claim drafts</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Evidence-first drafts. They never promise a compensation amount for an unverified
                rule.
              </p>
              <div className="mt-4 space-y-3">
                {cases.map((c) => (
                  <CaseCard
                    key={c.case_id}
                    c={c}
                    pack={packs.find((p) => p.case_id === c.case_id)}
                  />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
