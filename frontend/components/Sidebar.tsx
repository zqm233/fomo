"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import {
  Activity,
  BookOpen,
  Database,
  FileText,
  Flame,
  MessageSquare,
  Moon,
  Settings,
  Sun,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { BrandIcon } from "@/lib/brand-icon";

const navItems = [
  { href: "/reports",  label: "投研简报",   icon: FileText },
  { href: "/tickers",  label: "热门股池",   icon: Flame },
  { href: "/articles", label: "文章库",     icon: BookOpen },
  { href: "/chat",     label: "RAG 对话",   icon: MessageSquare },
  { href: "/jobs",     label: "任务队列",   icon: Activity },
  { href: "/sources",  label: "数据源配置", icon: Database },
  { href: "/prompts",  label: "Prompt 管理", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();

  return (
    <aside className="relative z-20 w-56 shrink-0 flex flex-col bg-card border-r border-border">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-4 border-b border-border/40">
        <BrandIcon size={28} className="shrink-0" />
        <span className="text-base font-bold tracking-tight">FOMO</span>
        <span className="text-xs text-muted-foreground ml-auto">美股投研</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "group relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-200",
                active
                  ? "text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {/* Active bg pill */}
              {active && (
                <span className="absolute inset-0 rounded-lg bg-primary/10 ring-1 ring-primary/20" />
              )}
              {/* Hover bg */}
              {!active && (
                <span className="absolute inset-0 rounded-lg bg-muted/0 group-hover:bg-muted/60 transition-colors duration-200" />
              )}
              <Icon className="relative h-4 w-4 shrink-0" />
              <span className="relative">{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer: theme toggle */}
      <div className="px-4 py-3 border-t border-border/40 flex items-center justify-between">
        <p className="text-xs text-muted-foreground"></p>
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="h-7 w-7 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          aria-label="切换主题"
        >
          <Sun className="h-3.5 w-3.5 dark:hidden" />
          <Moon className="h-3.5 w-3.5 hidden dark:block" />
        </button>
      </div>
    </aside>
  );
}
