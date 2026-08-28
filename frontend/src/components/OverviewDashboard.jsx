import {
  ArrowLeft,
  BrainCircuit,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronLeft,
  Clock3,
  ListTodo,
  Scissors,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { faNumber, sourceLabels, truncate } from "../lib/format";
import { Badge } from "./ui/badge";
import { DailyPlanCard } from "./DailyPlanCard";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { EmptyState } from "./EmptyState";
import { PanelTitle } from "./PanelTitle";

function Metric({
  icon: Icon,
  label,
  value,
  helper,
  tone = "violet",
  onClick,
}) {
  const tones = {
    violet: "bg-violet-400/10 text-violet-300 border-violet-400/15",
    emerald: "bg-emerald-400/10 text-emerald-300 border-emerald-400/15",
    amber: "bg-amber-400/10 text-amber-300 border-amber-400/15",
    cyan: "bg-cyan-400/10 text-cyan-300 border-cyan-400/15",
  };
  return (
    <button
      onClick={onClick}
      className="group rounded-2xl border border-line/80 bg-surface/90 p-4 text-right shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-slate-600/70 sm:p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <span
          className={`grid size-10 place-items-center rounded-xl border ${tones[tone]}`}
        >
          <Icon size={18} />
        </span>
        <ChevronLeft
          size={16}
          className="mt-1 text-slate-700 transition group-hover:-translate-x-1 group-hover:text-slate-400"
        />
      </div>
      <p className="mt-5 text-2xl font-bold tracking-tight text-white">
        {faNumber(value)}
      </p>
      <p className="mt-1 text-xs font-medium text-slate-400">{label}</p>
      <p className="mt-2 text-[10px] text-slate-600">{helper}</p>
    </button>
  );
}

export function OverviewDashboard({
  data,
  onNavigate = () => {},
  onTaskSelect = () => {},
  notify = () => {},
  onRefresh = () => {},
}) {
  const {
    tasks,
    approvals,
    memories,
    salons,
    salonPlan,
    projects,
    reminders,
    tools,
    health,
  } = data;
  const doneCount = tasks.filter((task) => task.status === "done").length;
  const activeTasks = tasks
    .filter((task) => !["done", "cancelled", "failed"].includes(task.status))
    .slice(0, 4);
  const enabledTools = tools.filter((tool) => tool.enabled).length;
  const currentHour = new Date().getHours();
  const greeting =
    currentHour < 12 ? "صبح بخیر" : currentHour < 18 ? "وقت بخیر" : "عصر بخیر";

  return (
    <div data-testid="overview-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="COMMAND CENTER"
        title={`${greeting}، امروز روی چه چیزی تمرکز می‌کنیم؟`}
        description="یک نمای زنده از کارها، تصمیم‌های منتظر شما و حرکت ماژول‌های هوشمند."
        meta={
          <span className="rounded-full border border-emerald-400/15 bg-emerald-400/[.07] px-2 py-0.5 text-[9px] text-emerald-300">
            هسته {health ? "آنلاین" : "در حال اتصال"}
          </span>
        }
        action={
          <Button onClick={() => onNavigate("tasks")}>
            <Sparkles size={16} />
            ثبت درخواست جدید
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Metric
          icon={ListTodo}
          label="تسک‌های فعال"
          value={tasks.length - doneCount}
          helper={`${faNumber(doneCount)} مورد تکمیل شده`}
          onClick={() => onNavigate("tasks")}
        />
        <Metric
          icon={ShieldCheck}
          label="منتظر تصمیم شما"
          value={approvals.length}
          helper="اقدام حساس بدون اجازه اجرا نمی‌شود"
          tone="amber"
          onClick={() => onNavigate("approval")}
        />
        <Metric
          icon={Scissors}
          label="پیگیری سالن امروز"
          value={salonPlan.length}
          helper={`از مجموع ${faNumber(salons.length)} سالن`}
          tone="emerald"
          onClick={() => onNavigate("salon")}
        />
        <Metric
          icon={Clock3}
          label="ددلاین نزدیک"
          value={reminders.length}
          helper={`در میان ${faNumber(projects.length)} پروژه`}
          tone="cyan"
          onClick={() => onNavigate("personal")}
        />
      </div>

      <div className="mt-5">
        <DailyPlanCard notify={notify} onChanged={onRefresh} />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
        <Card>
          <CardHeader>
            <div>
              <h2 className="font-semibold text-white">تمرکز امروز</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                کارهای باز با اولویت اقدام
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onNavigate("tasks")}
            >
              مشاهده همه <ArrowLeft size={14} />
            </Button>
          </CardHeader>
          <CardContent className="p-2 sm:p-3">
            {activeTasks.length === 0 ? (
              <EmptyState
                compact
                icon={CheckCircle2}
                title="همه‌چیز انجام شده"
                description="فعلاً تسک بازی وجود ندارد."
              />
            ) : (
              <div className="space-y-1">
                {activeTasks.map((task, index) => (
                  <button
                    key={task.id}
                    onClick={() => onTaskSelect(task)}
                    className="group flex w-full items-center gap-3 rounded-xl px-3 py-3.5 text-right transition hover:bg-white/[.035]"
                  >
                    <span className="grid size-9 shrink-0 place-items-center rounded-xl border border-line bg-elevated/60 text-xs font-semibold text-slate-500">
                      {faNumber(index + 1)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-slate-200 group-hover:text-white">
                          {task.title}
                        </p>
                        <Badge status={task.status} />
                      </div>
                      <p className="mt-1 truncate text-[11px] text-slate-600">
                        {task.description || "بدون توضیح اضافه"}
                      </p>
                    </div>
                    <ChevronLeft
                      size={16}
                      className="text-slate-700 group-hover:text-primary-soft"
                    />
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader>
            <div>
              <h2 className="font-semibold text-white">نبض سیستم</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                وضعیت قابلیت‌های اصلی
              </p>
            </div>
            <Zap size={18} className="text-amber-300" />
          </CardHeader>
          <CardContent className="space-y-4">
            <PulseRow
              label="ابزارهای آماده"
              value={`${faNumber(enabledTools)} از ${faNumber(tools.length)}`}
              percent={tools.length ? enabledTools / tools.length : 0}
            />
            <PulseRow
              label="حافظه بلندمدت"
              value={`${faNumber(memories.length)} ورودی`}
              percent={Math.min(memories.length / 20, 1)}
              tone="bg-mint"
            />
            <PulseRow
              label="نرخ تکمیل تسک"
              value={
                tasks.length
                  ? `${faNumber(Math.round((doneCount / tasks.length) * 100))}٪`
                  : "—"
              }
              percent={tasks.length ? doneCount / tasks.length : 0}
              tone="bg-cyan-400"
            />
            <div className="grid grid-cols-2 gap-2 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onNavigate("salon")}
              >
                <Scissors size={14} />
                سالن‌ها
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onNavigate("personal")}
              >
                <BriefcaseBusiness size={14} />
                پروژه‌ها
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <div>
              <h2 className="font-semibold text-white">اقدام فوری</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                مواردی که منتظر شما هستند
              </p>
            </div>
            <ShieldCheck size={18} className="text-primary-soft" />
          </CardHeader>
          <CardContent>
            {approvals.length === 0 ? (
              <EmptyState
                compact
                icon={ShieldCheck}
                title="صف تصمیم خالی است"
              />
            ) : (
              <div className="space-y-2">
                {approvals.slice(0, 3).map((step) => (
                  <button
                    key={step.id}
                    onClick={() => onNavigate("approval")}
                    className="w-full rounded-xl border border-violet-400/10 bg-violet-400/[.045] p-3 text-right transition hover:bg-violet-400/[.08]"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-xs font-medium text-slate-300">
                        {step.title}
                      </p>
                      <Badge status="needs_approval" />
                    </div>
                    <p
                      dir="ltr"
                      className="mt-2 truncate text-left text-[10px] text-slate-600"
                    >
                      {step.tool_name}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <h2 className="font-semibold text-white">آخرین یادگیری‌ها</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                داده‌هایی که وارد حافظه همراه شده‌اند
              </p>
            </div>
            <BrainCircuit size={18} className="text-mint" />
          </CardHeader>
          <CardContent>
            {memories.length === 0 ? (
              <EmptyState
                compact
                icon={BrainCircuit}
                title="حافظه هنوز خالی است"
              />
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {memories.slice(0, 4).map((memory) => (
                  <button
                    key={memory.id}
                    onClick={() => onNavigate("memory")}
                    className="rounded-xl border border-line/70 bg-white/[.018] p-3.5 text-right transition hover:border-slate-600"
                  >
                    <span className="text-[9px] font-bold text-mint">
                      {sourceLabels[memory.source] || memory.source}
                    </span>
                    <p className="mt-2 text-[11px] leading-6 text-slate-500">
                      {truncate(memory.content, 90)}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function PulseRow({ label, value, percent, tone = "bg-primary" }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-[11px]">
        <span className="text-slate-500">{label}</span>
        <span className="font-medium text-slate-300">{value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full transition-all duration-700 ${tone}`}
          style={{ width: `${Math.max(5, percent * 100)}%` }}
        />
      </div>
    </div>
  );
}
