import { forwardRef } from "react";
import { cn } from "../../lib/utils";

const variants = {
  primary:
    "border border-primary-soft/25 bg-gradient-to-b from-[#8f6bfa] to-[#6d3ff0] text-white shadow-[0_10px_30px_rgba(124,92,255,.28),inset_0_1px_0_rgba(255,255,255,.18)] hover:from-[#9a78ff] hover:to-[#7747fb] hover:shadow-[0_14px_38px_rgba(124,92,255,.38),inset_0_1px_0_rgba(255,255,255,.22)] active:translate-y-px",
  secondary:
    "border border-line bg-elevated/70 text-slate-200 hover:border-slate-600 hover:bg-elevated active:translate-y-px",
  outline:
    "border border-primary/25 bg-primary/[.06] text-primary-soft hover:bg-primary/[.12] active:translate-y-px",
  ghost: "text-slate-400 hover:bg-white/[.055] hover:text-white",
  danger:
    "border border-rose-500/20 bg-rose-500/10 text-rose-300 hover:bg-rose-500/18 active:translate-y-px",
  success:
    "border border-emerald-400/20 bg-emerald-400/10 text-emerald-300 hover:bg-emerald-400/18 active:translate-y-px",
};
const sizes = {
  xs: "h-8 rounded-lg px-2.5 text-[11px]",
  sm: "h-9 rounded-[10px] px-3 text-xs",
  default: "h-11 rounded-xl px-4 text-sm",
  lg: "h-12 rounded-xl px-5 text-sm",
  icon: "size-10 rounded-xl p-0",
};

export const Button = forwardRef(function Button(
  {
    className,
    variant = "primary",
    size = "default",
    type = "button",
    loading = false,
    children,
    ...props
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-2 font-medium transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-45",
        variants[variant],
        sizes[size],
        className,
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && (
        <span
          className="size-4 animate-spin rounded-full border-2 border-current border-l-transparent"
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  );
});
