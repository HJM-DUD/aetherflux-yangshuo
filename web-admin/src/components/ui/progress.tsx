import { cn } from "../../lib/utils";

type ProgressProps = {
  value: number; // 0–100
  className?: string;
  indicatorClassName?: string;
  showLabel?: boolean;
};

export function Progress({ value, className, indicatorClassName, showLabel = false }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value));

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          role="progressbar"
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={100}
          className={cn(
            "h-full rounded-full transition-all duration-500 ease-out",
            "bg-[hsl(var(--analysis,158,72%,52%))]",
            indicatorClassName,
          )}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-bold tabular-nums text-muted-foreground min-w-[3ch] text-right">
          {Math.round(clamped)}%
        </span>
      )}
    </div>
  );
}
