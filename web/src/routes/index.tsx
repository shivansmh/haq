import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, ChevronDown, FileText, Inbox, Lock, Scale, ShieldCheck } from "lucide-react";
import { Logo } from "@/components/Logo";
import { SweepVisual } from "@/components/SweepVisual";
import { Stripe } from "@/components/Stripe";
import { useEffect } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Haq — Money stuck? Sweep your inbox and claim it back" },
      { name: "description", content: "Haq reads your Gmail (read-only) for failed UPI payments, ATM errors and overdue invoices, then prepares a claim you file yourself." },
      { property: "og:title", content: "Haq — Sweep your inbox and claim it back" },
      { property: "og:description", content: "Find failed payments and overdue dues hiding in your inbox, with the rule and evidence for each." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Home,
});

const STEPS = [
  { icon: Inbox, title: "Sweep", text: "Connect Gmail with read-only access, or try the sample inbox. Haq only looks for payment and dues signals." },
  { icon: Scale, title: "Match", text: "Each signal is matched to a specific rule — RBI turnaround times, the MSMED Act — with its source shown." },
  { icon: FileText, title: "Claim", text: "Get a ready-to-send draft, evidence checklist and escalation path. You file it; nothing is sent for you." },
];

const RIGHTS = [
  { title: "Failed UPI & card payments", source: "RBI turnaround-time framework", detail: "Money left your account but the payment failed and wasn't reversed in time." },
  { title: "ATM cash not dispensed", source: "RBI TAT · ATM reversals", detail: "Your account was debited but the machine didn't give you the cash." },
  { title: "Overdue MSME invoices", source: "MSMED Act · Sections 15 & 16", detail: "A buyer has held your registered-MSME invoice past 45 days." },
];

const FAQ = [
  { q: "What does Gmail access mean?", a: "Google shows you its own consent screen. Haq asks for read-only access, scans only for payment and dues signals, and doesn't keep your email after the session. You can revoke access at any time." },
  { q: "Does Haq file the claim for me?", a: "No. Haq prepares the draft, the evidence list and who to escalate to. You review it and send it yourself." },
  { q: "Are the amounts guaranteed?", a: "No. Where a rule isn't fully verified yet, Haq shows the evidence without claiming a deadline or compensation figure." },
  { q: "Can I try it without connecting Gmail?", a: "Yes — run the sweep on the sample inbox to see exactly how it works." },
];

