import { cn } from "../../lib/utils";

type SeparatorProps = {
  orientation?: "horizontal" | "vertical";
  className?: string;
  label?: string;
};

export function Separator({ orientation = "horizontal", className, label }: SeparatorProps) {
  if (label) {
    return (
      <div className={cn("flex items-center gap-3", className)}>
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="h-px flex-1 bg-border" />
      </div>
    );
  }

  if (orientation === "vertical") {
    return <div className={cn("h-full w-px shrink-0 bg-border", className)} />;
  }

  return <div className={cn("h-px w-full shrink-0 bg-border", className)} />;
}
