import { useEffect, useState } from "react";
import {
  CalendarCheck,
  ClipboardCheck,
  Loader2,
  MoonStar,
  Sunrise,
} from "lucide-react";
import { api } from "../lib/api";
import { faNumber } from "../lib/format";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { Input, Textarea } from "./ui/input";

/**
 * Self-contained daily delivery plan card: staggered deadlines (one task per
 * day starting tomorrow), morning reminder + evening report settings, and the
 * end-of-day report box.
 */
export function DailyPlanCard({ notify = () => {}, onChanged = () => {} }) {
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState("");
  const [savingReport, setSavingReport] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const result = await api.getDailyPlan();
      setPlan(result);
      setReport(result.report_today || "");
    } catch (reason) {
      setError(reason.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggleEnabled(enabled) {
    setBusy(true);
    try {
      const settings = await api.setDailySettings({ enabled });
      setPlan((current) => ({ ...current, settings }));
      notify(
        enabled
          ? "یادآوری صبح و گزارش شبانه فعال شد"
          : "برنامه روزانه غیرفعال شد",
        "success",
      );
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function assign() {
    setBusy(true);
    try {
      const result = await api.assignDailyDeadlines();
      notify(
        result.count > 0
          ? `${faNumber(result.count)} تسک از فردا، روزی یکی زمان تحویل گرفت`
          : "تسک بدون زمان تحویلی نمانده",
        "success",
      );
      await load();
      await onChanged();
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function saveTime(field, value) {
    setBusy(true);
    try {
      const settings = await api.setDailySettings({ [field]: value });
      setPlan((current) => ({ ...current, settings }));
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function submitReport() {
    if (!report.trim()) {
      notify("گزارش خالی است؛ چند کلمه بنویس", "error");
      return;
    }
    setSavingReport(true);
    try {
      await api.submitDailyReport(report.trim());
      notify("گزارش امروز ثبت شد", "success");
      await load();
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setSavingReport(false);
    }
  }

  if (error) {
    return (
      <Card data-testid="daily-plan-card">
        <CardContent>
          <p className="text-xs text-rose-300">{error}</p>
        </CardContent>
      </Card>
    );
  }
  if (!plan) {
    return (
      <Card data-testid="daily-plan-card">
        <CardContent>
          <p className="flex items-center gap-2 py-4 text-xs text-slate-500">
            <Loader2 size={14} className="animate-spin" /> در حال بارگذاری
            برنامه روزانه…
          </p>
        </CardContent>
      </Card>
    );
  }

  const { settings, today, unscheduled_count: unscheduled } = plan;

  return (
    <Card data-testid="daily-plan-card">
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 font-semibold text-white">
              <CalendarCheck size={17} className="text-emerald-300" />
              برنامه تحویل روزانه
            </h2>
            <p className="mt-1 text-[10px] text-slate-600">
              هر روز یک تسک، یادآوری صبح و گزارش شبانه ({settings.timezone})
            </p>
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-[10px] text-slate-400">
            <input
              type="checkbox"
              checked={settings.enabled}
              disabled={busy}
              onChange={(event) => toggleEnabled(event.target.checked)}
              aria-label="فعال بودن برنامه روزانه"
              className="size-4 accent-emerald-400"
              data-testid="daily-plan-toggle"
            />
            فعال
          </label>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-line bg-background/50 p-3">
            <p className="flex items-center gap-1.5 text-[10px] text-slate-500">
              <Sunrise size={13} className="text-amber-300" /> یادآوری صبح
            </p>
            <Input
              dir="ltr"
              type="time"
              value={settings.morning_time}
              disabled={busy}
              onChange={(event) => saveTime("morning_time", event.target.value)}
              className="mt-2 h-9 text-center font-mono text-xs"
              aria-label="ساعت یادآوری صبح"
            />
          </div>
          <div className="rounded-xl border border-line bg-background/50 p-3">
            <p className="flex items-center gap-1.5 text-[10px] text-slate-500">
              <MoonStar size={13} className="text-indigo-300" /> گزارش شبانه
            </p>
            <Input
              dir="ltr"
              type="time"
              value={settings.evening_time}
              disabled={busy}
              onChange={(event) => saveTime("evening_time", event.target.value)}
              className="mt-2 h-9 text-center font-mono text-xs"
              aria-label="ساعت گزارش شبانه"
            />
          </div>
        </div>

        <div className="mt-3">
          <p className="mb-2 text-[10px] font-medium text-slate-400">
            کارهای امروز
          </p>
          {today.length === 0 ? (
            <p className="rounded-xl border border-dashed border-line px-3 py-4 text-center text-[11px] text-slate-600">
              برای امروز زمان تحویلی ثبت نشده
            </p>
          ) : (
            <ul className="space-y-1.5">
              {today.map((task) => (
                <li
                  key={task.id}
                  className="flex items-center justify-between gap-2 rounded-xl border border-line/70 bg-background/40 px-3 py-2"
                >
                  <span className="truncate text-xs text-slate-300">
                    {task.title}
                  </span>
                  <Badge status={task.status} />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-3">
          <p className="text-[10px] text-slate-600">
            {unscheduled > 0
              ? `${faNumber(unscheduled)} تسک بدون زمان تحویل`
              : "همه تسک‌های باز زمان تحویل دارند"}
          </p>
          <Button
            size="sm"
            variant="outline"
            loading={busy}
            disabled={unscheduled === 0}
            onClick={assign}
            data-testid="assign-deadlines"
          >
            <CalendarCheck size={14} /> از فردا، روزی یک تسک
          </Button>
        </div>

        <div className="mt-3 rounded-xl border border-indigo-400/10 bg-indigo-400/[.03] p-3">
          <p className="flex items-center gap-1.5 text-[10px] font-medium text-indigo-200">
            <ClipboardCheck size={13} /> گزارش امشب
          </p>
          <Textarea
            value={report}
            onChange={(event) => setReport(event.target.value)}
            placeholder="امروز چه کارهایی انجام دادی؟"
            className="mt-2 min-h-20 text-xs leading-6"
            aria-label="گزارش شبانه"
          />
          <div className="mt-2 flex items-center justify-between gap-2">
            <p className="text-[9px] text-slate-600">
              {plan.report_today
                ? "گزارش امروز ثبت شده؛ با ذخیره دوباره به‌روز می‌شود"
                : "بعد از ساعت گزارش، همراه هم همین را ازت می‌پرسد"}
            </p>
            <Button
              size="sm"
              loading={savingReport}
              disabled={!report.trim()}
              onClick={submitReport}
              data-testid="submit-report"
            >
              ثبت گزارش
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
