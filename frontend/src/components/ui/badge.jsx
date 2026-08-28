import { cn } from "../../lib/utils";

const colors = {
  pending: "border-slate-500/20 bg-slate-400/[.08] text-slate-300",
  planned: "border-sky-400/20 bg-sky-400/[.09] text-sky-300",
  running: "border-amber-400/20 bg-amber-400/[.09] text-amber-300",
  paused: "border-orange-400/20 bg-orange-400/[.09] text-orange-300",
  needs_approval: "border-violet-400/25 bg-violet-400/[.11] text-violet-300",
  waiting_for_user:
    "border-fuchsia-400/20 bg-fuchsia-400/[.09] text-fuchsia-300",
  done: "border-emerald-400/20 bg-emerald-400/[.09] text-emerald-300",
  completed: "border-emerald-400/20 bg-emerald-400/[.09] text-emerald-300",
  active: "border-emerald-400/20 bg-emerald-400/[.09] text-emerald-300",
  interested: "border-teal-400/20 bg-teal-400/[.09] text-teal-300",
  customer: "border-indigo-400/20 bg-indigo-400/[.09] text-indigo-300",
  lead: "border-sky-400/20 bg-sky-400/[.09] text-sky-300",
  contacted: "border-cyan-400/20 bg-cyan-400/[.09] text-cyan-300",
  submitted: "border-blue-400/20 bg-blue-400/[.09] text-blue-300",
  won: "border-emerald-400/20 bg-emerald-400/[.09] text-emerald-300",
  failed: "border-rose-400/20 bg-rose-400/[.09] text-rose-300",
  lost: "border-rose-400/20 bg-rose-400/[.09] text-rose-300",
  cancelled: "border-slate-500/20 bg-slate-500/[.08] text-slate-400",
  inactive: "border-slate-500/20 bg-slate-500/[.08] text-slate-400",
};

export const statusLabels = {
  pending: "در انتظار",
  planned: "برنامه‌ریزی‌شده",
  running: "در حال اجرا",
  paused: "متوقف",
  needs_approval: "نیازمند تأیید",
  waiting_for_user: "منتظر کاربر",
  done: "انجام‌شده",
  failed: "ناموفق",
  cancelled: "لغوشده",
  active: "فعال",
  lead: "سرنخ",
  contacted: "تماس گرفته",
  interested: "علاقه‌مند",
  customer: "مشتری",
  inactive: "غیرفعال",
  do_not_contact: "عدم تماس",
  submitted: "ارسال‌شده",
  won: "برنده",
  lost: "از دست‌رفته",
  completed: "تکمیل‌شده",
};

export function Badge({ status, children, className, dot = false }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-[10px] font-medium",
        colors[status] || colors.pending,
        className,
      )}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" />}
      {children || statusLabels[status] || status}
    </span>
  );
}
