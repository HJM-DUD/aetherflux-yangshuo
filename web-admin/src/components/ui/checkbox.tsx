import { Check } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

type CheckboxProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> & {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
};

export function Checkbox({ className, checked, onCheckedChange, disabled, ...props }: CheckboxProps) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "peer inline-flex h-5 w-5 shrink-0 items-center justify-center rounded border border-border bg-background transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
        "disabled:cursor-not-allowed disabled:opacity-50",
        checked && "border-primary bg-primary text-primary-foreground",
        className,
      )}
      {...props}
    >
      {checked && <Check className="h-3.5 w-3.5" />}
    </button>
  );
}
