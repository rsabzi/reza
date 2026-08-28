import { Inbox } from "lucide-react";

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  compact = false,
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-2xl border border-dashed border-line/90 bg-white/[.012] px-6 text-center ${compact ? "min-h-36 py-7" : "min-h-52 py-10"}`}
      role="status"
    >
      <div className="mb-4 grid size-12 place-items-center rounded-2xl border border-line bg-elevated/60 text-slate-500 shadow-inner">
        <Icon size={21} strokeWidth={1.7} aria-hidden="true" />
      </div>
      <p className="text-sm font-semibold text-slate-300">{title}</p>
      {description && (
        <p className="mt-2 max-w-sm text-xs leading-6 text-slate-600">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
