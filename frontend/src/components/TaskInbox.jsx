import { useMemo, useState } from "react";
import {
  ArrowLeft,
  CalendarClock,
  ChevronDown,
  Filter,
  ListChecks,
  Plus,
  Repeat2,
  Search,
  Sparkles,
} from "lucide-react";
import { api } from "../lib/api";
import { faDate, faNumber } from "../lib/format";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { Field, Input, Select, Textarea } from "./ui/input";
import { EmptyState } from "./EmptyState";
import { PanelTitle } from "./PanelTitle";

export function TaskInbox({
  tasks = [],
  onCreated = () => {},
  onSelect = () => {},
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [moduleName, setModuleName] = useState("");
  const [recurring, setRecurring] = useState(false);
  const [scheduledTime, setScheduledTime] = useState("09:00");
  const [advanced, setAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = useMemo(
    () =>
      tasks.filter((task) => {
        const matchesSearch =
          !search ||
          `${task.title} ${task.description || ""}`
            .toLowerCase()
            .includes(search.toLowerCase());
        return (
          matchesSearch &&
          (statusFilter === "all" || task.status === statusFilter)
        );
      }),
    [tasks, search, statusFilter],
  );

  async function submit(event) {
    event.preventDefault();
    if (!title.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const payload = {
        title: title.trim(),
        description: description.trim() || null,
        module_name: moduleName || null,
        ...(recurring
          ? { recurrence_rule: "daily", scheduled_time: scheduledTime }
          : {}),
      };
      const task = await api.createTask(payload);
      onCreated(task);
      setTitle("");
      setDescription("");
      setModuleName("");
      setRecurring(false);
      setAdvanced(false);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setSubmitting(false);
    }
  }

  const activeCount = tasks.filter(
    (task) => !["done", "cancelled", "failed"].includes(task.status),
  ).length;
  const doneCount = tasks.filter((task) => task.status === "done").length;

  return (
    <div data-testid="task-inbox-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="TASK WORKSPACE"
        title="صندوق کارهای هوشمند"
        description="درخواست را طبیعی بنویس، زمینه آن را مشخص کن و مسیر اجرا را زیر نظر داشته باش."
        meta={
          <span className="text-[10px] text-slate-600">
            {faNumber(activeCount)} کار فعال
          </span>
        }
      />

      <Card className="relative mb-5 overflow-hidden border-primary/20">
        <div className="pointer-events-none absolute -left-16 -top-24 size-72 rounded-full bg-primary/[.09] blur-3xl" />
        <CardContent className="relative p-5 sm:p-6">
          <form onSubmit={submit}>
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl border border-primary/20 bg-primary/10 text-primary-soft">
                  <Sparkles size={18} />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-white">
                    درخواست جدید
                  </h2>
                  <p className="mt-1 text-[11px] text-slate-600">
                    هر چیزی که می‌خواهی انجام شود را بنویس
                  </p>
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setAdvanced((value) => !value)}
              >
                تنظیمات بیشتر{" "}
                <ChevronDown
                  size={14}
                  className={`transition ${advanced ? "rotate-180" : ""}`}
                />
              </Button>
            </div>
            <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
              <div className="space-y-3">
                <Input
                  aria-label="عنوان تسک"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="مثلاً برای سالن آریانا یک برنامه پیگیری آماده کن…"
                  className="h-12 text-[15px]"
                />
                <Textarea
                  aria-label="توضیحات تسک"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  className="min-h-20"
                  placeholder="نتیجه مورد انتظار، محدودیت‌ها یا اطلاعات تکمیلی (اختیاری)"
                />
              </div>
              <Button
                type="submit"
                size="lg"
                className="h-12 self-start lg:min-w-40"
                disabled={!title.trim()}
                loading={submitting}
              >
                <Plus size={17} />
                افزودن به همراه
              </Button>
            </div>
            {advanced && (
              <div className="mt-4 grid animate-slide-up gap-3 rounded-xl border border-line/70 bg-background/45 p-4 sm:grid-cols-3">
                <Field label="حوزه تسک">
                  <Select
                    value={moduleName}
                    onChange={(event) => setModuleName(event.target.value)}
                  >
                    <option value="">عمومی</option>
                    <option value="salon">بازاریابی سالن</option>
                    <option value="personal">شخصی و فریلنس</option>
                  </Select>
                </Field>
                <Field label="نوع اجرا">
                  <Select
                    value={recurring ? "daily" : "once"}
                    onChange={(event) =>
                      setRecurring(event.target.value === "daily")
                    }
                  >
                    <option value="once">یک‌بار</option>
                    <option value="daily">تکرار روزانه</option>
                  </Select>
                </Field>
                <Field
                  label="زمان اجرا"
                  hint={!recurring ? "برای تکرار فعال می‌شود" : null}
                >
                  <Input
                    type="time"
                    value={scheduledTime}
                    onChange={(event) => setScheduledTime(event.target.value)}
                    disabled={!recurring}
                  />
                </Field>
              </div>
            )}
            {error && (
              <p className="mt-3 text-xs text-rose-300" role="alert">
                {error}
              </p>
            )}
          </form>
        </CardContent>
      </Card>

      <div className="mb-5 grid grid-cols-3 gap-3">
        <MiniStat label="همه" value={tasks.length} icon={ListChecks} />
        <MiniStat
          label="فعال"
          value={activeCount}
          icon={CalendarClock}
          tone="text-amber-300"
        />
        <MiniStat
          label="تمام‌شده"
          value={doneCount}
          icon={Sparkles}
          tone="text-emerald-300"
        />
      </div>

      <Card>
        <CardHeader className="flex-col items-stretch sm:flex-row sm:items-center">
          <div>
            <h2 className="font-semibold text-white">فهرست تسک‌ها</h2>
            <p className="mt-1 text-[11px] text-slate-600">
              {faNumber(filtered.length)} نتیجه از {faNumber(tasks.length)} تسک
            </p>
          </div>
          <div className="flex gap-2">
            <div className="relative flex-1 sm:w-64">
              <Search
                size={15}
                className="absolute right-3 top-3 text-slate-600"
              />
              <Input
                aria-label="جستجوی تسک"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="h-10 pr-9"
                placeholder="جستجو…"
              />
            </div>
            <div className="relative">
              <Filter
                size={14}
                className="pointer-events-none absolute right-3 top-3 text-slate-600"
              />
              <Select
                aria-label="فیلتر وضعیت تسک"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="h-10 w-36 pr-8"
              >
                <option value="all">همه وضعیت‌ها</option>
                <option value="pending">در انتظار</option>
                <option value="paused">متوقف</option>
                <option value="done">انجام‌شده</option>
                <option value="failed">ناموفق</option>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-2 sm:p-3">
          {tasks.length === 0 ? (
            <EmptyState
              title="هنوز کاری ثبت نشده"
              description="اولین درخواستت را در کادر بالا بنویس."
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              compact
              icon={Search}
              title="نتیجه‌ای پیدا نشد"
              description="عبارت جستجو یا فیلتر را تغییر بده."
            />
          ) : (
            <div className="space-y-1">
              {filtered.map((task) => (
                <button
                  key={task.id}
                  onClick={() => onSelect(task)}
                  className="group flex w-full items-center gap-3 rounded-xl px-3 py-3.5 text-right transition hover:bg-white/[.035]"
                >
                  <span
                    className={`grid size-10 shrink-0 place-items-center rounded-xl border ${task.recurrence_rule ? "border-cyan-400/15 bg-cyan-400/[.07] text-cyan-300" : "border-line bg-elevated/50 text-slate-500"}`}
                  >
                    {task.recurrence_rule ? (
                      <Repeat2 size={17} />
                    ) : (
                      <ListChecks size={17} />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium text-slate-200 group-hover:text-white">
                        {task.title}
                      </p>
                      <Badge status={task.status} />
                      {task.module_name && (
                        <span className="text-[10px] text-slate-600">
                          {task.module_name === "salon" ? "سالن" : "شخصی"}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 truncate text-[11px] text-slate-600">
                      {task.description ||
                        `ایجاد شده در ${faDate(task.created_at)}`}
                    </p>
                  </div>
                  <ArrowLeft
                    size={16}
                    className="shrink-0 text-slate-700 transition group-hover:-translate-x-1 group-hover:text-primary-soft"
                  />
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function MiniStat({ label, value, icon: Icon, tone = "text-primary-soft" }) {
  return (
    <div className="rounded-xl border border-line/70 bg-surface/70 p-3 sm:flex sm:items-center sm:gap-3">
      <Icon size={16} className={tone} />
      <div className="mt-2 sm:mt-0">
        <p className="text-lg font-bold text-white">{faNumber(value)}</p>
        <p className="text-[10px] text-slate-600">{label}</p>
      </div>
    </div>
  );
}
