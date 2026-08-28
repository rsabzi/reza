import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Cpu,
  Loader2,
  MessageSquareText,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { Input, Select } from "./ui/input";

const OUTBOUND_STATUS_LABEL = {
  draft: "پیش‌نویس",
  needs_approval: "نیازمند تأیید",
  sending: "در حال ارسال",
  sent: "ارسال شد",
  failed: "ناموفق",
};

function safeStatus(value) {
  return OUTBOUND_STATUS_LABEL[value] || value;
}

export function AssistantConnections({
  status = {},
  notify = () => {},
  onStatusChanged = () => {},
}) {
  const [model, setModel] = useState(status.reasoning_model || "");
  const [savingModel, setSavingModel] = useState(false);
  const [telegramStatus, setTelegramStatus] = useState({});
  const [token, setToken] = useState("");
  const [tokenError, setTokenError] = useState("");
  const [testingToken, setTestingToken] = useState(false);
  const [savingToken, setSavingToken] = useState(false);
  const [contacts, setContacts] = useState([]);
  const [contactForm, setContactForm] = useState({
    owner_type: "general",
    owner_id: "",
    address: "",
    label: "",
  });
  const [outbound, setOutbound] = useState([]);

  useEffect(() => {
    setModel(status.reasoning_model || status.default_model || "");
  }, [status.reasoning_model, status.default_model]);

  useEffect(() => {
    api
      .getTelegramSetting()
      .then(setTelegramStatus)
      .catch(() => {});
    api
      .listContacts()
      .then(setContacts)
      .catch(() => {});
    api
      .listOutboundMessages()
      .then(setOutbound)
      .catch(() => {});
  }, [status.telegram_configured]);

  async function saveModel() {
    if (!model) return;
    setSavingModel(true);
    try {
      await api.setGeminiModel(model);
      await onStatusChanged();
      notify(`مدل گفتگو به ${model} تغییر کرد`, "success");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setSavingModel(false);
    }
  }

  async function saveToken(event) {
    event.preventDefault();
    if (token.trim().length < 20) {
      setTokenError("توکن ربات بیش از حد کوتاه است");
      return;
    }
    setSavingToken(true);
    setTokenError("");
    try {
      const result = await api.saveTelegramToken(token.trim());
      setToken("");
      setTelegramStatus(result);
      await onStatusChanged();
      notify("توکن تلگرام تأیید و رمز‌شده ذخیره شد", "success");
    } catch (reason) {
      setTokenError(reason.message);
    } finally {
      setSavingToken(false);
    }
  }

  async function testToken() {
    setTestingToken(true);
    setTokenError("");
    try {
      const result = await api.testTelegramToken();
      setTelegramStatus(result);
      await onStatusChanged();
      notify("اتصال واقعی به Bot API موفق بود", "success");
    } catch (reason) {
      setTokenError(reason.message);
      notify(reason.message, "error");
    } finally {
      setTestingToken(false);
    }
  }

  async function removeToken() {
    try {
      const result = await api.removeTelegramToken();
      setTelegramStatus(result);
      await onStatusChanged();
      notify("توکن تلگرام حذف شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    }
  }

  async function addContact(event) {
    event.preventDefault();
    try {
      const created = await api.createContact({
        owner_type: contactForm.owner_type,
        owner_id: contactForm.owner_id ? Number(contactForm.owner_id) : null,
        channel: "telegram",
        address: contactForm.address.trim(),
        label: contactForm.label.trim() || null,
        enabled: true,
      });
      setContacts((items) => [...items, created]);
      setContactForm({
        owner_type: "general",
        owner_id: "",
        address: "",
        label: "",
      });
      notify("مخاطب تلگرام ثبت شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    }
  }

  async function removeContact(id) {
    try {
      await api.deleteContact(id);
      setContacts((items) => items.filter((item) => item.id !== id));
      notify("مخاطب حذف شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    }
  }

  return (
    <div className="mt-5 grid gap-5 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <div>
            <h2 className="font-semibold text-white">مدل Gemini</h2>
            <p className="mt-1 text-[11px] text-slate-600">
              مدل گفتگو و برنامه‌ریزی؛ در صورت منقضی‌شدن، همراه خودش به مدل بعدی
              می‌رود.
            </p>
          </div>
          <Cpu size={18} className="text-primary-soft" />
        </CardHeader>
        <CardContent>
          <label
            className="text-xs font-medium text-slate-300"
            htmlFor="gemini-model"
          >
            مدل ترجیحی
          </label>
          <div className="mt-2 flex gap-2">
            <Select
              id="gemini-model"
              aria-label="مدل Gemini"
              value={model}
              onChange={(event) => setModel(event.target.value)}
            >
              {(status.supported_models || [status.default_model]).map(
                (name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ),
              )}
            </Select>
            <Button
              size="sm"
              onClick={saveModel}
              loading={savingModel}
              disabled={!model}
            >
              ذخیره مدل
            </Button>
          </div>
          <p
            className="mt-3 text-[10px] leading-5 text-slate-600"
            data-testid="telegram-status-note"
          >
            با تغییر مدل، گفتگوهای بعدی از همان مدل شروع می‌شوند؛ اگر مدل در
            دسترس نبود (404)، به‌طور خودکار به گزینه پایدار بعدی می‌رویم.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <h2 className="font-semibold text-white">
              اتصال تلگرام (ارسال واقعی)
            </h2>
            <p className="mt-1 text-[11px] text-slate-600">
              توکن Bot فقط رمز‌شده در Backend ذخیره می‌شود و هرگز به مرورگر یا
              Gemini نمی‌رود.
            </p>
          </div>
          <Send size={18} className="text-cyan-300" />
        </CardHeader>
        <CardContent>
          <div
            className={`rounded-xl border p-3 ${telegramStatus.configured ? "border-emerald-400/15 bg-emerald-400/[.04]" : "border-line/70 bg-background/45"}`}
          >
            <div className="flex items-center gap-2">
              {telegramStatus.configured ? (
                <CheckCircle2 size={15} className="text-emerald-300" />
              ) : (
                <ShieldCheck size={15} className="text-slate-600" />
              )}
              <span className="text-[11px] text-slate-300">
                {telegramStatus.configured
                  ? "ربات متصل است"
                  : "توکن تنظیم نشده"}
              </span>
              {telegramStatus.hint && (
                <code
                  dir="ltr"
                  className="mr-auto rounded bg-black/20 px-2 py-0.5 text-[10px] text-cyan-300"
                >
                  {telegramStatus.hint}
                </code>
              )}
            </div>
          </div>

          <form onSubmit={saveToken} className="mt-4">
            <Input
              type="password"
              dir="ltr"
              aria-label="توکن ربات تلگرام"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="123456789:AAA…"
              autoComplete="new-password"
            />
            {tokenError && (
              <p className="mt-2 text-[11px] text-rose-300" role="alert">
                {tokenError}
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                type="submit"
                size="sm"
                loading={savingToken}
                disabled={!token.trim()}
              >
                تست با getMe و ذخیره
              </Button>
              {telegramStatus.configured && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    loading={testingToken}
                    onClick={testToken}
                  >
                    <RefreshCw size={13} /> تست دوباره
                  </Button>
                  <Button variant="danger" size="sm" onClick={removeToken}>
                    <Trash2 size={13} /> حذف توکن
                  </Button>
                </>
              )}
            </div>
          </form>
          <p className="mt-3 text-[10px] leading-5 text-slate-600">
            بدون توکن و chat_id مخاطب، همراه هرگز ارسال را جعل نمی‌کند و دقیقاً
            می‌گوید چه چیزی کم است.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <h2 className="font-semibold text-white">
              مخاطبان تلگرام (chat_id)
            </h2>
            <p className="mt-1 text-[11px] text-slate-600">
              Endpoint عمومی برای سالن، پروژه یا عمومی؛ ارسال واقعی فقط از همین
              مسیر انجام می‌شود.
            </p>
          </div>
          <Users size={18} className="text-slate-500" />
        </CardHeader>
        <CardContent>
          <form onSubmit={addContact} className="grid grid-cols-2 gap-2">
            <Select
              aria-label="نوع مالک مخاطب"
              value={contactForm.owner_type}
              onChange={(event) =>
                setContactForm((form) => ({
                  ...form,
                  owner_type: event.target.value,
                }))
              }
            >
              <option value="general">عمومی</option>
              <option value="salon">سالن</option>
              <option value="project">پروژه</option>
            </Select>
            <Input
              type="number"
              aria-label="شناسه مالک"
              placeholder="owner id (اختیاری)"
              value={contactForm.owner_id}
              onChange={(event) =>
                setContactForm((form) => ({
                  ...form,
                  owner_id: event.target.value,
                }))
              }
            />
            <Input
              dir="ltr"
              aria-label="chat_id تلگرام"
              placeholder="chat_id عددی"
              value={contactForm.address}
              onChange={(event) =>
                setContactForm((form) => ({
                  ...form,
                  address: event.target.value,
                }))
              }
            />
            <Input
              aria-label="برچسب مخاطب"
              placeholder="برچسب (مثلاً کارفرما)"
              value={contactForm.label}
              onChange={(event) =>
                setContactForm((form) => ({
                  ...form,
                  label: event.target.value,
                }))
              }
            />
            <Button type="submit" size="sm" className="col-span-2">
              <Plus size={13} /> ثبت مخاطب
            </Button>
          </form>
          <div className="mt-3 space-y-1.5">
            {contacts.length === 0 && (
              <p
                data-testid="contacts-empty"
                className="text-[11px] text-slate-700"
              >
                هنوز مخاطبی ثبت نشده است.
              </p>
            )}
            {contacts.map((contact) => (
              <div
                key={contact.id}
                className="flex items-center gap-2 rounded-lg border border-line/60 px-3 py-2 text-[11px]"
              >
                <span className="rounded bg-cyan-400/10 px-1.5 py-0.5 text-[9px] text-cyan-300">
                  {contact.owner_type}
                </span>
                <span dir="ltr" className="font-mono text-slate-300">
                  {contact.address}
                </span>
                <span className="text-slate-700">{contact.label}</span>
                <button
                  type="button"
                  aria-label={`حذف مخاطب ${contact.id}`}
                  className="mr-auto text-slate-700 hover:text-rose-300"
                  onClick={() => removeContact(contact.id)}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <h2 className="font-semibold text-white">پیام‌های خروجی</h2>
            <p className="mt-1 text-[11px] text-slate-600">
              وضعیت واقعی و Receipt Provider برای هر پیام؛ هیچ پیامی بدون دریافت
              message_id «sent» نمی‌شود.
            </p>
          </div>
          <MessageSquareText size={18} className="text-slate-500" />
        </CardHeader>
        <CardContent>
          <div
            className="max-h-[260px] space-y-2 overflow-y-auto"
            data-testid="outbound-list"
          >
            {outbound.length === 0 && (
              <p className="text-[11px] text-slate-700">
                هنوز پیام خروجی‌ای ثبت نشده است.
              </p>
            )}
            {outbound.map((message) => (
              <div
                key={message.id}
                className="rounded-xl border border-line/60 p-3"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-md px-2 py-0.5 text-[9px] ${
                      message.status === "sent"
                        ? "bg-emerald-400/10 text-emerald-300"
                        : message.status === "failed"
                          ? "bg-rose-400/10 text-rose-300"
                          : "bg-amber-400/10 text-amber-200"
                    }`}
                    data-testid={`outbound-status-${message.id}`}
                  >
                    {safeStatus(message.status)}
                  </span>
                  {message.provider_message_id && (
                    <code dir="ltr" className="text-[9px] text-emerald-300">
                      msg_id: {message.provider_message_id}
                    </code>
                  )}
                  {message.owner_type && (
                    <span className="text-[9px] text-slate-700">
                      {message.owner_type}
                    </span>
                  )}
                </div>
                <p className="mt-1.5 line-clamp-2 text-[11px] leading-5 text-slate-400">
                  {message.content}
                </p>
                {message.error && (
                  <p className="mt-1 text-[10px] text-rose-300">
                    {message.error}
                  </p>
                )}
              </div>
            ))}
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="mt-3"
            onClick={() => api.listOutboundMessages().then(setOutbound)}
          >
            <Loader2 size={13} /> تازه‌سازی لیست
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
