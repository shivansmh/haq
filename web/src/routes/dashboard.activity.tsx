import { createFileRoute } from "@tanstack/react-router";
import { useSweepState } from "@/lib/sweep-store";

export const Route = createFileRoute("/dashboard/activity")({
  head: () => ({ meta: [
    { title: "Activity — Haq" },
    { name: "description", content: "Your recent Haq sweeps this session." },
    { property: "og:title", content: "Activity — Haq" },
    { property: "og:description", content: "Your recent Haq sweeps this session." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  component: ActivityPage,
});

function ActivityPage() {
  const { activity } = useSweepState();
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-5xl">Activity</h1>
      {activity.length === 0 ? <p className="mt-6 text-muted-foreground">Nothing yet this session.</p> : (
        <ul className="mt-8 divide-y divide-border border-y border-border">
          {activity.map((a) => <li key={a.at + a.text} className="flex justify-between gap-4 py-4 text-sm"><span>{a.text}</span><span className="shrink-0 text-muted-foreground">{new Date(a.at).toLocaleTimeString()}</span></li>)}
        </ul>
      )}
    </div>
  );
}
