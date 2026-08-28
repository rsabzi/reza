import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  Copy,
  ListPlus,
  Pencil,
  Play,
  RefreshCw,
  Repeat2,
  Route,
  ShieldAlert,
  Trash2,
  Wrench,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { faDate, faNumber, toolLabels } from "../lib/format";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { ConfirmDialog, Dialog } from "./ui/dialog";
import { Field, Input, Select, Textarea } from "./ui/input";
import { EmptyState } from "./EmptyState";
import { PanelTitle } from "./PanelTitle";

const stepIcons = {
  done: CheckCircle2,
  running: Play,
  needs_approval: ShieldAlert,
  waiting_for_user: Clock3,
  failed: X,
};

export function TaskDetail({
  task,
  tools = [],
  busy = false,
  onBack = () => {},
  onPlan = () => {},
  onExecute = () => {},
  onChanged = () => {},
  onDeleted = () => {},
  onDecision = () => {},
  notify = () => {},
}) {
  const [editOpen, setEditOpen] = useState(false);
  const [stepOpen, setStepOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [localError, setLocalError] = useState("");

  if (!task) {
    return (
      <div data-testid="task-detail-panel" className="animate-fade-in">
        <PanelTitle eyebrow="TASK DETAIL" title="جزئیات تسک" />
        <EmptyState
          icon={Route}
          title="یک تسک را انتخاب کنید"
          description="از صندوق تسک‌ها یک مورد را باز کنید تا برنامه اجرا را ببینید."
          action={
            <Button variant="secondary" onClick={onBack}>
              <ArrowRight size={16} />
              بازگشت به صندوق
            </Button>
          }
        />
      </div>
    );
  }

  const steps = task.steps || [];
  const completed = steps.filter((step) => step.status === "done").length;
  const progress = steps.length
    ? Math.round((completed / steps.length) * 100)
    : 0;

  async function refreshTask(message) {
    const fresh = await api.getTask(task.id);
    onChanged(fresh);
    if (message) notify(message, "success");
  }

  async function updateTask(payload) {
    setSaving(true);
    setLocalError("");
    try {
      await api.updateTask(task.id, payload);
      await refreshTask("تغییرات تسک ذخیره شد");
      setEditOpen(false);
    } catch (reason) {
      setLocalError(reason.message);
    } finally {
      setSaving(false);
    }
  }

  async function addStep(payload) {
    setSaving(true);
    setLocalError("");
    try {
      await api.createStep({
        task_id: task.id,
        position: steps.length
          ? Math.max(...steps.map((item) => item.position)) + 1
          : 0,
        ...payload,
      });
      await refreshTask("قدم جدید به مسیر اجرا اضافه شد");
      setStepOpen(false);
    } catch (reason) {
      setLocalError(reason.message);
    } finally {
      setSaving(false);
    }
  }

  async function deleteTask() {
    setSaving(true);
    try {
      await api.deleteTask(task.id);
      notify("تسک حذف شد", "success");
      onDeleted(task);
      setDeleteOpen(false);
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function deleteStep(step) {
    try {
      await api.deleteStep(step.id);
      await refreshTask("قدم حذف شد");
    } catch (reason) {
      notify(reason.message, "error");
    }
  }

  async function completeManualStep(step) {
    try {
      await api.updateStep(step.id, {
        status: "done",
        result: { note: "توسط کاربر تکمیل شد" },
      });
      await refreshTask("قدم به‌عنوان انجام‌شده ثبت شد");
    } catch (reason) {
      notify(reason.message, "error");
    }
  }

  async function decide(step, action) {
    setSaving(true);
    try {
      const updated =
        action === "approve"
          ? await api.approveStep(step.id)
          : await api.rejectStep(step.id);
      onDecision(step, updated);
      notify(
        action === "approve" ? "اقدام تأیید و ادامه اجرا شد" : "اقدام رد شد",
        "success",
      );
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function runNow() {
    setSaving(true);
    try {
      const instance = await api.runTaskNow(task.id);
      notify(
        `نسخه جدید تسک با شناسه ${faNumber(instance.id)} ساخته شد`,
        "success",
      );
      onChanged(task, { refreshAll: true });
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div data-testid="task-detail-panel" className="animate-fade-in">
      <button
        onClick={onBack}
        className="mb-4 flex items-center gap-2 text-xs text-slate-500 transition hover:text-white"
      >
        <ArrowRight size={14} />
        بازگشت به تسک‌ها
      </button>
      <PanelTitle
        eyebrow={`TASK #${faNumber(task.id)}`}
        title={task.title}
        description={
          task.description || "برای این تسک توضیحات اضافه‌ای ثبت نشده است."
        }
        meta={<Badge status={task.status} dot />}
        action={
          <>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setEditOpen(true)}
              aria-label="ویرایش تسک"
            >
              <Pencil size={16} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="text-rose-300"
              onClick={() => setDeleteOpen(true)}
              aria-label="حذف تسک"
            >
              <Trash2 size={16} />
            </Button>
            {task.recurrence_rule && (
              <Button variant="secondary" onClick={runNow} loading={saving}>
                <Repeat2 size={16} />
                اجرای همین حالا
              </Button>
            )}
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => onPlan(task.id)}
            >
              <Bot size={16} />
              برنامه‌ریزی AI
            </Button>
            <Button
              disabled={busy || !steps.length}
              onClick={() => onExecute(task.id)}
            >
              <Play size={16} />
              اجرای مسیر
            </Button>
          </>
        }
      />

      {localError && (
        <div
          className="mb-4 rounded-xl border border-rose-400/15 bg-rose-400/[.06] p-3 text-xs text-rose-300"
          role="alert"
        >
          {localError}
        </div>
      )}

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <InfoBox
          label="پیشرفت"
          value={`${faNumber(progress)}٪`}
          helper={`${faNumber(completed)} از ${faNumber(steps.length)} قدم`}
        />
        <InfoBox
          label="ماژول"
          value={
            task.module_name === "salon"
              ? "سالن"
              : task.module_name === "personal"
                ? "شخصی"
                : "عمومی"
          }
          helper="حوزه اجرای تسک"
        />
        <InfoBox
          label="زمان‌بندی"
          value={
            task.recurrence_rule ? `روزانه ${task.scheduled_time}` : "یک‌بار"
          }
          helper={task.recurrence_rule ? "تکرار خودکار فعال" : "بدون تکرار"}
        />
        <InfoBox
          label="ایجاد"
          value={faDate(task.created_at, { year: undefined })}
          helper={`آخرین تغییر: ${faDate(task.updated_at, { year: undefined })}`}
        />
      </div>

      <Card>
        <CardHeader>
          <div>
            <h2 className="font-semibold text-white">مسیر اجرا</h2>
            <p className="mt-1 text-[11px] text-slate-600">
              قدم‌ها به ترتیب اجرا می‌شوند و در نقاط حساس متوقف خواهند شد.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setStepOpen(true)}>
            <ListPlus size={15} />
            افزودن قدم دستی
          </Button>
        </CardHeader>
        <CardContent>
          {steps.length === 0 ? (
            <EmptyState
              icon={Route}
              title="هنوز برنامه‌ای ساخته نشده"
              description="از برنامه‌ریزی AI استفاده کن یا قدم‌ها را دستی اضافه کن؛ اجرای دستی بدون کلید Gemini هم ممکن است."
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setStepOpen(true)}
                >
                  <ListPlus size={15} />
                  اولین قدم را اضافه کن
                </Button>
              }
            />
          ) : (
            <ol className="relative space-y-2 before:absolute before:bottom-7 before:right-[21px] before:top-7 before:w-px before:bg-line">
              {steps.map((step, index) => (
                <StepRow
                  key={step.id}
                  step={step}
                  index={index}
                  saving={saving}
                  onDelete={() => deleteStep(step)}
                  onComplete={() => completeManualStep(step)}
                  onDecision={(action) => decide(step, action)}
                  notify={notify}
                />
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <EditTaskDialog
        task={task}
        open={editOpen}
        onClose={() => {
          setEditOpen(false);
          setLocalError("");
        }}
        onSave={updateTask}
        loading={saving}
        error={localError}
      />
      <AddStepDialog
        tools={tools}
        open={stepOpen}
        onClose={() => {
          setStepOpen(false);
          setLocalError("");
        }}
        onSave={addStep}
        loading={saving}
        error={localError}
      />
      <ConfirmDialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={deleteTask}
        loading={saving}
        title="حذف این تسک؟"
        description="تمام قدم‌های وابسته نیز حذف می‌شوند. این عملیات قابل بازگشت نیست."
      />
    </div>
  );
}

function InfoBox({ label, value, helper }) {
  return (
    <div className="rounded-xl border border-line/70 bg-surface/70 p-4">
      <p className="text-[10px] text-slate-600">{label}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
      <p className="mt-1 truncate text-[10px] text-slate-700">{helper}</p>
    </div>
  );
}

function StepRow({
  step,
  index,
  saving,
  onDelete,
  onComplete,
  onDecision,
  notify,
}) {
  const [expanded, setExpanded] = useState(false);
  const Icon = stepIcons[step.status] || Circle;
  const canDelete = ["pending", "cancelled", "failed"].includes(step.status);
  async function copyResult() {
    await navigator.clipboard?.writeText(
      typeof step.result === "string"
        ? step.result
        : JSON.stringify(step.result, null, 2),
    );
    notify("نتیجه در کلیپ‌بورد کپی شد", "success");
  }
  return (
    <li className="relative rounded-xl transition hover:bg-white/[.018]">
      <div className="flex gap-3 p-3">
        <div
          className={`z-10 grid size-11 shrink-0 place-items-center rounded-xl border bg-surface ${step.status === "done" ? "border-emerald-400/20 text-emerald-300" : step.status === "needs_approval" ? "border-violet-400/25 text-violet-300" : step.status === "failed" ? "border-rose-400/20 text-rose-300" : "border-line text-slate-500"}`}
        >
          <Icon size={18} />
        </div>
        <div className="min-w-0 flex-1 pt-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] text-slate-700">
              {faNumber(index + 1)}
            </span>
            <h3 className="text-sm font-medium text-slate-200">{step.title}</h3>
            <Badge status={step.status} />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[10px] text-slate-600">
            {step.tool_name ? (
              <span className="flex items-center gap-1">
                <Wrench size={11} />
                {toolLabels[step.tool_name] || step.tool_name}
              </span>
            ) : (
              <span>قدم دستی</span>
            )}
            {step.error && <span className="text-rose-300">{step.error}</span>}
          </div>
          {(step.result != null ||
            Object.keys(step.arguments || {}).length > 0) && (
            <button
              className="mt-2 text-[10px] text-primary-soft hover:text-white"
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? "بستن جزئیات" : "مشاهده ورودی و خروجی"}
            </button>
          )}
          {expanded && (
            <div className="mt-3 grid gap-2 lg:grid-cols-2">
              {Object.keys(step.arguments || {}).length > 0 && (
                <CodeBox label="ورودی" value={step.arguments} />
              )}
              {step.result != null && (
                <div className="relative">
                  <CodeBox label="خروجی" value={step.result} />
                  <button
                    aria-label="کپی نتیجه"
                    onClick={copyResult}
                    className="absolute left-2 top-2 text-slate-600 hover:text-white"
                  >
                    <Copy size={13} />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-start gap-1">
          {step.status === "needs_approval" && (
            <>
              <Button
                size="xs"
                variant="danger"
                disabled={saving}
                onClick={() => onDecision("reject")}
              >
                <X size={13} />
                رد
              </Button>
              <Button
                size="xs"
                variant="success"
                disabled={saving}
                onClick={() => onDecision("approve")}
              >
                <Check size={13} />
                تأیید
              </Button>
            </>
          )}
          {!step.tool_name && step.status === "pending" && (
            <Button size="xs" variant="success" onClick={onComplete}>
              <Check size={13} />
              انجام شد
            </Button>
          )}
          {canDelete && (
            <Button
              size="icon"
              variant="ghost"
              className="size-8 text-slate-600 hover:text-rose-300"
              onClick={onDelete}
              aria-label="حذف قدم"
            >
              <Trash2 size={14} />
            </Button>
          )}
        </div>
      </div>
    </li>
  );
}

function CodeBox({ label, value }) {
  return (
    <div className="rounded-xl border border-line/70 bg-background/70 p-3">
      <p className="mb-2 text-right text-[9px] font-bold text-slate-600">
        {label}
      </p>
      <pre
        dir="ltr"
        className="max-h-52 overflow-auto whitespace-pre-wrap text-left text-[10px] leading-5 text-slate-400"
      >
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function EditTaskDialog({ task, open, onClose, onSave, loading, error }) {
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description || "");
  const [status, setStatus] = useState(task.status);
  useEffect(() => {
    setTitle(task.title);
    setDescription(task.description || "");
    setStatus(task.status);
  }, [task]);
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="ویرایش تسک"
      description="عنوان، توضیح و وضعیت فعلی را به‌روزرسانی کن."
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSave({ title, description: description || null, status });
        }}
        className="space-y-4"
      >
        <Field label="عنوان">
          <Input
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </Field>
        <Field label="توضیحات">
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </Field>
        <Field label="وضعیت">
          <Select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="pending">در انتظار</option>
            <option value="planned">برنامه‌ریزی‌شده</option>
            <option value="paused">متوقف</option>
            <option value="done">انجام‌شده</option>
            <option value="cancelled">لغوشده</option>
          </Select>
        </Field>
        {error && <p className="text-xs text-rose-300">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
          <Button type="submit" loading={loading}>
            ذخیره تغییرات
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function AddStepDialog({ tools, open, onClose, onSave, loading, error }) {
  const [title, setTitle] = useState("");
  const [toolName, setToolName] = useState("");
  const [argumentsText, setArgumentsText] = useState("{}");
  const [parseError, setParseError] = useState("");
  function submit(event) {
    event.preventDefault();
    setParseError("");
    let args = {};
    try {
      args = toolName ? JSON.parse(argumentsText || "{}") : {};
    } catch {
      setParseError("ورودی ابزار باید JSON معتبر باشد");
      return;
    }
    onSave({ title, tool_name: toolName || null, arguments: args });
  }
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="افزودن قدم اجرایی"
      description="برای اجرای خودکار ابزار انتخاب کن؛ قدم بدون ابزار را می‌توانی دستی تکمیل کنی."
    >
      <form onSubmit={submit} className="space-y-4">
        <Field label="عنوان قدم">
          <Input
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="مثلاً بررسی خروجی نهایی"
          />
        </Field>
        <Field label="ابزار" hint="اختیاری">
          <Select
            value={toolName}
            onChange={(event) => setToolName(event.target.value)}
          >
            <option value="">بدون ابزار — انجام دستی</option>
            {tools
              .filter((tool) => tool.enabled)
              .map((tool) => (
                <option key={tool.name} value={tool.name}>
                  {toolLabels[tool.name] || tool.name}
                </option>
              ))}
          </Select>
        </Field>
        {toolName && (
          <Field label="آرگومان‌های ابزار" hint="JSON" error={parseError}>
            <Textarea
              dir="ltr"
              className="font-mono text-xs"
              value={argumentsText}
              onChange={(event) => setArgumentsText(event.target.value)}
            />
          </Field>
        )}
        {error && <p className="text-xs text-rose-300">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
          <Button type="submit" loading={loading}>
            <ListPlus size={15} />
            افزودن قدم
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
