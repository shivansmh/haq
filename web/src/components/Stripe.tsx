import { cn } from "@/lib/utils";

/** Tilted gold ticker strip, like event-poster tape. */
export function Stripe({ items, reverse, tilt = "-rotate-2", className }: { items: string[]; reverse?: boolean; tilt?: string; className?: string }) {
  const row = [...items, ...items, ...items];
  return (
    <div className={cn("relative z-10 -mx-4 overflow-hidden border-y-2 border-primary-foreground bg-gold py-2.5 text-primary-foreground shadow-panel", tilt, className)} aria-hidden>
      <div className={cn("flex w-max gap-6 whitespace-nowrap font-stripe text-lg uppercase tracking-wide md:text-2xl", reverse ? "animate-marquee-reverse" : "animate-marquee")}>
        {[0, 1].map((k) => (
          <span key={k} className="flex gap-6">
            {row.map((t, i) => <span key={i} className="flex items-center gap-6">{t}<span>✳</span></span>)}
          </span>
        ))}
      </div>
    </div>
  );
}
