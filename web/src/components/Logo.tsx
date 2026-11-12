import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn("flex items-center gap-2 font-semibold", className)}>
      <span className="grid size-7 place-items-center rounded-lg bg-gold font-display text-lg text-primary-foreground">h</span>
      <span className="text-lg tracking-tight">haq</span>
    </Link>
  );
}
