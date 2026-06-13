"use client";

import { cn } from "@/lib/utils";
import {
  Activity,
  BarChart3,
  FileCheck2,
  LayoutDashboard,
  LogOut,
  Settings,
  Shield,
  Upload,
  Zap,
} from "lucide-react";
import { signOut } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/upload", icon: Upload, label: "Upload Docs" },
  { href: "/batches", icon: FileCheck2, label: "Declarations" },
  { href: "/analytics", icon: BarChart3, label: "Analytics" },
  { href: "/simulator", icon: Activity, label: "Simulator" },
  { href: "/audit", icon: Shield, label: "Audit Trail" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 flex-col border-r border-white/10 bg-card/50 backdrop-blur-xl">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-white/10">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/20 ring-1 ring-primary/30">
          <Zap className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="font-bold text-sm gradient-text">TradeFlow AI</p>
          <p className="text-[10px] text-muted-foreground">Customs Intelligence</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto scrollbar-hidden px-3 py-4 space-y-1">
        {navItems.map(({ href, icon: Icon, label }) => (
          <Link key={href} href={href} className={cn("nav-item", pathname === href && "active")}>
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </Link>
        ))}
      </nav>

      {/* User footer */}
      <div className="border-t border-white/10 p-4">
        <div className="flex items-center gap-3 rounded-xl bg-white/5 px-3 py-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-primary text-xs font-bold">
            DO
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium truncate">Dev Operator</p>
            <p className="text-[10px] text-muted-foreground truncate">operator@tradeflow.local</p>
          </div>
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/" })}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
