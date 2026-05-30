import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "../../lib/utils";

type PaginationProps = {
  current: number;
  total: number;
  onPageChange: (page: number) => void;
  className?: string;
};

export function Pagination({ current, total, onPageChange, className }: PaginationProps) {
  if (total <= 1) return null;

  const pages = buildPages(current, total);

  return (
    <nav className={cn("flex items-center gap-1", className)} aria-label="分页">
      <PageButton
        disabled={current <= 1}
        onClick={() => onPageChange(current - 1)}
        aria-label="上一页"
      >
        <ChevronLeft className="h-4 w-4" />
      </PageButton>

      {pages.map((page, i) => {
        if (page === "...") {
          return (
            <span key={`ellipsis-${i}`} className="px-2 text-xs text-muted-foreground">
              …
            </span>
          );
        }
        const num = Number(page);
        return (
          <PageButton
            key={num}
            active={num === current}
            onClick={() => onPageChange(num)}
            aria-label={`第 ${num} 页`}
            aria-current={num === current ? "page" : undefined}
          >
            {num}
          </PageButton>
        );
      })}

      <PageButton
        disabled={current >= total}
        onClick={() => onPageChange(current + 1)}
        aria-label="下一页"
      >
        <ChevronRight className="h-4 w-4" />
      </PageButton>
    </nav>
  );
}

function PageButton({
  active,
  disabled,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      disabled={disabled}
      className={cn(
        "inline-flex h-9 min-w-[2.25rem] items-center justify-center rounded-md px-2 text-sm font-medium transition",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
        "disabled:pointer-events-none disabled:opacity-50",
        active
          ? "bg-primary text-primary-foreground shadow-sm"
          : "text-foreground hover:bg-muted",
        className,
      )}
      {...props}
    />
  );
}

function buildPages(current: number, total: number): (string | number)[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages: (string | number)[] = [1];

  if (current > 3) pages.push("...");

  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (current < total - 2) pages.push("...");

  pages.push(total);
  return pages;
}
