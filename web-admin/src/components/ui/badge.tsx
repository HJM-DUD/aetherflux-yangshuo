import { AlertTriangle } from "lucide-react";
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/utils";

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  icon?: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
};

export function Badge({ children, className, icon, tone = "neutral", ...props }: BadgeProps) {
  const tones = {
    neutral: "bg-slate-100 text-slate-800 shadow-sm dark:bg-slate-800 dark:text-slate-100",
    success: "bg-emerald-600 text-white shadow-sm dark:bg-emerald-500 dark:text-white",
    warning: "bg-white text-red-500 shadow-sm dark:bg-slate-950 dark:text-red-400",
    danger: "bg-white text-red-500 shadow-sm dark:bg-slate-950 dark:text-red-400",
    info: "bg-primary text-primary-foreground shadow-sm"
  };
  const leadingIcon = icon || (tone === "warning" ? <AlertTriangle className="h-3.5 w-3.5" /> : null);
  return (
    <span
      className={cn("inline-flex min-h-7 items-center gap-1.5 rounded-md px-2.5 text-xs font-semibold", tones[tone], className)}
      {...props}
    >
      {leadingIcon}
      {children}
    </span>
  );
}
