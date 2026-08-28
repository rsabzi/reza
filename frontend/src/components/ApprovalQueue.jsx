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
import { ConfirmDialog, Dialog } from "./ui/dialog";
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
  // Outputs of the just-approved action, shown immediately in a dialog:
  // { title, error, entries: [{ id, title, text, json }] }
  const [resultView, setResultView] = useState(null);

  function collectOutputs(updatedTask, approvedStepId, startedAt) {
    const approved = (updatedTask.steps || []).find(
      (item) => item.id === approvedStepId,
    );
    const entries = [];
    for (const step of updatedTask.steps || []) {
      if (step.result == null) continue;
      const isApproved = step.id === approvedStepId;
      // Older results from previous runs are still reachable in task detail;
      // here we surface the approved step plus everything executed with it.
      const ranInThisApproval = new Date(step.updated_at) >= startedAt;
      if (!isApproved && !ranInThisApproval) continue;
      entries.push({
        id: step.id,
        title: step.title,
        result: step.result,
      });
    }
    return {
      title: approved?.title || "اقدام تأییدشده",
      error:
        approved?.status === "failed"
          ? approved.error || "اجرا با خطا مواجه شد"
          : null,
      entries,
    };
  }

  async function decide(step, action) {
    setBusyId(step.id);
    setError("");
    const startedAt = new Date(Date.now() - 1000);
    try {
      const updatedTask =
        action === "approve"
          ? await api.approveStep(step.id)
          : await api.rejectStep(step.id);
      if (action === "approve") {
        setResultView(collectOutputs(updatedTask, step.id, startedAt));
        onApproved(step, updatedTask);
      } else {
        onRejected(step, updatedTask);
      }
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
      <ApprovalResultDialog
        view={resultView}
        onClose={() => setResultView(null)}
      />
    </div>
  );
}

/** Prefer human-readable text fields of a tool result over raw JSON. */
const TEXT_FIELDS = [
  "script",
  "proposal",
  "content",
  "message",
  "text",
  "summary",
];

function readableResult(result) {
  if (typeof result === "string") {
    return result.trim() ? result : null;
  }
  if (result && typeof result === "object") {
    for (const key of TEXT_FIELDS) {
      const value = result[key];
      if (typeof value === "string" && value.trim()) return value;
    }
  }
  return null;
}

function ApprovalResultDialog({ view, onClose }) {
  const [copied, setCopied] = useState(false);
  if (!view) return null;

  const plainText = view.entries
    .map(
      (entry) =>
        readableResult(entry.result) ?? JSON.stringify(entry.result, null, 2),
    )
    .join("\n\n---\n\n");

  async function copyAll() {
    await navigator.clipboard?.writeText(plainText);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={`نتیجه اجرا: ${view.title}`}
      description={
        view.entries.length > 0
          ? "خروجی اقدام تأییدشده آماده استفاده است."
          : undefined
      }
      size="md"
    >
      <div
        className="space-y-4 px-5 py-5 sm:px-6"
        data-testid="approval-result"
      >
        {view.error && (
          <p
            className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs leading-6 text-rose-300"
            role="alert"
          >
            {view.error}
          </p>
        )}
        {view.entries.length === 0 && !view.error && (
          <p className="py-6 text-center text-xs text-slate-500">
            اقدام اجرا شد ولی خروجی متنی برنگرداند؛ وضعیت آن در جزئیات تسک قابل
            مشاهده است.
          </p>
        )}
        {view.entries.map((entry) => {
          const text = readableResult(entry.result);
          return (
            <div key={entry.id || entry.title}>
              {view.entries.length > 1 && (
                <p className="mb-2 text-[11px] font-medium text-slate-400">
                  {entry.title}
                </p>
              )}
              <p
                className="whitespace-pre-line rounded-xl border border-line bg-background/60 p-4 text-[13px] leading-8 text-slate-200"
                data-testid="approval-result-text"
              >
                {text ?? JSON.stringify(entry.result, null, 2)}
              </p>
            </div>
          );
        })}
        {view.entries.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[10px] text-slate-600">
              همین خروجی در «جزئیات تسک» هم ذخیره شده است.
            </p>
            <Button size="sm" variant="outline" onClick={copyAll}>
              {copied ? <Check size={14} /> : <ArrowLeft size={14} />}
              {copied ? "کپی شد" : "کپی خروجی"}
            </Button>
          </div>
        )}
      </div>
    </Dialog>
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
