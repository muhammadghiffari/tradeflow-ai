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
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
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
    <aside className="flex h-screen w-64 flex-col border-r border-white/5 bg-slate-950/80 backdrop-blur-xl">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-white/5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-500/20 ring-1 ring-cyan-500/30 shadow-lg shadow-cyan-500/10">
          <Zap className="h-5 w-5 text-cyan-400" />
        </div>
        <div>
          <p className="font-bold text-sm bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">TradeFlow AI</p>
          <p className="text-[10px] text-slate-500 font-medium tracking-wide uppercase">Customs Intelligence</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto scrollbar-hidden px-3 py-4 space-y-1">
        {navItems.map(({ href, icon: Icon, label }) => {
          const isActive = href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(href);
          return (
            <Link key={href} href={href} className={cn("nav-item transition-all duration-200 hover:scale-[1.01] active:scale-[0.99]", isActive && "active")}>
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User footer */}
      <div className="border-t border-white/5 p-4">
        <div className="flex items-center gap-3 rounded-xl bg-white/[0.03] border border-white/5 px-3 py-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-500/20 text-cyan-400 text-xs font-bold ring-1 ring-cyan-500/30">
            DO
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold truncate text-slate-200">Dev Operator</p>
            <p className="text-[10px] text-slate-500 truncate">operator@tradeflow.local</p>
          </div>
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/" })}
            className="text-slate-400 hover:text-red-400 transition-colors p-1 rounded-lg hover:bg-red-500/10"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}
