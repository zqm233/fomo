"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart2,
  Database,
  History,
  MessageSquare,
  Settings,
  Sun,
  Sunset,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/pre-market", label: "盘前简讯", icon: Sun },
  { href: "/post-market", label: "盘后复盘", icon: Sunset },
  { href: "/chat", label: "RAG 对话", icon: MessageSquare },
  { href: "/history", label: "历史简报", icon: History },
  { href: "/sources", label: "数据源配置", icon: Database },
  { href: "/prompts", label: "Prompt 管理", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-card flex flex-col">
      <div className="flex items-center gap-2 px-5 py-4 border-b border-border">
        <TrendingUp className="h-6 w-6 text-primary" />
        <span className="text-lg font-bold tracking-tight text-foreground">FOMO</span>
        <span className="text-xs text-muted-foreground ml-auto">美股投研</span>
      </div>

      <nav className="flex-1 py-3 px-2 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                active
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 py-3 border-t border-border">
        <p className="text-xs text-muted-foreground">
          AI 驱动 · 美东时区自动运行
        </p>
      </div>
    </aside>
  );
}
