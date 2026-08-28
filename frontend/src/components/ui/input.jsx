import { forwardRef } from "react";
import { cn } from "../../lib/utils";

const fieldClass =
  "w-full rounded-xl border border-line bg-[#090d16]/80 px-3.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 hover:border-slate-700 focus:border-primary/65 focus:ring-4 focus:ring-primary/[.08] disabled:cursor-not-allowed disabled:opacity-50";

export const Input = forwardRef(function Input({ className, ...props }, ref) {
  return (
    <input ref={ref} className={cn("h-11", fieldClass, className)} {...props} />
  );
});

export const Textarea = forwardRef(function Textarea(
  { className, ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      className={cn(
        "min-h-28 resize-y px-3.5 py-3 leading-7",
        fieldClass,
        className,
      )}
      {...props}
    />
  );
});

export const Select = forwardRef(function Select(
  { className, children, ...props },
  ref,
) {
  return (
    <select
      ref={ref}
      className={cn("h-11 appearance-none", fieldClass, className)}
      {...props}
    >
      {children}
    </select>
  );
});

export function Field({ label, hint, error, children, className }) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-2 flex items-center justify-between gap-3 text-xs font-medium text-slate-300">
        {label}
        {hint && <span className="font-normal text-slate-600">{hint}</span>}
      </span>
      {children}
      {error && (
        <span className="mt-1.5 block text-[11px] text-rose-300">{error}</span>
      )}
    </label>
  );
}
