import { createFileRoute, Link, Outlet } from "@tanstack/react-router";
import { Activity, FileText, LayoutDashboard, PenLine, Sparkles } from "lucide-react";
import { Logo } from "@/components/Logo";

export const Route = createFileRoute("/dashboard")({
  component: DashboardLayout,
});

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/dashboard/claims", label: "Claims", icon: FileText },
  { to: "/dashboard/sweep", label: "Sweep", icon: Sparkles },
  { to: "/dashboard/manual", label: "Manual claim", icon: PenLine },
  { to: "/dashboard/activity", label: "Activity", icon: Activity },
] as const;

function DashboardLayout() {
  return (
    <div className="dark min-h-screen bg-background text-foreground md:flex">
      <aside className="flex shrink-0 flex-col border-sidebar-border bg-sidebar text-sidebar-foreground md:sticky md:top-0 md:h-screen md:w-60 md:border-r">
        <div className="flex items-center justify-between px-5 py-5"><Logo /></div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {NAV.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              activeOptions={{ exact: "exact" in n }}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              activeProps={{ className: "bg-sidebar-accent text-sidebar-accent-foreground" }}
            >
              <n.icon className="size-4" /> {n.label}
            </Link>
          ))}
        </nav>
        <p className="mt-auto hidden px-5 py-5 text-xs text-sidebar-foreground/50 md:block">Read-only · nothing stored after your session</p>
      </aside>
      <div className="flex min-h-screen flex-1 flex-col">
        <main className="flex-1 px-5 py-10 md:px-12"><Outlet /></main>
        <footer className="flex justify-between border-t border-border px-5 py-4 text-xs text-muted-foreground md:px-12">
          <span>© 2026 haq</span><span>Haq doesn't give legal advice. You file every claim.</span>
        </footer>
      </div>
    </div>
  );
}
