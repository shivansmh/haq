import { createFileRoute, Link } from "@tanstack/react-router";
import { useSweepState } from "@/lib/sweep-store";
import { CaseCard } from "@/components/CaseCard";

export const Route = createFileRoute("/dashboard/claims")({
  head: () => ({ meta: [
    { title: "My claims — Haq" },
    { name: "description", content: "Review possible claims found by your Haq sweep." },
    { property: "og:title", content: "My claims — Haq" },
    { property: "og:description", content: "Review possible claims found by your Haq sweep." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  component: Claims,
});

function Claims() {
  const { result } = useSweepState();
  const packs = result?.claim_packs ?? [];
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display text-5xl">My claims</h1>
      {!result?.cases?.length ? (
        <p className="mt-6 text-muted-foreground">No claims yet. <Link to="/dashboard/sweep" className="font-semibold text-primary">Run a sweep</Link> to find some.</p>
      ) : (
        <div className="mt-8 space-y-3">{result.cases.map((c) => <CaseCard key={c.case_id} c={c} pack={packs.find((p) => p.case_id === c.case_id)} />)}</div>
      )}
    </div>
  );
}
