import { useEffect, useMemo, useState } from "react";
import {
  BellRing,
  BriefcaseBusiness,
  CheckCircle2,
  Command,
  ListTodo,
  Search,
  Scissors,
  ShieldCheck,
  X,
} from "lucide-react";
import { faNumber } from "../lib/format";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
import { Input } from "./ui/input";

export function CommandPalette({
  open,
  onClose,
  tasks = [],
  salons = [],
  projects = [],
  onTask,
  onNavigate,
}) {
  const [query, setQuery] = useState("");
  useEffect(() => {
    if (open) setQuery("");
  }, [open]);
  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return [];
    const includes = (value) => value.toLowerCase().includes(normalized);
    return [
      ...tasks
        .filter((item) => includes(`${item.title} ${item.description || ""}`))
        .slice(0, 4)
        .map((item) => ({
          type: "task",
          item,
          title: item.title,
          subtitle: "تسک",
          icon: ListTodo,
        })),
      ...salons
        .filter((item) =>
          includes(`${item.name} ${item.phone} ${item.city || ""}`),
        )
        .slice(0, 4)
        .map((item) => ({
          type: "salon",
          item,
          title: item.name,
          subtitle: item.phone,
          icon: Scissors,
        })),
      ...projects
        .filter((item) => includes(`${item.title} ${item.client_name || ""}`))
        .slice(0, 4)
        .map((item) => ({
          type: "project",
          item,
          title: item.title,
          subtitle: item.client_name || "پروژه شخصی",
          icon: BriefcaseBusiness,
        })),
    ];
  }, [query, tasks, salons, projects]);

  function choose(result) {
    onClose();
    if (result.type === "task") onTask(result.item);
    else onNavigate(result.type === "salon" ? "salon" : "personal");
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="جستجوی سریع"
      description="میان تسک‌ها، سالن‌ها و پروژه‌ها جستجو کن."
      size="lg"
    >
      <div className="relative">
        <Search
          size={17}
          className="absolute right-3.5 top-3.5 text-slate-600"
        />
        <Input
          autoFocus
          aria-label="جستجوی سراسری"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-12 pr-10 text-[15px]"
          placeholder="عبارت مورد نظر را بنویس…"
        />
      </div>
      <div className="mt-4 min-h-44">
        {!query ? (
          <div className="grid min-h-44 place-items-center text-center">
            <div>
              <Command className="mx-auto text-slate-700" size={28} />
              <p className="mt-3 text-xs text-slate-600">
                برای پیدا کردن سریع هر رکورد شروع به تایپ کن
              </p>
            </div>
          </div>
        ) : results.length === 0 ? (
          <div className="grid min-h-44 place-items-center text-xs text-slate-600">
            نتیجه‌ای پیدا نشد
          </div>
        ) : (
          <div className="space-y-1">
            {results.map((result) => {
              const Icon = result.icon;
              return (
                <button
                  key={`${result.type}-${result.item.id}`}
                  onClick={() => choose(result)}
                  className="flex w-full items-center gap-3 rounded-xl p-3 text-right transition hover:bg-white/[.04]"
                >
                  <span className="grid size-9 place-items-center rounded-xl border border-line bg-elevated/50 text-slate-500">
                    <Icon size={15} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <strong className="block truncate text-xs font-medium text-slate-300">
                      {result.title}
                    </strong>
                    <span className="mt-1 block truncate text-[10px] text-slate-600">
                      {result.subtitle}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </Dialog>
  );
}

export function NotificationPopover({
  open,
  approvals = [],
  reminders = [],
  onClose,
  onNavigate,
}) {
  if (!open) return null;
  return (
    <div className="absolute left-0 top-12 z-50 w-[min(360px,calc(100vw-2rem))] animate-slide-up overflow-hidden rounded-2xl border border-line bg-surface shadow-popover">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <p className="text-xs font-semibold text-white">اعلان‌ها</p>
          <p className="mt-1 text-[9px] text-slate-600">
            {faNumber(approvals.length + reminders.length)} مورد نیازمند توجه
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onClose}
        >
          <X size={14} />
        </Button>
      </div>
      <div className="max-h-80 overflow-y-auto p-2">
        {approvals.length === 0 && reminders.length === 0 ? (
          <div className="grid min-h-36 place-items-center text-center">
            <div>
              <CheckCircle2 className="mx-auto text-emerald-300" size={22} />
              <p className="mt-2 text-xs text-slate-500">اعلان تازه‌ای نیست</p>
            </div>
          </div>
        ) : (
          <>
            {approvals.slice(0, 3).map((step) => (
              <button
                key={step.id}
                onClick={() => {
                  onNavigate("approval");
                  onClose();
                }}
                className="flex w-full gap-3 rounded-xl p-3 text-right hover:bg-white/[.035]"
              >
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-violet-400/[.09] text-violet-300">
                  <ShieldCheck size={14} />
                </span>
                <div>
                  <p className="text-[11px] font-medium text-slate-300">
                    {step.title}
                  </p>
                  <p className="mt-1 text-[9px] text-slate-600">
                    منتظر تأیید شما
                  </p>
                </div>
              </button>
            ))}
            {reminders.slice(0, 3).map((item) => (
              <button
                key={item.project.id}
                onClick={() => {
                  onNavigate("personal");
                  onClose();
                }}
                className="flex w-full gap-3 rounded-xl p-3 text-right hover:bg-white/[.035]"
              >
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-amber-400/[.09] text-amber-300">
                  <BellRing size={14} />
                </span>
                <div>
                  <p className="text-[11px] font-medium text-slate-300">
                    {item.project.title}
                  </p>
                  <p className="mt-1 text-[9px] text-slate-600">
                    {item.days_until_due === 0
                      ? "موعد امروز"
                      : `${faNumber(item.days_until_due)} روز تا موعد`}
                  </p>
                </div>
              </button>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

export function ToastStack({ toasts, onDismiss }) {
  return (
    <div
      className="fixed bottom-4 left-4 z-[100] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2"
      aria-live="polite"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex animate-slide-up items-start gap-3 rounded-xl border p-3.5 shadow-popover backdrop-blur-xl ${toast.type === "error" ? "border-rose-400/20 bg-[#241218]/95 text-rose-200" : "border-emerald-400/20 bg-[#0d211d]/95 text-emerald-200"}`}
        >
          <span
            className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ${toast.type === "error" ? "bg-rose-400/10" : "bg-emerald-400/10"}`}
          >
            {toast.type === "error" ? (
              <X size={13} />
            ) : (
              <CheckCircle2 size={13} />
            )}
          </span>
          <p className="flex-1 text-xs leading-6">{toast.message}</p>
          <button
            onClick={() => onDismiss(toast.id)}
            className="text-current opacity-50 hover:opacity-100"
          >
            <X size={13} />
          </button>
        </div>
      ))}
    </div>
  );
}
