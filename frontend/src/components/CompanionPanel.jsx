import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Loader2,
  MessageCircle,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";
import { PanelTitle } from "./PanelTitle";

const ACTION_LABELS = {
  delete_application_record: "حذف رکورد",
  send_telegram_message: "ارسال پیام تلگرام",
  prepare_salon_outreach: "آماده‌سازی متن پیگیری سالن",
  prepare_project_proposal: "آماده‌سازی پروپوزال",
  generate_outreach_script: "ساخت متن ارتباطی",
  draft_project_proposal: "پروپوزال پروژه",
  prepare_delete: "بررسی حذف",
  create_salon: "افزودن سالن",
  create_task: "ساخت تسک",
  create_personal_project: "ساخت پروژه",
  create_playbook: "ساخت پلی‌بوک",
  set_tool_policy: "تغییر سیاست ابزار",
  set_model_preference: "انتخاب مدل",
  set_default_reminder_window: "تنظیم بازه یادآوری",
  log_salon_interaction: "ثبت تعامل سالن",
  update_salon: "ویرایش سالن",
  update_task: "ویرایش تسک",
  update_personal_project: "ویرایش پروژه",
  schedule_task: "زمان‌بندی تسک",
  add_task_step: "افزودن مرحله تسک",
  run_task: "اجرای تسک",
};

const QUICK_PROMPTS = [
  "امروز چه کاری باید انجام بدهم؟",
  "یک سالن آفتاب با شماره ۰۹۱۲۱۲۳۴۵۶۷ در تهران اضافه کن",
  "یک تسک روزانه ساعت ۹ صبح برای پیگیری پروژه‌ها بساز",
  "وضعیت کارهایم را بررسی کن و سه اولویت امروز را پیشنهاد بده",
];

function mini(value) {
  if (value === null || value === undefined) return null;
  if (typeof value !== "object") return String(value);
  const text = JSON.stringify(value);
  return text.length > 160 ? `${text.slice(0, 160)}…` : text;
}

function ActionCard({ action, onApprovalClick }) {
  const label = ACTION_LABELS[action.name] || action.name;
  const needsApproval = Boolean(action.needs_approval);
  return (
    <div
      data-testid={`action-${action.name}`}
      className={cn(
        "mt-2 rounded-xl border p-3 text-[11px]",
        needsApproval
          ? "border-amber-400/20 bg-amber-400/[.04]"
          : action.ok
            ? "border-emerald-400/15 bg-emerald-400/[.04]"
            : "border-rose-400/20 bg-rose-400/[.04]",
      )}
    >
      <div className="flex items-center gap-2">
        {needsApproval ? (
          <ShieldCheck size={14} className="shrink-0 text-amber-300" />
        ) : action.ok ? (
          <CheckCircle2 size={14} className="shrink-0 text-emerald-300" />
        ) : (
          <XCircle size={14} className="shrink-0 text-rose-300" />
        )}
        <span className="font-medium text-slate-200">{label}</span>
        <span className="mr-auto">
          {needsApproval ? (
            <button
              type="button"
              onClick={onApprovalClick}
              className="rounded-md bg-amber-400/15 px-2 py-0.5 text-[10px] text-amber-200 hover:bg-amber-400/25"
            >
              نیازمند تأیید
            </button>
          ) : action.ok ? (
            <span className="rounded-md bg-emerald-400/15 px-2 py-0.5 text-[10px] text-emerald-200">
              موفق
            </span>
          ) : (
            <span className="rounded-md bg-rose-400/15 px-2 py-0.5 text-[10px] text-rose-200">
              ناموفق
            </span>
          )}
        </span>
      </div>
      {action.arguments && (
        <p className="mt-2 truncate text-slate-600" dir="rtl">
          {mini(action.arguments)}
        </p>
      )}
      {action.result && (
        <p className="mt-1.5 break-words text-slate-500" dir="ltr">
          <span className="text-slate-700">result: </span>
          {mini(action.result)}
        </p>
      )}
      {action.error && (
        <p className="mt-1.5 break-words text-rose-300">{mini(action.error)}</p>
      )}
    </div>
  );
}

