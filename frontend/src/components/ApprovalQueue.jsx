import { useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Clock3,
  Eye,
  FileText,
  MessageSquareText,
  ShieldCheck,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { faDate, faNumber, toolLabels } from "../lib/format";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { ConfirmDialog } from "./ui/dialog";
import { EmptyState } from "./EmptyState";
import { PanelTitle } from "./PanelTitle";

const toolIcons = {
  generate_outreach_script: MessageSquareText,
  draft_project_proposal: FileText,
};

export function ApprovalQueue({
  steps = [],
  onApproved = () => {},
  onRejected = () => {},
  onViewTask = () => {},
}) {
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [rejecting, setRejecting] = useState(null);

  async function decide(step, action) {
    setBusyId(step.id);
    setError("");
    try {
      const updatedTask =
        action === "approve"
          ? await api.approveStep(step.id)
          : await api.rejectStep(step.id);
      if (action === "approve") onApproved(step, updatedTask);
      else onRejected(step, updatedTask);
      setRejecting(null);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div data-testid="approval-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="HUMAN IN THE LOOP"
        title="مرکز تصمیم و تأیید"
        description="جزئیات هر اقدام حساس را ببین؛ فقط مواردی که تأیید می‌کنی اجرا خواهند شد."
        meta={
          <span className="rounded-full border border-amber-400/15 bg-amber-400/[.07] px-2 py-0.5 text-[9px] text-amber-300">
            {faNumber(steps.length)} تصمیم باز
          </span>
        }
      />

      <div className="mb-5 flex gap-3 rounded-2xl border border-amber-400/12 bg-amber-400/[.035] p-4">
        <ShieldCheck className="mt-0.5 shrink-0 text-amber-300" size={19} />
        <div>
          <p className="text-xs font-semibold text-amber-200">
            کنترل نهایی همیشه با شماست
          </p>
          <p className="mt-1 text-[11px] leading-6 text-slate-500">
            تأیید، همان قدم را اجرا می‌کند و سپس مسیر تسک از همان نقطه ادامه
            می‌یابد. رد کردن، تسک را متوقف و لغو می‌کند.
          </p>
        </div>
      </div>

      {error && (
        <p
          className="mb-4 rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-300"
          role="alert"
        >
          {error}
        </p>
      )}
      {steps.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="صف تأیید خالی است"
          description="فعلاً هیچ اقدام حساسی منتظر تصمیم شما نیست."
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {steps.map((step) => {
            const Icon = toolIcons[step.tool_name] || ShieldCheck;
            return (
              <Card
                key={step.id}
                className="overflow-hidden border-violet-400/15"
              >
                <div className="h-1 bg-gradient-to-l from-primary via-violet-400 to-fuchsia-400" />
                <CardContent className="p-5">
                  <div className="flex items-start gap-3">
                    <span className="grid size-11 shrink-0 place-items-center rounded-xl border border-violet-400/20 bg-violet-400/[.09] text-violet-300">
                      <Icon size={19} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-white">
                        {step.title}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-slate-600">
                        <span className="flex items-center gap-1">
                          <Clock3 size={11} />
                          {faDate(step.created_at, { year: undefined })}
                        </span>
                        <span>تسک #{faNumber(step.task_id)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 rounded-xl border border-line/70 bg-background/60 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <span className="text-[10px] font-semibold text-slate-500">
                        اقدام پیشنهادی
                      </span>
                      <code
                        dir="ltr"
                        className="rounded-lg bg-violet-400/[.08] px-2 py-1 text-[10px] text-violet-300"
                      >
                        {toolLabels[step.tool_name] ||
                          step.tool_name ||
                          "manual"}
                      </code>
                    </div>
                    <ArgumentPreview arguments={step.arguments || {}} />
                  </div>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onViewTask(step.task_id)}
                    >
                      <Eye size={14} />
                      مشاهده تسک
                    </Button>
                    <div className="flex gap-2">
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={busyId === step.id}
                        onClick={() => setRejecting(step)}
                      >
                        <X size={15} />
                        رد کردن
                      </Button>
                      <Button
                        variant="success"
                        size="sm"
                        loading={busyId === step.id}
                        onClick={() => decide(step, "approve")}
                      >
                        <Check size={15} />
                        تأیید و ادامه
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
      <ConfirmDialog
        open={Boolean(rejecting)}
        onClose={() => setRejecting(null)}
        onConfirm={() => rejecting && decide(rejecting, "reject")}
        loading={Boolean(rejecting && busyId === rejecting.id)}
        title="رد این اقدام؟"
        description="با رد کردن، این قدم و تسک مربوطه لغو می‌شوند و قدم‌های بعدی اجرا نخواهند شد."
        confirmLabel="بله، رد شود"
      />
    </div>
  );
}

function ArgumentPreview({ arguments: args }) {
  const entries = Object.entries(args);
  if (entries.length === 0)
    return (
      <p className="text-[11px] text-slate-600">
        این اقدام ورودی اضافه‌ای ندارد.
      </p>
    );
  return (
    <dl className="space-y-2">
      {entries.map(([key, value]) => (
        <div
          key={key}
          className="flex items-start justify-between gap-4 text-[11px]"
        >
          <dt dir="ltr" className="text-slate-600">
            {key}
          </dt>
          <dd
            className="max-w-[70%] break-words text-left text-slate-300"
            dir={
              typeof value === "string" && /[\u0600-\u06ff]/.test(value)
                ? "rtl"
                : "ltr"
            }
          >
            {typeof value === "object" ? JSON.stringify(value) : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
