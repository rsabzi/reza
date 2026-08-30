import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  BrainCircuit,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCopy,
  Clock3,
  Gauge,
  Loader2,
  Maximize2,
  MessageCircle,
  MessagesSquare,
  Mic,
  Plus,
  RefreshCw,
  Scissors,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";
import { PanelTitle } from "./PanelTitle";
import { RichText } from "../lib/markdown";

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
  { icon: CalendarDays, text: "امروز چه کاری باید انجام بدهم؟" },
  {
    icon: Scissors,
    text: "یک سالن آفتاب با شماره ۰۹۱۲۱۲۳۴۵۶۷ در تهران اضافه کن",
  },
  {
    icon: Clock3,
    text: "یک تسک روزانه ساعت ۹ صبح برای پیگیری پروژه‌ها بساز",
  },
  {
    icon: Gauge,
    text: "وضعیت کارهایم را بررسی کن و سه اولویت امروز را پیشنهاد بده",
  },
];

const CAPABILITY_CHIPS = [
  "سالن جدید اضافه کن",
  "برای من یک تسک بساز",
  "پروپوزال پروژه را آماده کن",
  "در حافظه‌ام جستجو کن",
];

function formatTime(value) {
  if (!value || value === 0) return "اکنون";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("fa-IR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function stringify(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function ActionCard({ action, onApprovalClick }) {
  const [expanded, setExpanded] = useState(true);
  const label = ACTION_LABELS[action.name] || action.name;
  const needsApproval = Boolean(action.needs_approval);
  const status = needsApproval ? "pending" : action.ok ? "ok" : "fail";
  return (
    <div
      data-testid={`action-${action.name}`}
      className={cn(
        "mt-2.5 overflow-hidden rounded-xl border text-[11px] transition",
        status === "pending" &&
          "border-amber-400/25 bg-amber-400/[.05] shadow-[0_0_24px_rgba(251,191,36,.05)]",
        status === "ok" && "border-emerald-400/15 bg-emerald-400/[.04]",
        status === "fail" &&
          "border-rose-400/25 bg-rose-400/[.05] shadow-[0_0_24px_rgba(244,63,94,.05)]",
      )}
    >
      <div className="flex items-center gap-2 px-3 pt-2.5">
        <span
          className={cn(
            "grid size-6 shrink-0 place-items-center rounded-lg",
            status === "pending" && "bg-amber-400/15 text-amber-300",
            status === "ok" && "bg-emerald-400/15 text-emerald-300",
            status === "fail" && "bg-rose-400/15 text-rose-300",
          )}
        >
          {status === "pending" ? (
            <ShieldCheck size={13} />
          ) : status === "ok" ? (
            <CheckCircle2 size={13} />
          ) : (
            <XCircle size={13} />
          )}
        </span>
        <span className="min-w-0 flex-1 truncate font-semibold text-slate-200">
          {label}
        </span>
        {status === "pending" ? (
          <button
            type="button"
            onClick={onApprovalClick}
            className="flex shrink-0 items-center gap-1 rounded-lg bg-amber-400/15 px-2 py-1 text-[10px] font-medium text-amber-200 transition hover:bg-amber-400/30"
          >
            <ShieldCheck size={11} />
            نیازمند تأیید
          </button>
        ) : (
          <span
            className={cn(
              "shrink-0 rounded-lg px-2 py-1 text-[10px] font-medium",
              status === "ok"
                ? "bg-emerald-400/15 text-emerald-200"
                : "bg-rose-400/15 text-rose-200",
            )}
          >
            {status === "ok" ? "موفق" : "ناموفق"}
          </span>
        )}
        {(action.arguments || action.result || action.error) && (
          <button
            type="button"
            aria-label="باز و بسته کردن جزئیات ابزار"
            onClick={() => setExpanded((value) => !value)}
            className="grid size-6 shrink-0 place-items-center rounded-lg text-slate-600 transition hover:bg-white/[.05] hover:text-slate-300"
          >
            <ChevronDown
              size={13}
              className={cn("transition", expanded ? "rotate-180" : "")}
            />
          </button>
        )}
      </div>
      {expanded && (
        <div className="space-y-1.5 px-3 pb-2.5 pt-2">
          {action.arguments && (
            <p
              className="whitespace-pre-wrap break-all rounded-lg bg-black/25 p-2 font-mono text-[9.5px] leading-4 text-slate-500"
              dir="ltr"
            >
              <span className="text-slate-700">args </span>
              {stringify(action.arguments)}
            </p>
          )}
          {action.result && (
            <p
              className="whitespace-pre-wrap break-all rounded-lg bg-black/25 p-2 font-mono text-[9.5px] leading-4 text-emerald-200/80"
              dir="ltr"
            >
              <span className="text-emerald-300/50">result </span>
              {stringify(action.result)}
            </p>
          )}
          {action.error && (
            <p
              className="whitespace-pre-wrap break-all rounded-lg bg-black/25 p-2 font-mono text-[9.5px] leading-4 text-rose-300/90"
              dir="ltr"
            >
              <span className="text-rose-300/50">error </span>
              {stringify(action.error)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable */
    }
  }
  return (
    <button
      type="button"
      aria-label="کپی پاسخ"
      onClick={copy}
      className={cn(
        "grid size-6 place-items-center rounded-lg transition",
        copied
          ? "text-emerald-300"
          : "text-slate-600 opacity-0 hover:bg-white/[.05] hover:text-slate-300 group-hover:opacity-100 focus-visible:opacity-100",
      )}
    >
      {copied ? <Check size={12} /> : <ClipboardCopy size={12} />}
    </button>
  );
}

function AssistantAvatar({ thinking = false, size = "md" }) {
  return (
    <span
      className={cn(
        "hamrah-orb grid shrink-0 place-items-center text-white",
        size === "sm" ? "size-7" : "size-9",
        thinking ? "hamrah-orb--thinking" : "hamrah-orb--idle",
      )}
    >
      {thinking ? (
        <Loader2 size={size === "sm" ? 12 : 15} className="animate-spin" />
      ) : (
        <Bot size={size === "sm" ? 13 : 17} strokeWidth={2} />
      )}
    </span>
  );
}

export function CompanionPanel({
  system = {},
  approvals = 0,
  onNavigate = () => {},
  onChanged = () => {},
  notify = () => {},
  variant = "page",
  onExpand = null,
}) {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(variant !== "dock");
  const [listening, setListening] = useState(false);
  const abortRef = useRef(null);
  const composerRef = useRef(null);
  const scrollRef = useRef(null);
  const syncedAfterAction = useRef(false);
  const recognitionRef = useRef(null);

  const hasKey = Boolean(system.gemini_configured);
  const isDock = variant === "dock";

  const speechAvailable =
    typeof window !== "undefined" &&
    Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

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

  useEffect(
    () => () => {
      if (abortRef.current) abortRef.current.abort();
    },
    [],
  );

  async function newConversation() {
    try {
      const created = await api.createConversation("گفتگوی جدید");
      setConversations((items) => [created, ...items]);
      setActiveId(created.id);
      setMessages([]);
      setSidebarOpen(false);
      setConnectionError(null);
      if (composerRef.current) composerRef.current.focus();
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

  function stopGeneration() {
    if (abortRef.current) abortRef.current.abort();
  }

  async function sendMessage() {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    setSending(true);
    setConnectionError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const result = await api.assistantChat(
        {
          message: text,
          conversation_id: activeId,
        },
        controller.signal,
      );
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
      if (reason?.isAbort && reason.external) {
        setMessages((current) => [
          ...current,
          {
            id: `local-user-${Date.now()}`,
            role: "user",
            content: text,
            actions: [],
            created_at: 0,
          },
          {
            id: `local-stop-${Date.now()}`,
            role: "assistant",
            content: "⏹ تولید پاسخ متوقف شد.",
            actions: [],
            created_at: 0,
            stopped: true,
          },
        ]);
        setDraft(text);
      } else {
        setDraft(text);
        setConnectionError(reason.message);
      }
    } finally {
      setSending(false);
      abortRef.current = null;
    }
  }

  async function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await sendMessage();
    }
  }

  function autoGrow(event) {
    const el = event.currentTarget;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  function toggleVoice() {
    const SpeechRecognitionImpl =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionImpl) return;
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    try {
      const recognition = new SpeechRecognitionImpl();
      recognition.lang = "fa-IR";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onresult = (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript;
        if (transcript) {
          setDraft((current) =>
            current ? `${current} ${transcript}` : transcript,
          );
        }
      };
      recognition.onend = () => setListening(false);
      recognition.onerror = () => setListening(false);
      recognitionRef.current = recognition;
      recognition.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  }

  const greeting = useMemo(
    () =>
      messages.length === 0 && !loadingMessages && !sending
        ? "سلام، من همراه‌ات هستم. امروز چه کاری می‌خواهی برایت انجام بدهم؟"
        : null,
    [messages.length, loadingMessages, sending],
  );

  const conversationList = (
    <>
      <div className="flex items-center justify-between border-b border-line/60 px-3 py-2.5">
        <span className="flex items-center gap-1.5 text-[10px] font-semibold text-slate-400">
          <MessagesSquare size={12} />
          گفتگوها
        </span>
        {isDock && (
          <button
            type="button"
            aria-label="بستن فهرست گفتگوها"
            className="grid size-6 place-items-center rounded-lg text-slate-600 transition hover:bg-white/[.05] hover:text-slate-300"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={13} />
          </button>
        )}
      </div>
      <div className="chat-scroll flex-1 overflow-y-auto p-2">
        {loadingConversations ? (
          <p className="p-3 text-[11px] text-slate-600">در حال بارگذاری…</p>
        ) : conversations.length === 0 ? (
          <p className="p-3 text-[11px] leading-6 text-slate-600">
            هنوز گفتگویی ندارید. اولین پیام را بنویسید.
          </p>
        ) : (
          conversations.map((item) => (
            <div
              key={item.id}
              data-testid={`conversation-${item.id}-row`}
              className={cn(
                "group mb-1 flex items-center gap-1 rounded-xl px-2 py-2 text-right transition",
                item.id === activeId
                  ? "border border-primary/15 bg-primary/[.08]"
                  : "border border-transparent hover:bg-white/[.03]",
              )}
            >
              <button
                type="button"
                className="min-w-0 flex-1 text-right"
                onClick={() => openConversation(item.id)}
              >
                <p className="truncate text-[11px] font-medium text-slate-300">
                  {item.title}
                </p>
                {item.last_message && (
                  <p className="mt-0.5 truncate text-[9px] text-slate-600">
                    {item.last_message}
                  </p>
                )}
              </button>
              <button
                type="button"
                aria-label={`حذف گفتگو ${item.id}`}
                className="grid size-6 shrink-0 place-items-center rounded-lg text-slate-600 opacity-0 transition hover:bg-rose-400/10 hover:text-rose-300 group-hover:opacity-100 focus-visible:opacity-100"
                onClick={() => deleteConversation(item.id)}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))
        )}
      </div>
      <div className="border-t border-line/60 p-2">
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={newConversation}
        >
          <Plus size={13} /> گفتگوی جدید
        </Button>
      </div>
    </>
  );

  const thread = (
    <div
      ref={scrollRef}
      className="chat-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5"
      data-testid="companion-messages"
    >
      {greeting && (
        <div className="mx-auto max-w-md animate-slide-up">
          <div className="flex flex-col items-center text-center">
            <span className="hamrah-orb grid size-16 place-items-center text-white">
              <Bot size={30} strokeWidth={1.8} />
            </span>
            <h3 className="mt-4 text-balance text-base font-bold text-white">
              سلام، من همراه‌ات هستم. امروز چه کاری می‌خواهی برایت انجام بدهم؟
            </h3>
            <p className="mt-2 text-[11px] leading-6 text-slate-500">
              سالن بساز، تسک روزانه بگذار، پروژه را فعال کن یا وضعیت را بپرس؛
              بقیه‌اش با من.
            </p>
          </div>

          {!hasKey && isDock && (
            <div className="mt-5 flex flex-col items-center gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/[.05] p-4 text-center">
              <p className="text-xs font-semibold text-amber-100">
                برای استفاده از همراه، کلید Gemini لازم است
              </p>
              <p className="text-[10px] leading-5 text-slate-500">
                بدون کلید، بقیه داشبورد و ابزارها عادی کار می‌کنند اما گفتگو
                متوقف است.
              </p>
              <Button
                size="sm"
                onClick={() => onNavigate("settings")}
                className="mt-1"
              >
                <Sparkles size={13} /> رفتن به تنظیمات
              </Button>
            </div>
          )}

          <p className="mt-6 text-center text-[9px] font-semibold text-slate-600">
            با یکی از این‌ها شروع کن
          </p>
          <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
            {QUICK_PROMPTS.map(({ icon: Icon, text }) => (
              <button
                key={text}
                type="button"
                className="group flex items-center gap-2.5 rounded-xl border border-line/80 bg-white/[.02] px-3 py-2.5 text-right text-[10.5px] leading-5 text-slate-400 transition hover:border-primary/35 hover:bg-primary/[.05] hover:text-slate-200"
                onClick={() => setDraft(text)}
              >
                <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-white/[.04] text-slate-500 transition group-hover:bg-primary/15 group-hover:text-primary-soft">
                  <Icon size={13} />
                </span>
                <span className="min-w-0">{text}</span>
              </button>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap justify-center gap-1.5">
            {CAPABILITY_CHIPS.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => setDraft(chip)}
                className="rounded-full border border-line/80 bg-white/[.02] px-2.5 py-1 text-[9.5px] text-slate-500 transition hover:border-primary/30 hover:text-primary-soft"
              >
                {chip}
              </button>
            ))}
          </div>
        </div>
      )}

      {messages.map((message, index) => {
        const isUser = message.role === "user";
        return (
          <div
            key={`${message.id}-${index}`}
            data-testid={`message-${message.role}`}
            className={cn(
              "group mb-4 flex animate-slide-up items-end gap-2.5",
              isUser ? "justify-start" : "justify-end",
            )}
          >
            {!isUser && <AssistantAvatar size="sm" />}
            <div
              className={cn(
                "max-w-[86%] sm:max-w-[78%]",
                message.stopped && "opacity-70",
              )}
            >
              <div
                className={cn(
                  "rounded-2xl px-4 py-3 text-xs leading-6",
                  isUser
                    ? "rounded-tr-md border border-primary/25 bg-gradient-to-bl from-primary/30 to-primary/[.12] text-slate-100 shadow-bubble"
                    : "glass hairline rounded-tl-md text-slate-300 shadow-bubble",
                )}
              >
                {message.content && (
                  <RichText text={message.content} />
                )}
                {(message.actions || []).map((action, actionIndex) => (
                  <ActionCard
                    key={`${action.name}-${actionIndex}`}
                    action={action}
                    onApprovalClick={() => onNavigate("approval")}
                  />
                ))}
                {!isUser && message.provider_message_id && (
                  <p
                    className="mt-2.5 rounded-lg bg-emerald-400/[.06] px-2 py-1 text-[9.5px] text-emerald-200/80"
                    dir="ltr"
                  >
                    ✓ provider message_id: {message.provider_message_id}
                  </p>
                )}
              </div>
              <div
                className={cn(
                  "mt-1.5 flex items-center gap-2 text-[9px] text-slate-600",
                  isUser ? "justify-start" : "justify-end",
                )}
              >
                {!isUser && message.content && (
                  <CopyButton text={message.content} />
                )}
                <span>{formatTime(message.created_at)}</span>
              </div>
            </div>
          </div>
        );
      })}

      {loadingMessages && (
        <div className="flex items-center gap-2 text-[11px] text-slate-500">
          <Loader2 size={14} className="animate-spin" /> در حال بارگذاری…
        </div>
      )}

      {sending && (
        <div
          className="mb-4 flex animate-slide-up items-end gap-2.5"
          data-testid="typing-indicator"
        >
          <AssistantAvatar thinking size="sm" />
          <div className="glass hairline rounded-2xl rounded-tl-md px-4 py-3.5 shadow-bubble">
            <span className="flex items-center gap-1.5">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </span>
            <span className="mt-2 block text-[9.5px] text-slate-500">
              همراه در حال فکر کردن…
            </span>
          </div>
        </div>
      )}

      {connectionError && (
        <div
          className="mt-3 animate-slide-up rounded-xl border border-rose-400/20 bg-rose-400/[.05] p-3"
          data-testid="chat-error"
        >
          <p className="flex items-center gap-2 text-[11px] leading-5 text-rose-200">
            <AlertTriangle size={13} className="shrink-0" />
            {connectionError}
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
  );

  const composer = (
    <div className="shrink-0 border-t border-line/60 bg-black/10 p-3">
      <div
        className={cn(
          "rounded-2xl border bg-elevated/60 transition focus-within:border-primary/45 focus-within:shadow-[0_0_0_4px_rgba(139,92,246,.08)]",
          draft
            ? "border-line"
            : "border-line/70 hover:border-slate-600",
        )}
      >
        <textarea
          ref={composerRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onInput={autoGrow}
          onKeyDown={handleKeyDown}
          rows={1}
          maxLength={4000}
          disabled={!hasKey}
          placeholder={
            hasKey
              ? "الان چه کاری انجام بدهم؟ (Enter ارسال — Shift+Enter خط جدید)"
              : "برای گفتگو ابتدا کلید Gemini را در تنظیمات اضافه کن"
          }
          aria-label="پیام به همراه"
          className="chat-scroll block max-h-40 min-h-[52px] w-full resize-none bg-transparent px-4 pt-3.5 text-xs leading-6 text-slate-100 placeholder:text-slate-600 focus:outline-none disabled:opacity-50"
        />
        <div className="flex items-center justify-between gap-2 px-2.5 pb-2.5">
          <div className="flex items-center gap-1.5 text-[9px] text-slate-600">
            {listening ? (
              <span className="flex animate-pulse-soft items-center gap-1.5 text-rose-300">
                <span className="size-1.5 rounded-full bg-rose-400" />
                در حال شنیدن…
              </span>
            ) : (
              <>
                <kbd className="rounded border border-line bg-white/[.03] px-1.5 py-0.5 text-[8.5px]">
                  Enter
                </kbd>
                ارسال
                <span className="text-slate-700">•</span>
                <kbd className="rounded border border-line bg-white/[.03] px-1.5 py-0.5 text-[8.5px]">
                  Shift+Enter
                </kbd>
                خط جدید
              </>
            )}
            {draft.length > 3500 && (
              <span className="text-amber-300">
                {draft.length.toLocaleString("fa-IR")}/۴۰۰۰
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {speechAvailable && (
              <Button
                variant="ghost"
                size="icon"
                className={cn(
                  "size-9",
                  listening &&
                    "border border-rose-400/30 bg-rose-400/10 text-rose-300 hover:bg-rose-400/20 hover:text-rose-200",
                )}
                aria-label="ورودی صوتی"
                onClick={toggleVoice}
                disabled={!hasKey}
              >
                <Mic size={15} className={listening ? "animate-pulse-soft" : ""} />
              </Button>
            )}
            <Button
              size="sm"
              onClick={sending ? stopGeneration : sendMessage}
              disabled={!hasKey || (!sending && !draft.trim())}
              className={cn(
                sending &&
                  "border border-rose-400/30 bg-rose-500/15 text-rose-200 shadow-none hover:bg-rose-500/25 hover:text-rose-100",
              )}
            >
              {sending ? (
                <>
                  <Square size={12} fill="currentColor" />
                  توقف
                </>
              ) : (
                <>
                  <Send size={13} />
                  ارسال
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );

  /* -------- docked variant: slim column for the floating shell -------- */
  if (isDock) {
    return (
      <div
        data-testid="companion-panel"
        className="relative flex h-full flex-col overflow-hidden"
      >
        <div className="flex h-11 shrink-0 items-center justify-between border-b border-white/[.05] px-2">
          <button
            type="button"
            onClick={() => setSidebarOpen((value) => !value)}
            className={cn(
              "flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[10px] font-medium transition",
              sidebarOpen
                ? "bg-primary/[.12] text-primary-soft"
                : "text-slate-400 hover:bg-white/[.05] hover:text-slate-200",
            )}
          >
            <MessagesSquare size={13} />
            گفتگوها
            {conversations.length > 0 && (
              <span className="rounded-full bg-white/[.06] px-1.5 py-px text-[9px] text-slate-400">
                {conversations.length.toLocaleString("fa-IR")}
              </span>
            )}
          </button>
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              aria-label="گفتگوی جدید"
              onClick={newConversation}
              className="grid size-8 place-items-center rounded-lg text-slate-400 transition hover:bg-white/[.05] hover:text-slate-200"
            >
              <Plus size={14} />
            </button>
            <button
              type="button"
              aria-label="تازه‌سازی گفتگو"
              onClick={refreshActive}
              className="grid size-8 place-items-center rounded-lg text-slate-400 transition hover:bg-white/[.05] hover:text-slate-200"
            >
              <RefreshCw size={13} />
            </button>
            {onExpand && (
              <button
                type="button"
                aria-label="بزرگ‌نمایی گفتگو"
                onClick={onExpand}
                className="grid size-8 place-items-center rounded-lg text-slate-400 transition hover:bg-white/[.05] hover:text-slate-200"
              >
                <Maximize2 size={13} />
              </button>
            )}
          </div>
        </div>
        {approvals > 0 && (
          <button
            type="button"
            data-testid="companion-approval-link"
            onClick={() => onNavigate("approval")}
            className="mx-3 mt-3 flex shrink-0 items-center justify-between rounded-xl border border-amber-400/20 bg-amber-400/[.06] px-3 py-2 text-[10px] font-medium text-amber-200 transition hover:bg-amber-400/[.12]"
          >
            <span className="flex items-center gap-1.5">
              <ShieldCheck size={12} />
              {approvals.toLocaleString("fa-IR")} عملیات در انتظار تأیید توست
            </span>
            <ChevronDown size={12} className="rotate-90" />
          </button>
        )}
        {thread}
        {composer}
        {sidebarOpen && (
          <div className="absolute inset-0 z-10 flex animate-fade-in flex-col bg-[#0a0e18]/97 backdrop-blur-xl">
            {conversationList}
          </div>
        )}
      </div>
    );
  }

  /* -------- page variant: full workspace -------- */
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
            <Button
              variant="secondary"
              size="icon"
              className="size-9"
              aria-label="تازه‌سازی گفتگو"
              onClick={refreshActive}
            >
              <RefreshCw size={14} />
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
              <p className="mt-1 text-[10px] leading-5 text-slate-500">
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

      <div className="grid gap-4 lg:grid-cols-[252px_1fr]">
        <aside
          className={cn(
            "flex flex-col overflow-hidden rounded-2xl border border-line bg-surface/60 lg:flex",
            sidebarOpen ? "flex" : "hidden",
          )}
          data-testid="companion-conversations"
        >
          <div className="flex h-10 shrink-0 items-center justify-between border-b border-line/60 px-3">
            <span className="text-[10px] font-semibold text-slate-500">
              گفتگوها
            </span>
            <button
              type="button"
              aria-label="بستن فهرست گفتگوها"
              className="grid size-7 place-items-center rounded-lg text-slate-600 lg:hidden"
              onClick={() => setSidebarOpen(false)}
            >
              <ChevronDown size={14} />
            </button>
          </div>
          <div className="chat-scroll max-h-[300px] flex-1 overflow-y-auto p-2 lg:max-h-[560px]">
            {loadingConversations ? (
              <p className="p-3 text-[11px] text-slate-600">در حال بارگذاری…</p>
            ) : conversations.length === 0 ? (
              <p className="p-3 text-[11px] leading-6 text-slate-600">
                هنوز گفتگویی ندارید. اولین پیام را بنویسید.
              </p>
            ) : (
              conversations.map((item) => (
                <div
                  key={item.id}
                  data-testid={`conversation-${item.id}-row`}
                  className={cn(
                    "group mb-1 flex items-center gap-1 rounded-xl px-2 py-2.5 text-right transition",
                    item.id === activeId
                      ? "border border-primary/15 bg-primary/[.08]"
                      : "border border-transparent hover:bg-white/[.03]",
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-right"
                    onClick={() => openConversation(item.id)}
                  >
                    <p className="truncate text-[11px] font-medium text-slate-300">
                      {item.title}
                    </p>
                    {item.last_message && (
                      <p className="mt-1 truncate text-[9px] text-slate-600">
                        {item.last_message}
                      </p>
                    )}
                  </button>
                  <button
                    type="button"
                    aria-label={`حذف گفتگو ${item.id}`}
                    className="grid size-6 shrink-0 place-items-center rounded-lg text-slate-600 opacity-0 transition hover:bg-rose-400/10 hover:text-rose-300 group-hover:opacity-100 focus-visible:opacity-100"
                    onClick={() => deleteConversation(item.id)}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>

        <section className="flex min-h-[560px] flex-col overflow-hidden rounded-2xl border border-line bg-surface/60">
          <div className="flex h-12 shrink-0 items-center justify-between border-b border-line/60 px-4">
            <div className="flex items-center gap-2.5">
              <span className="grid size-7 place-items-center rounded-xl bg-primary/[.12] text-primary-soft">
                <MessageCircle size={14} />
              </span>
              <span className="text-[11px] font-semibold text-slate-300">
                {activeId ? "گفتگوی فعال" : "گفتگوی جدید"}
              </span>
              <span className="hidden items-center gap-1.5 rounded-full border border-line bg-white/[.02] px-2 py-0.5 text-[9px] text-slate-500 sm:flex">
                <span className="size-1.5 rounded-full bg-emerald-400" />
                {system.reasoning_model || "Gemini"}
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
            <div className="flex items-center gap-1">
              {onExpand && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8"
                  aria-label="بزرگ‌نمایی گفتگو"
                  onClick={onExpand}
                >
                  <Maximize2 size={14} />
                </Button>
              )}
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
          </div>
          <div className="flex h-[520px] min-h-0 flex-1 xl:h-[600px]">
            {thread}
          </div>
          {composer}
        </section>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[10px] text-slate-600">
        <span className="flex items-center gap-1.5">
          <BrainCircuit size={12} className="text-primary-soft/70" />
          مدل فعال: {system.reasoning_model || "—"}
        </span>
        <span className="flex items-center gap-1.5">
          <Clock3 size={12} className="text-primary-soft/70" />
          منطقه زمانی: {system.timezone || "—"}
        </span>
        <span className="flex items-center gap-1.5">
          <ShieldCheck
            size={12}
            className={approvals > 0 ? "text-amber-300" : "text-emerald-300/70"}
          />
          {approvals > 0
            ? `${approvals} عملیات در انتظار تأیید`
            : "بدون عملیات در انتظار تأیید"}
        </span>
      </div>
    </div>
  );
}