export function CompanionPanel({
  system = {},
  approvals = 0,
  onNavigate = () => {},
  onChanged = () => {},
  notify = () => {},
}) {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const composerRef = useRef(null);
  const scrollRef = useRef(null);
  const syncedAfterAction = useRef(false);

  const hasKey = Boolean(system.gemini_configured);

  const loadConversations = useCallback(async () => {
    try {
      const result = await api.listConversations();
      setConversations(result.filter((item) => item.status === "active"));
      return result.filter((item) => item.status === "active");
    } catch (reason) {
      setConnectionError(reason.message);
      return [];
    }
  }, []);

  const openConversation = useCallback(async (id) => {
    setActiveId(id);
    setSidebarOpen(false);
    setLoadingMessages(true);
    setConnectionError(null);
    try {
      const detail = await api.getConversation(id);
      setMessages(
        [...detail.messages].sort(
          (a, b) => (a.created_at || 0) - (b.created_at || 0),
        ),
      );
    } catch (reason) {
      setConnectionError(reason.message);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  const refreshActive = useCallback(async () => {
    if (!activeId) return;
    setLoadingMessages(true);
    try {
      const detail = await api.getConversation(activeId);
      setMessages(
        [...detail.messages].sort(
          (a, b) => (a.created_at || 0) - (b.created_at || 0),
        ),
      );
    } catch {
      /* keep current messages */
    } finally {
      setLoadingMessages(false);
    }
  }, [activeId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingConversations(true);
      const active = await loadConversations();
      if (!cancelled) {
        if (active.length) {
          await openConversation(active[0].id);
        }
        setLoadingConversations(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadConversations, openConversation]);

  useEffect(() => {
    if (activeId) {
      refreshActive();
    }
    // Reload when the approval center may have changed something.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approvals, activeId]);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending, loadingMessages]);

  async function newConversation() {
    try {
      const created = await api.createConversation("گفتگوی جدید");
      setConversations((items) => [created, ...items]);
      setActiveId(created.id);
      setMessages([]);
      setSidebarOpen(true);
      setConnectionError(null);
    } catch (reason) {
      notify(reason.message, "error");
    }
  }

  async function deleteConversation(id) {
    try {
      await api.deleteConversation(id);
      const remaining = conversations.filter((item) => item.id !== id);
      setConversations(remaining);
      if (activeId === id) {
        if (remaining.length) await openConversation(remaining[0].id);
        else {
          setActiveId(null);
          setMessages([]);
        }
      }
      notify("گفتگو حذف شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    }
  }

  async function sendMessage() {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    setSending(true);
    setConnectionError(null);
    try {
      const result = await api.assistantChat({
        message: text,
        conversation_id: activeId,
      });
      setActiveId(result.conversation_id);
      setConversations((items) =>
        items.some((item) => item.id === result.conversation_id)
          ? items
          : [
              {
                id: result.conversation_id,
                title: text.slice(0, 80),
                message_count: 2,
              },
              ...items,
            ],
      );
      setMessages((current) => [
        ...current,
        {
          id: `local-user-${Date.now()}`,
          role: "user",
          content: text,
          actions: [],
          created_at: 0,
        },
        result.message,
      ]);
      const actions = result.message.actions || [];
      const touched =
        actions.length > 0 ||
        actions.some((action) => action.ok && action.result) ||
        result.needs_approval;
      if (touched && !syncedAfterAction.current) {
        syncedAfterAction.current = true;
        onChanged();
        window.setTimeout(() => {
          syncedAfterAction.current = false;
        }, 1200);
      }
    } catch (reason) {
      setDraft(text);
      setConnectionError(reason.message);
    } finally {
      setSending(false);
    }
  }

  async function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await sendMessage();
    }
  }

  const greeting = useMemo(
    () =>
      messages.length === 0 && !loadingMessages && !sending
        ? "سلام، من همراه‌ات هستم. امروز چه کاری می‌خواهی برایت انجام بدهم؟"
        : null,
    [messages.length, loadingMessages, sending],
  );

  return (
    <div data-testid="companion-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="PERSONAL AGENT"
        title="همراه من"
        description="به زبان طبیعی بگو؛ همراه خودش ابزارها را اجرا می‌کند و فقط برای عملیات حساس از تو تأیید می‌گیرد."
        action={
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={newConversation}>
              <Plus size={14} /> گفتگوی جدید
            </Button>
          </div>
        }
      />

      {!hasKey && (
        <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/[.05] p-4 sm:flex-row sm:items-center">
          <div className="flex items-start gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-amber-400/10 text-amber-300">
              <AlertTriangle size={17} />
            </span>
            <div>
              <p className="text-xs font-medium text-amber-100">
                برای استفاده از همراه، کلید Gemini لازم است
              </p>
              <p className="mt-1 text-[10px] leading-5 text-slate-600">
                بدون کلید، بقیه داشبورد و ابزارها عادی کار می‌کنند اما گفتگو
                متوقف است.
              </p>
            </div>
          </div>
          <Button
            className="sm:mr-auto"
            size="sm"
            onClick={() => onNavigate("settings")}
          >
            <Sparkles size={14} /> رفتن به تنظیمات
          </Button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <aside
          className={cn(
            "overflow-hidden rounded-2xl border border-line bg-surface/60 lg:block",
            sidebarOpen ? "block" : "hidden",
          )}
          data-testid="companion-conversations"
        >
          <div className="flex h-10 items-center justify-between border-b border-line/60 px-3">
            <span className="text-[10px] font-bold tracking-wide text-slate-600">
              گفتگوها
            </span>
            <button
              type="button"
              aria-label="بستن فهرست گفتگوها"
              className="text-slate-700 lg:hidden"
              onClick={() => setSidebarOpen(false)}
            >
              <ChevronDown size={14} />
            </button>
          </div>
          <div className="max-h-[300px] overflow-y-auto p-2 lg:max-h-[520px]">
            {loadingConversations ? (
              <p className="p-3 text-[11px] text-slate-700">در حال بارگذاری…</p>
            ) : conversations.length === 0 ? (
              <p className="p-3 text-[11px] leading-6 text-slate-700">
                هنوز گفتگویی ندارید. اولین پیام را بنویسید.
              </p>
            ) : (
              conversations.map((item) => (
                <div
                  key={item.id}
                  data-testid={`conversation-${item.id}-row`}
                  className={cn(
                    "group mb-1 rounded-xl px-3 py-2.5 text-right transition",
                    item.id === activeId
                      ? "bg-primary/[.08] ring-1 ring-inset ring-primary/15"
                      : "hover:bg-white/[.03]",
                  )}
                >
                  <button
                    type="button"
                    className="block w-full text-right"
                    onClick={() => openConversation(item.id)}
                  >
                    <p className="truncate text-[11px] font-medium text-slate-300">
                      {item.title}
                    </p>
                    {item.last_message && (
                      <p className="mt-1 truncate text-[9px] text-slate-700">
                        {item.last_message}
                      </p>
                    )}
                  </button>
                  <button
                    type="button"
                    aria-label={`حذف گفتگو ${item.id}`}
                    className="mt-1 text-[9px] text-slate-700 opacity-0 transition group-hover:opacity-100"
                    onClick={() => deleteConversation(item.id)}
                  >
                    <Trash2 size={12} className="inline" /> حذف
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>

        <section className="flex min-h-[540px] flex-col overflow-hidden rounded-2xl border border-line bg-surface/60">
          <div className="flex h-11 shrink-0 items-center justify-between border-b border-line/60 px-4">
            <div className="flex items-center gap-2">
              <span className="grid size-6 place-items-center rounded-lg bg-primary/[.12] text-primary-soft">
                <MessageCircle size={13} />
              </span>
              <span className="text-[11px] font-medium text-slate-300">
                {activeId ? "گفتگوی فعال" : "گفتگوی جدید"}
              </span>
              {approvals > 0 && (
                <button
                  type="button"
                  data-testid="companion-approval-link"
                  onClick={() => onNavigate("approval")}
                  className="flex items-center gap-1 rounded-lg bg-amber-400/10 px-2 py-1 text-[10px] text-amber-200 hover:bg-amber-400/20"
                >
                  <ShieldCheck size={12} /> {approvals} نیازمند تأیید
                </button>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="تازه‌سازی گفتگو"
              onClick={refreshActive}
            >
              <RefreshCw size={14} />
            </Button>
          </div>

          <div
            ref={scrollRef}
            className="chat-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4"
            data-testid="companion-messages"
          >
            {greeting && (
              <div className="mx-auto max-w-md rounded-2xl border border-primary/10 bg-primary/[.04] p-5 text-center">
                <span className="mx-auto grid size-11 place-items-center rounded-2xl bg-primary/[.10] text-primary-soft">
                  <Bot size={22} />
                </span>
                <p className="mt-3 text-sm font-medium leading-7 text-slate-200">
                  سلام، من همراه‌ات هستم. امروز چه کاری می‌خواهی برایت انجام
                  بدهم؟
                </p>
                <p className="mt-2 text-[10px] leading-6 text-slate-600">
                  سالن بساز، تسک روزانه بگذار، پروژه را فعال کن یا وضعیت را
                  بپرس؛ بقیه‌اش با من.
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  {QUICK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="rounded-lg border border-line bg-white/[.02] px-2.5 py-1.5 text-[10px] text-slate-400 transition hover:border-primary/30 hover:text-slate-200"
                      onClick={() => setDraft(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message, index) => (
              <div
                key={`${message.id}-${index}`}
                data-testid={`message-${message.role}`}
                className={cn(
                  "mb-3 flex",
                  message.role === "user" && "justify-start",
                )}
              >
                <div
                  className={cn(
                    "max-w-[86%] rounded-2xl px-4 py-3 text-xs leading-6",
                    message.role === "user"
                      ? "rounded-tr-md bg-primary/[.14] text-slate-100"
                      : "rounded-tl-md border border-line bg-panel text-slate-300",
                  )}
                >
                  {message.content && (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  )}
                  {(message.actions || []).map((action, actionIndex) => (
                    <ActionCard
                      key={`${action.name}-${actionIndex}`}
                      action={action}
                      onApprovalClick={() => onNavigate("approval")}
                    />
                  ))}
                  {message.role === "assistant" &&
                    message.provider_message_id && (
                      <p
                        className="mt-2 rounded-lg bg-emerald-400/[.06] px-2 py-1 text-[10px] text-emerald-200"
                        dir="ltr"
                      >
                        ✓ provider message_id: {message.provider_message_id}
                      </p>
                    )}
                </div>
              </div>
            ))}

            {loadingMessages && (
              <div className="flex items-center gap-2 text-[11px] text-slate-600">
                <Loader2 size={14} className="animate-spin" /> در حال بارگذاری…
              </div>
            )}

            {sending && (
              <div
                className="flex items-center gap-2 text-[11px] text-slate-600"
                data-testid="typing-indicator"
              >
                <span className="flex gap-1">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </span>
                همراه در حال فکر کردن…
              </div>
            )}

            {connectionError && (
              <div
                className="mt-3 rounded-xl border border-rose-400/20 bg-rose-400/[.05] p-3"
                data-testid="chat-error"
              >
                <p className="flex items-center gap-2 text-[11px] text-rose-200">
                  <AlertTriangle size={13} /> {connectionError}
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-2"
                  onClick={sendMessage}
                >
                  <RefreshCw size={13} /> تلاش دوباره
                </Button>
              </div>
            )}
          </div>

          <div className="shrink-0 border-t border-line/60 p-3">
            <textarea
              ref={composerRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              maxLength={4000}
              disabled={!hasKey}
              placeholder={
                hasKey
                  ? "الان چه کاری انجام بدهم؟ (Enter ارسال — Shift+Enter خط جدید)"
                  : "برای گفتگو ابتدا کلید Gemini را در تنظیمات اضافه کن"
              }
              aria-label="پیام به همراه"
              className="min-h-[64px] w-full resize-none rounded-xl border border-line bg-elevated/60 px-3 py-2.5 text-xs text-slate-200 placeholder:text-slate-700 focus:border-primary/40 focus:outline-none disabled:opacity-50"
              style={{ maxHeight: 160 }}
            />
            <div className="mt-2 flex items-center justify-between">
              <p className="text-[9px] text-slate-700">
                Enter ارسال • Shift+Enter خط جدید
              </p>
              <Button
                size="sm"
                onClick={sendMessage}
                disabled={!hasKey || sending || !draft.trim()}
              >
                {sending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Send size={14} />
                )}
                ارسال
              </Button>
            </div>
          </div>
        </section>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-700">
        <span className="flex items-center gap-1">
          <BrainCircuit size={12} />
          مدل فعال: {system.reasoning_model || "—"}
        </span>
        <span className="flex items-center gap-1">
          <Clock3 size={12} />
          منطقه زمانی: {system.timezone || "—"}
        </span>
        <span className="flex items-center gap-1">
          <ShieldCheck size={12} />
          {approvals > 0
            ? `${approvals} عملیات در انتظار تأیید`
            : "بدون عملیات در انتظار تأیید"}
        </span>
      </div>
    </div>
  );
}
