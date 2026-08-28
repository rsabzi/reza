import { useEffect, useState } from "react";
import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Copy,
  Database,
  ExternalLink,
  Eye,
  EyeOff,
  KeyRound,
  RefreshCw,
  ServerCog,
  Settings2,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { ConfirmDialog } from "./ui/dialog";
import { Input, Select } from "./ui/input";
import { PanelTitle } from "./PanelTitle";
import { AssistantConnections } from "./AssistantConnections";
import { CustomSchemaPanel } from "./CustomSchemaPanel";

export function SettingsPanel({
  status = {},
  refreshInterval = 0,
  onRefreshInterval = () => {},
  onRefresh = () => {},
  onStatusChanged = () => {},
  notify = () => {},
}) {
  const [testing, setTesting] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const [removingKey, setRemovingKey] = useState(false);
  const [removeTarget, setRemoveTarget] = useState(null); // null | "all" | slot
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [keyError, setKeyError] = useState("");
  const [geminiKeys, setGeminiKeys] = useState({ keys: [], count: 0, max: 10 });

  async function loadKeys() {
    try {
      const result = await api.getGeminiKeys();
      setGeminiKeys(result);
    } catch {
      // Key management is auxiliary; status chips already surface failures.
    }
  }

  useEffect(() => {
    loadKeys();
  }, [status.gemini_key_hint, status.gemini_configured]);

  async function testConnection() {
    setTesting(true);
    try {
      await api.health();
      notify("ارتباط Dashboard و Agent Core سالم است", "success");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setTesting(false);
    }
  }

  async function saveGeminiKey(event) {
    event.preventDefault();
    if (apiKey.trim().length < 10) {
      setKeyError("کلید واردشده بیش از حد کوتاه است");
      return;
    }
    setSavingKey(true);
    setKeyError("");
    try {
      const result = await api.addGeminiKey(apiKey.trim());
      setApiKey("");
      setShowKey(false);
      setGeminiKeys(result);
      await onStatusChanged();
      notify(
        result.count > 1
          ? "کلید جدید تأیید و به چرخش کلیدها اضافه شد"
          : "کلید توسط Google تأیید و به‌صورت رمز‌شده ذخیره شد",
        "success",
      );
    } catch (reason) {
      setKeyError(reason.message);
    } finally {
      setSavingKey(false);
    }
  }

  async function removeGeminiKeySlot(slot) {
    setRemovingKey(true);
    try {
      const result = await api.removeGeminiKeySlot(slot);
      setGeminiKeys(result);
      await onStatusChanged();
      notify("کلید انتخاب‌شده از چرخش حذف شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setRemovingKey(false);
    }
  }

  async function testGemini() {
    setTesting(true);
    setKeyError("");
    try {
      await api.testGeminiKey();
      await onStatusChanged();
      notify("اتصال واقعی به Gemini موفق بود", "success");
    } catch (reason) {
      setKeyError(reason.message);
      notify(reason.message, "error");
    } finally {
      setTesting(false);
    }
  }

  async function removeGemini() {
    setRemovingKey(true);
    try {
      if (removeTarget === "all") {
        await api.removeGeminiKey();
        setGeminiKeys({ keys: [], count: 0, max: geminiKeys.max });
        notify("همه کلیدهای ذخیره‌شده از Dashboard حذف شد", "success");
      } else if (typeof removeTarget === "number") {
        const result = await api.removeGeminiKeySlot(removeTarget);
        setGeminiKeys(result);
        notify("کلید انتخاب‌شده از چرخش حذف شد", "success");
      }
      setRemoveTarget(null);
      await onStatusChanged();
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setRemovingKey(false);
    }
  }

  async function copyEnvironmentName() {
    await navigator.clipboard?.writeText("GEMINI_API_KEY");
    notify("نام متغیر کپی شد", "success");
  }

  return (
    <div data-testid="settings-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="SYSTEM & SECRETS"
        title="تنظیمات و وضعیت سیستم"
        description="کلید Gemini، آمادگی سرویس‌ها و رفتار همگام‌سازی را بدون ویرایش دستی Backend مدیریت کن."
        action={
          <Button variant="secondary" onClick={onRefresh}>
            <RefreshCw size={15} /> به‌روزرسانی وضعیت
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
        <StatusCard
          icon={ServerCog}
          title="Agent Core API"
          value={status.api_ready ? "آنلاین" : "در دسترس نیست"}
          helper={`نسخه ${status.version || "—"}`}
          ready={status.api_ready}
        />
        <StatusCard
          icon={Bot}
          title="مدل استدلال"
          value={status.gemini_configured ? "آماده" : "نیازمند کلید"}
          helper={status.reasoning_model || "gemini-3.7-flash"}
          ready={status.gemini_configured}
          warning
        />
        <StatusCard
          icon={BrainCircuit}
          title="Embedding"
          value={status.embedding_backend === "gemini" ? "Gemini" : "محلی"}
          helper={status.embedding_model || "gemini-embedding-001"}
          ready
        />
        <StatusCard
          icon={Clock3}
          title="زمان‌بند"
          value={status.scheduler_running ? "در حال اجرا" : "متوقف"}
          helper={status.timezone || "UTC"}
          ready={status.scheduler_running}
        />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
        <Card>
          <CardHeader>
            <div>
              <h2 className="font-semibold text-white">اتصال امن Gemini</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                کلید فقط به Backend ارسال می‌شود و هرگز دوباره به مرورگر
                برنمی‌گردد.
              </p>
            </div>
            <KeyRound size={18} className="text-primary-soft" />
          </CardHeader>
          <CardContent>
            <div
              className={`rounded-xl border p-4 ${status.gemini_configured ? "border-emerald-400/15 bg-emerald-400/[.04]" : "border-amber-400/15 bg-amber-400/[.04]"}`}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`grid size-9 shrink-0 place-items-center rounded-xl ${status.gemini_configured ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-300"}`}
                >
                  {status.gemini_configured ? (
                    <CheckCircle2 size={17} />
                  ) : (
                    <KeyRound size={17} />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-xs font-semibold text-slate-200">
                      {status.gemini_configured
                        ? geminiKeys.count > 1
                          ? `Gemini متصل است (${geminiKeys.count} کلید در چرخش)`
                          : "Gemini متصل است"
                        : "کلید Gemini تنظیم نشده"}
                    </p>
                    {status.gemini_key_hint && (
                      <code
                        dir="ltr"
                        className="rounded bg-black/20 px-2 py-0.5 text-[10px] text-emerald-300"
                      >
                        {status.gemini_key_hint}
                      </code>
                    )}
                  </div>
                  <p className="mt-1 text-[10px] leading-5 text-slate-500">
                    {status.gemini_configured
                      ? `منبع: ${status.gemini_key_source === "dashboard" ? "Secret رمز‌شده Dashboard" : "متغیر محیطی Backend"}`
                      : "کلید جدید Auth را از Google AI Studio بگیر و همین‌جا ثبت کن."}
                  </p>
                </div>
              </div>
            </div>

            {geminiKeys.keys?.length > 0 && (
              <div
                data-testid="gemini-key-list"
                className="mt-3 divide-y divide-line/60 rounded-xl border border-line/60"
              >
                {geminiKeys.keys.map((item) => (
                  <div
                    key={item.slot}
                    className="flex items-center gap-2 px-3 py-2.5"
                  >
                    <span
                      dir="ltr"
                      className="grid size-6 shrink-0 place-items-center rounded-lg bg-black/25 font-mono text-[10px] text-slate-400"
                    >
                      {item.slot}
                    </span>
                    <code
                      dir="ltr"
                      className="font-mono text-[11px] text-slate-300"
                    >
                      {item.hint || "••••"}
                    </code>
                    {item.active ? (
                      <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 text-[9px] font-medium text-emerald-300">
                        متصل / فعال
                      </span>
                    ) : item.cooling_seconds > 0 ? (
                      <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-2 py-0.5 text-[9px] font-medium text-amber-300">
                        استراحت موقت ({Math.ceil(item.cooling_seconds)}ث)
                      </span>
                    ) : (
                      <span className="rounded-full border border-line px-2 py-0.5 text-[9px] text-slate-500">
                        ذخیره‌شده
                      </span>
                    )}
                    <span className="flex-1" />
                    <button
                      type="button"
                      aria-label={`حذف کلید ${item.hint || item.slot}`}
                      disabled={removingKey}
                      onClick={() => setRemoveTarget(item.slot)}
                      className="text-slate-600 transition hover:text-rose-300 disabled:opacity-50"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
                <p className="px-3 py-2 text-[9px] leading-5 text-slate-600">
                  اگر کلیدی به محدودیت نرخ یا سهمیه برخورد کند، Backend بدون قطع
                  شدن تسک به کلید بعدی می‌رود و کلید سالم را فعال نگه می‌دارد.
                </p>
              </div>
            )}

            <form onSubmit={saveGeminiKey} className="mt-4">
              <label
                className="text-xs font-medium text-slate-300"
                htmlFor="gemini-key"
              >
                {geminiKeys.count > 0
                  ? `افزودن کلید بعدی به چرخش (${geminiKeys.count}/${geminiKeys.max})`
                  : "Gemini API Key"}
              </label>
              <div className="relative mt-2">
                <Input
                  id="gemini-key"
                  aria-label="کلید API جمنای"
                  dir="ltr"
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  autoComplete="new-password"
                  spellCheck="false"
                  className="h-12 pl-11 font-mono text-xs"
                  placeholder="کلید Auth یا API Key را اینجا وارد کنید"
                />
                <button
                  type="button"
                  onClick={() => setShowKey((value) => !value)}
                  className="absolute left-3 top-3.5 text-slate-600 transition hover:text-white"
                  aria-label={showKey ? "مخفی کردن کلید" : "نمایش کلید"}
                >
                  {showKey ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              {keyError && (
                <p
                  className="mt-2 text-[11px] leading-5 text-rose-300"
                  role="alert"
                >
                  {keyError}
                </p>
              )}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <a
                  href="https://aistudio.google.com/api-keys"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-[10px] text-cyan-300 transition hover:text-white"
                >
                  ساخت کلید جدید در Google AI Studio <ExternalLink size={12} />
                </a>
                <Button
                  type="submit"
                  size="sm"
                  loading={savingKey}
                  disabled={!apiKey.trim()}
                >
                  <ShieldCheck size={14} /> اعتبارسنجی و افزودن به چرخش
                </Button>
              </div>
            </form>

            {status.gemini_configured && (
              <div className="mt-4 flex flex-wrap gap-2 border-t border-line/60 pt-4">
                <Button
                  variant="outline"
                  size="sm"
                  loading={testing}
                  onClick={testGemini}
                >
                  <RefreshCw size={14} /> تست اتصال Gemini
                </Button>
                {status.gemini_key_source === "dashboard" && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => setRemoveTarget("all")}
                  >
                    <Trash2 size={14} /> حذف همه کلیدها
                  </Button>
                )}
              </div>
            )}

            <div className="mt-4 flex gap-3 rounded-xl border border-cyan-400/10 bg-cyan-400/[.035] p-3">
              <ShieldCheck
                className="mt-0.5 shrink-0 text-cyan-300"
                size={15}
              />
              <p className="text-[10px] leading-6 text-slate-500">
                کلید پس از تأیید Google با Fernet رمز می‌شود. کلید رمزگشایی محلی
                با مجوز فایل 0600 نگه‌داری می‌شود؛ مقدار خام در API status، لاگ
                یا پاسخ Frontend نمایش داده نمی‌شود.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <h2 className="font-semibold text-white">رفتار داشبورد</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                تنظیمات این بخش در مرورگر شما ذخیره می‌شود.
              </p>
            </div>
            <Settings2 size={18} className="text-slate-500" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-xl border border-line/70 bg-background/45 p-4">
              <label
                className="text-xs font-medium text-slate-300"
                htmlFor="refresh-interval"
              >
                همگام‌سازی خودکار
              </label>
              <p className="mb-3 mt-1 text-[10px] leading-5 text-slate-600">
                اطلاعات داشبورد بدون Reload کامل دوباره خوانده شود.
              </p>
              <Select
                id="refresh-interval"
                value={refreshInterval}
                onChange={(event) =>
                  onRefreshInterval(Number(event.target.value))
                }
              >
                <option value="0">خاموش</option>
                <option value="30">هر ۳۰ ثانیه</option>
                <option value="60">هر ۱ دقیقه</option>
                <option value="300">هر ۵ دقیقه</option>
              </Select>
            </div>
            <div className="rounded-xl border border-line/70 bg-background/45 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-medium text-slate-300">
                    پایگاه داده
                  </p>
                  <p className="mt-1 text-[10px] text-slate-600">
                    ذخیره‌سازی لوکال تک‌کاربره
                  </p>
                </div>
                <span className="flex items-center gap-2 rounded-lg bg-white/[.035] px-2.5 py-1.5 text-[10px] text-slate-400">
                  <Database size={13} /> {status.database || "SQLite"}
                </span>
              </div>
            </div>
            <Button
              className="w-full"
              variant="outline"
              loading={testing}
              onClick={testConnection}
            >
              <ShieldCheck size={15} /> آزمایش ارتباط واقعی Backend
            </Button>
            <Button
              className="w-full"
              variant="ghost"
              size="sm"
              onClick={copyEnvironmentName}
            >
              <Copy size={13} /> کپی نام متغیر سازگار
            </Button>
          </CardContent>
        </Card>
      </div>

      <AssistantConnections
        status={status}
        notify={notify}
        onStatusChanged={onStatusChanged}
      />

      <div className="mt-5" data-testid="settings-custom-schema">
        <CustomSchemaPanel notify={notify} />
      </div>

      <ConfirmDialog
        open={removeTarget !== null}
        onClose={() => setRemoveTarget(null)}
        onConfirm={removeGemini}
        loading={removingKey}
        title={
          removeTarget === "all" ? "حذف همه کلیدهای Gemini؟" : "حذف این کلید؟"
        }
        description={
          removeTarget === "all"
            ? "نسخه رمز‌شده همه کلیدهایی که از Dashboard ثبت کرده‌اید حذف می‌شود. در صورت وجود متغیر محیطی، Backend به‌طور خودکار از آن استفاده خواهد کرد."
            : "این کلید از چرخش حذف می‌شود؛ بقیه کلیدها فعال می‌مانند."
        }
        confirmLabel="حذف کلید"
      />
    </div>
  );
}

function StatusCard({
  icon: Icon,
  title,
  value,
  helper,
  ready,
  warning = false,
}) {
  return (
    <Card>
      <CardContent>
        <div className="flex items-start justify-between gap-3">
          <span
            className={`grid size-10 place-items-center rounded-xl ${ready ? "bg-emerald-400/[.08] text-emerald-300" : warning ? "bg-amber-400/[.08] text-amber-300" : "bg-rose-400/[.08] text-rose-300"}`}
          >
            <Icon size={18} />
          </span>
          <span
            className={`mt-1 size-2 rounded-full ${ready ? "bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.7)]" : warning ? "bg-amber-400" : "bg-rose-400"}`}
          />
        </div>
        <p className="mt-4 text-sm font-semibold text-white">{value}</p>
        <p className="mt-1 text-[10px] text-slate-500">{title}</p>
        <p
          dir="ltr"
          className="mt-2 truncate text-left text-[9px] text-slate-700"
        >
          {helper}
        </p>
      </CardContent>
    </Card>
  );
}