function Home() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const gmail = params.get("gmail");
    if (!gmail) return;
    const query = new URLSearchParams({ gmail });
    const reason = params.get("reason");
    if (reason) query.set("reason", reason);
    const base = window.location.pathname.replace(/\/$/, "");
    window.location.replace(`${base}/dashboard/sweep?${query.toString()}`);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Logo />
          <nav className="hidden gap-7 text-sm font-medium text-muted-foreground md:flex">
            <a href="#how" className="hover:text-foreground">How it works</a>
            <a href="#rights" className="hover:text-foreground">What we find</a>
            <a href="#faq" className="hover:text-foreground">FAQs</a>
          </nav>
          <div className="flex items-center gap-3 text-sm">
            <Link to="/dashboard" className="hidden font-medium text-muted-foreground hover:text-foreground sm:block">Dashboard</Link>
            <Link to="/dashboard" className="rounded-full bg-foreground px-4 py-2 font-semibold text-background hover:opacity-90">Start your claim</Link>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden bg-hero text-hero-foreground">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 md:grid-cols-[1.1fr_1fr] md:py-24">
          <div>
            <Link to="/dashboard/sweep" className="inline-flex items-center gap-2 rounded-full bg-hero-foreground/15 px-3 py-1 text-xs font-semibold">
              Sweep is live — find money stuck in failed payments <span className="opacity-80">Try it →</span>
            </Link>
            <h1 className="mt-6 font-display text-5xl leading-[1.02] md:text-7xl">Money stuck? Sweep your inbox and <span className="italic text-panel">claim it back.</span></h1>
            <p className="mt-6 max-w-lg text-base leading-relaxed opacity-90 md:text-lg">
              Haq finds failed UPI payments, ATM errors and overdue invoices in your email, checks them against the rule, and drafts the claim so you don't have to fight the bank alone.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-5">
              <Link to="/dashboard" className="inline-flex items-center gap-2 rounded-full bg-hero-foreground px-5 py-3 text-sm font-semibold text-foreground shadow-sm hover:opacity-90">
                Check my inbox <ArrowRight className="size-4" />
              </Link>
              <a href="#how" className="text-sm font-semibold underline-offset-4 hover:underline">See how it works</a>
            </div>
          </div>
          <div className="flex justify-center md:justify-end"><SweepVisual /></div>
        </div>
      </section>

      <Stripe items={["Failed UPI refunds", "ATM cash not dispensed", "MSME dues past 45 days", "Read-only Gmail"]} />

      <section id="how" className="mx-auto max-w-6xl px-5 py-20">
        <p className="text-sm font-semibold text-primary">A simple sweep</p>
        <h2 className="mt-2 max-w-xl font-display text-4xl md:text-5xl">From inbox noise to a clear next step.</h2>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <div key={s.title} className="rounded-2xl border border-border bg-card p-6">
              <div className="flex items-center justify-between">
                <span className="grid size-10 place-items-center rounded-xl bg-accent text-primary"><s.icon className="size-5" /></span>
                <span className="font-display text-2xl text-muted-foreground">0{i + 1}</span>
              </div>
              <h3 className="mt-5 text-lg font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="rights" className="bg-panel text-panel-foreground">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-20 md:grid-cols-[1fr_1.4fr]">
          <div>
            <p className="text-sm font-semibold text-primary">What Haq looks for</p>
            <h2 className="mt-2 font-display text-4xl md:text-5xl">Specific rules. Visible sources.</h2>
            <p className="mt-4 text-panel-muted">Haq never turns a guess into a confident number. Every finding shows the email it came from.</p>
          </div>
          <ul className="divide-y divide-panel-border border-y border-panel-border">
            {RIGHTS.map((r) => (
              <li key={r.title} className="grid gap-1 py-6 md:grid-cols-[1fr_1.2fr] md:gap-6">
                <div><h3 className="text-lg font-semibold">{r.title}</h3><p className="text-xs text-primary">{r.source}</p></div>
                <p className="text-sm text-panel-muted">{r.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <Stripe reverse tilt="rotate-1" items={["You file every claim", "Nothing stored", "Sources shown", "Built for India"]} />

      <section className="mx-auto grid max-w-6xl gap-4 px-5 py-16 md:grid-cols-3">
        {[{ i: Lock, t: "Read-only Gmail", d: "Haq can't send, delete or change anything." }, { i: ShieldCheck, t: "Nothing stored", d: "Email content is processed during your session only." }, { i: FileText, t: "You stay in control", d: "You review and file every claim yourself." }].map((x) => (
          <div key={x.t} className="flex gap-3"><x.i className="mt-0.5 size-5 text-primary" /><div><p className="font-semibold">{x.t}</p><p className="text-sm text-muted-foreground">{x.d}</p></div></div>
        ))}
      </section>

      <section id="faq" className="mx-auto max-w-3xl px-5 pb-24">
        <h2 className="font-display text-4xl">Questions, answered plainly</h2>
        <div className="mt-8 divide-y divide-border border-y border-border">
          {FAQ.map((f) => (
            <details key={f.q} className="group py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between font-semibold">{f.q}<ChevronDown className="size-4 transition-transform group-open:rotate-180" /></summary>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
            </details>
          ))}
        </div>
        <div className="mt-14 rounded-2xl bg-hero p-8 text-hero-foreground md:p-10">
          <h3 className="font-display text-3xl md:text-4xl">See what's hiding in your inbox.</h3>
          <Link to="/dashboard/sweep" className="mt-6 inline-flex items-center gap-2 rounded-full bg-hero-foreground px-5 py-3 text-sm font-semibold text-foreground">Run a sweep <ArrowRight className="size-4" /></Link>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-8 text-sm text-muted-foreground">
          <Logo className="text-foreground" />
          <p>Built for India · privacy first · you file every claim</p>
          <p>© 2026 haq</p>
        </div>
      </footer>
    </div>
  );
}
