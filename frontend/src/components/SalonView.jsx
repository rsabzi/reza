import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Building2,
  CalendarClock,
  FileUp,
  Filter,
  History,
  MapPin,
  MessageCirclePlus,
  MessageSquareText,
  Pencil,
  Phone,
  Plus,
  Search,
  Scissors,
  Target,
  Trash2,
  UserRoundCheck,
} from "lucide-react";
import { api } from "../lib/api";
import { faDate, faNumber, relativeDate } from "../lib/format";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { ConfirmDialog, Dialog } from "./ui/dialog";
import { Field, Input, Select, Textarea } from "./ui/input";
import { EmptyState } from "./EmptyState";
import { PanelTitle } from "./PanelTitle";

const emptySalon = {
  name: "",
  phone: "",
  city: "",
  address: "",
  status: "lead",
  notes: "",
  tags: "",
};

export function SalonView({
  salons = [],
  dailyPlan = [],
  onCreated = () => {},
  onChanged = () => {},
  onTaskCreated = () => {},
  notify = () => {},
}) {
  const [formOpen, setFormOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [interactions, setInteractions] = useState([]);
  const [interactionOpen, setInteractionOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const visible = useMemo(
    () =>
      salons.filter((salon) => {
        const matches =
          !search ||
          `${salon.name} ${salon.phone} ${salon.city || ""}`
            .toLowerCase()
            .includes(search.toLowerCase());
        return matches && (filter === "all" || salon.status === filter);
      }),
    [salons, search, filter],
  );

  async function openSalon(salon) {
    setSelected(salon);
    setInteractions([]);
    setError("");
    try {
      setInteractions(await api.listSalonInteractions(salon.id));
    } catch (reason) {
      setError(reason.message);
    }
  }

  async function saveSalon(values) {
    setBusy(true);
    setError("");
    try {
      const payload = {
        ...values,
        tags: values.tags
          ? values.tags
              .split("،")
              .map((item) => item.trim())
              .filter(Boolean)
          : [],
      };
      if (editing) await api.updateSalon(editing.id, payload);
      else {
        const created = await api.createSalon(payload);
        onCreated(created);
      }
      await onChanged();
      setFormOpen(false);
      setEditing(null);
      notify(
        editing ? "اطلاعات سالن به‌روزرسانی شد" : "سالن جدید ثبت شد",
        "success",
      );
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeSalon() {
    if (!deleting) return;
    setBusy(true);
    try {
      await api.deleteSalon(deleting.id);
      if (selected?.id === deleting.id) setSelected(null);
      setDeleting(null);
      await onChanged();
      notify("سالن و تاریخچه تعامل‌های آن حذف شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function logInteraction(payload) {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await api.logSalonInteraction(selected.id, payload);
      const [nextInteractions, freshSalon] = await Promise.all([
        api.listSalonInteractions(selected.id),
        api.getSalon(selected.id),
      ]);
      setInteractions(nextInteractions);
      setSelected(freshSalon);
      setInteractionOpen(false);
      await onChanged();
      notify("تعامل در تاریخچه و حافظه بلندمدت ثبت شد", "success");
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  async function generateOutreach(salon) {
    setBusy(true);
    try {
      const task = await api.createTask({
        title: `متن معرفی برای ${salon.name}`,
        description: "ساخت پیش‌نویس ارتباطی از ماژول سالن",
        module_name: "salon",
      });
      const step = await api.invokeTool("generate_outreach_script", {
        task_id: task.id,
        title: `بازبینی متن معرفی ${salon.name}`,
        arguments: { salon_id: salon.id, offer: "افزایش رزرو و بازگشت مشتری" },
      });
      await onTaskCreated(task, step);
      notify(
        step.status === "needs_approval"
          ? "متن معرفی به صف تأیید اضافه شد"
          : "متن معرفی تولید شد",
        "success",
      );
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(false);
    }
  }

  const leads = salons.filter((salon) =>
    ["lead", "contacted", "interested"].includes(salon.status),
  ).length;
  const customers = salons.filter(
    (salon) => salon.status === "customer",
  ).length;

  return (
    <div data-testid="salon-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="SALON GROWTH CRM"
        title="رشد و ارتباط با سالن‌ها"
        description="از کشف سرنخ تا ثبت تعامل و پیگیری هوشمند، تمام چرخه ارتباط را در یک فضای متمرکز مدیریت کن."
        meta={
          <span className="text-[10px] text-slate-600">
            {faNumber(dailyPlan.length)} پیگیری مجاز امروز
          </span>
        }
        action={
          <>
            <Button variant="secondary" onClick={() => setImportOpen(true)}>
              <FileUp size={16} />
              ورود گروهی
            </Button>
            <Button
              onClick={() => {
                setEditing(null);
                setFormOpen(true);
              }}
            >
              <Plus size={16} />
              سالن جدید
            </Button>
          </>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <SalonStat icon={Building2} label="کل سالن‌ها" value={salons.length} />
        <SalonStat
          icon={Target}
          label="سرنخ فعال"
          value={leads}
          tone="text-cyan-300"
        />
        <SalonStat
          icon={CalendarClock}
          label="برنامه امروز"
          value={dailyPlan.length}
          tone="text-amber-300"
        />
        <SalonStat
          icon={UserRoundCheck}
          label="مشتری"
          value={customers}
          tone="text-emerald-300"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.45fr_.55fr]">
        <Card>
          <CardHeader className="flex-col items-stretch lg:flex-row lg:items-center">
            <div>
              <h2 className="font-semibold text-white">پایگاه سالن‌ها</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                {faNumber(visible.length)} رکورد قابل مشاهده
              </p>
            </div>
            <div className="flex gap-2">
              <div className="relative flex-1 lg:w-56">
                <Search
                  size={14}
                  className="absolute right-3 top-3 text-slate-600"
                />
                <Input
                  aria-label="جستجوی سالن"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="h-10 pr-9"
                  placeholder="نام، تلفن یا شهر…"
                />
              </div>
              <div className="relative">
                <Filter
                  size={13}
                  className="pointer-events-none absolute right-3 top-3 text-slate-600"
                />
                <Select
                  aria-label="فیلتر وضعیت سالن"
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                  className="h-10 w-36 pr-8"
                >
                  <option value="all">همه وضعیت‌ها</option>
                  <option value="lead">سرنخ</option>
                  <option value="contacted">تماس گرفته</option>
                  <option value="interested">علاقه‌مند</option>
                  <option value="customer">مشتری</option>
                  <option value="inactive">غیرفعال</option>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-2 sm:p-3">
            {salons.length === 0 ? (
              <EmptyState
                icon={Scissors}
                title="هنوز سالنی ثبت نشده"
                description="یک سالن جدید اضافه یا فهرست موجود را به‌صورت گروهی وارد کن."
                action={
                  <Button size="sm" onClick={() => setFormOpen(true)}>
                    <Plus size={14} />
                    ثبت اولین سالن
                  </Button>
                }
              />
            ) : visible.length === 0 ? (
              <EmptyState
                compact
                icon={Search}
                title="سالنی مطابق جستجو پیدا نشد"
              />
            ) : (
              <div className="space-y-1">
                {visible.map((salon) => (
                  <SalonRow
                    key={salon.id}
                    salon={salon}
                    onOpen={() => openSalon(salon)}
                    onEdit={() => {
                      setEditing(salon);
                      setFormOpen(true);
                    }}
                    onDelete={() => setDeleting(salon)}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="self-start">
          <CardHeader>
            <div>
              <h2 className="font-semibold text-white">برنامه تماس امروز</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                فیلترشده با cadence پلی‌بوک
              </p>
            </div>
            <Target size={18} className="text-mint" />
          </CardHeader>
          <CardContent>
            {dailyPlan.length === 0 ? (
              <EmptyState
                compact
                icon={Target}
                title="پیگیری‌ای برای امروز نیست"
                description="فاصله تماس پلی‌بوک برای همه سالن‌ها رعایت شده است."
              />
            ) : (
              <div className="space-y-3">
                {dailyPlan.map((item, index) => (
                  <article
                    key={item.salon.id}
                    className="rounded-xl border border-emerald-400/10 bg-emerald-400/[.035] p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="grid size-8 place-items-center rounded-lg bg-emerald-400/10 text-xs font-bold text-emerald-300">
                        {faNumber(index + 1)}
                      </span>
                      <Badge status={item.salon.status} />
                    </div>
                    <h3 className="mt-3 text-sm font-semibold text-slate-200">
                      {item.salon.name}
                    </h3>
                    <p className="mt-1 text-[10px] leading-5 text-slate-600">
                      {item.days_since_contact == null
                        ? "بدون تماس قبلی"
                        : `${faNumber(item.days_since_contact)} روز از آخرین تماس گذشته`}
                    </p>
                    <Button
                      className="mt-3 w-full"
                      variant="success"
                      size="sm"
                      loading={busy}
                      onClick={() => generateOutreach(item.salon)}
                    >
                      <MessageSquareText size={14} />
                      ساخت متن پیگیری
                    </Button>
                  </article>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <SalonFormDialog
        open={formOpen}
        salon={editing}
        loading={busy}
        error={error}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
          setError("");
        }}
        onSave={saveSalon}
      />
      <SalonDetailDialog
        salon={selected}
        interactions={interactions}
        open={Boolean(selected)}
        error={error}
        busy={busy}
        onClose={() => setSelected(null)}
        onEdit={() => {
          setEditing(selected);
          setSelected(null);
          setFormOpen(true);
        }}
        onLog={() => setInteractionOpen(true)}
        onOutreach={() => selected && generateOutreach(selected)}
      />
      <InteractionDialog
        open={interactionOpen}
        loading={busy}
        error={error}
        onClose={() => {
          setInteractionOpen(false);
          setError("");
        }}
        onSave={logInteraction}
      />
      <ImportDialog
        open={importOpen}
        loading={busy}
        onClose={() => setImportOpen(false)}
        onImported={async () => {
          await onChanged();
          notify("ورود گروهی پردازش شد", "success");
        }}
        notify={notify}
      />
      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={removeSalon}
        loading={busy}
        title="حذف سالن؟"
        description={`سالن «${deleting?.name || ""}» و تمام تعامل‌های وابسته به آن حذف می‌شوند.`}
      />
    </div>
  );
}

function SalonStat({ icon: Icon, label, value, tone = "text-primary-soft" }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-line/70 bg-surface/75 p-4">
      <span
        className={`grid size-10 place-items-center rounded-xl bg-white/[.035] ${tone}`}
      >
        <Icon size={17} />
      </span>
      <div>
        <p className="text-xl font-bold text-white">{faNumber(value)}</p>
        <p className="text-[10px] text-slate-600">{label}</p>
      </div>
    </div>
  );
}

function SalonRow({ salon, onOpen, onEdit, onDelete }) {
  return (
    <div className="group flex items-center gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[.03]">
      <button
        onClick={onOpen}
        className="flex min-w-0 flex-1 items-center gap-3 text-right"
      >
        <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-line bg-elevated/50 text-slate-500">
          <Scissors size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-medium text-slate-200 group-hover:text-white">
              {salon.name}
            </h3>
            <Badge status={salon.status} />
          </div>
          <div className="mt-1.5 flex flex-wrap gap-3 text-[10px] text-slate-600">
            <span dir="ltr" className="flex items-center gap-1">
              <Phone size={10} />
              {salon.phone}
            </span>
            {salon.city && (
              <span className="flex items-center gap-1">
                <MapPin size={10} />
                {salon.city}
              </span>
            )}
            <span>{relativeDate(salon.last_contact_at)}</span>
          </div>
        </div>
      </button>
      <div className="flex opacity-100 transition lg:opacity-0 lg:group-hover:opacity-100">
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onEdit}
          aria-label="ویرایش سالن"
        >
          <Pencil size={14} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-slate-600 hover:text-rose-300"
          onClick={onDelete}
          aria-label="حذف سالن"
        >
          <Trash2 size={14} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onOpen}
          aria-label="جزئیات سالن"
        >
          <ArrowLeft size={14} />
        </Button>
      </div>
    </div>
  );
}

function SalonFormDialog({ open, salon, loading, error, onClose, onSave }) {
  const [values, setValues] = useState(emptySalon);
  useEffect(() => {
    setValues(
      salon ? { ...salon, tags: (salon.tags || []).join("، ") } : emptySalon,
    );
  }, [salon, open]);
  function set(key, value) {
    setValues((current) => ({ ...current, [key]: value }));
  }
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={salon ? "ویرایش سالن" : "ثبت سالن جدید"}
      description="اطلاعات پایه و وضعیت فعلی ارتباط را ثبت کن."
      size="lg"
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSave(values);
        }}
        className="space-y-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="نام سالن">
            <Input
              aria-label="نام سالن"
              required
              value={values.name}
              onChange={(event) => set("name", event.target.value)}
            />
          </Field>
          <Field label="شماره تماس">
            <Input
              aria-label="تلفن سالن"
              dir="ltr"
              required
              value={values.phone}
              onChange={(event) => set("phone", event.target.value)}
            />
          </Field>
          <Field label="شهر">
            <Input
              value={values.city || ""}
              onChange={(event) => set("city", event.target.value)}
            />
          </Field>
          <Field label="وضعیت">
            <Select
              value={values.status}
              onChange={(event) => set("status", event.target.value)}
            >
              <option value="lead">سرنخ</option>
              <option value="contacted">تماس گرفته</option>
              <option value="interested">علاقه‌مند</option>
              <option value="customer">مشتری</option>
              <option value="inactive">غیرفعال</option>
              <option value="do_not_contact">عدم تماس</option>
            </Select>
          </Field>
          <Field label="نشانی" className="sm:col-span-2">
            <Input
              value={values.address || ""}
              onChange={(event) => set("address", event.target.value)}
            />
          </Field>
          <Field
            label="برچسب‌ها"
            hint="با «،» جدا کن"
            className="sm:col-span-2"
          >
            <Input
              value={values.tags || ""}
              onChange={(event) => set("tags", event.target.value)}
              placeholder="VIP، رنگ مو، مرکز تهران"
            />
          </Field>
          <Field label="یادداشت" className="sm:col-span-2">
            <Textarea
              value={values.notes || ""}
              onChange={(event) => set("notes", event.target.value)}
            />
          </Field>
        </div>
        {error && <p className="text-xs text-rose-300">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
          <Button type="submit" loading={loading}>
            {salon ? "ذخیره تغییرات" : "ثبت سالن"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function SalonDetailDialog({
  salon,
  interactions,
  open,
  error,
  busy,
  onClose,
  onEdit,
  onLog,
  onOutreach,
}) {
  if (!salon) return null;
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={salon.name}
      description={`${salon.city || "شهر ثبت نشده"} • ${salon.phone}`}
      size="lg"
    >
      <div className="mb-5 flex flex-wrap gap-2">
        <Badge status={salon.status} />
        {(salon.tags || []).map((tag) => (
          <span
            key={tag}
            className="rounded-full border border-line px-2.5 py-1 text-[10px] text-slate-500"
          >
            {tag}
          </span>
        ))}
      </div>
      <div className="mb-5 grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-line bg-background/50 p-4">
          <p className="text-[10px] text-slate-600">آخرین تماس</p>
          <p className="mt-2 text-xs font-medium text-slate-300">
            {salon.last_contact_at ? faDate(salon.last_contact_at) : "ثبت نشده"}
          </p>
        </div>
        <div className="rounded-xl border border-line bg-background/50 p-4">
          <p className="text-[10px] text-slate-600">تعداد تعامل</p>
          <p className="mt-2 text-xs font-medium text-slate-300">
            {faNumber(interactions.length)} مورد
          </p>
        </div>
      </div>
      <div className="mb-5 flex flex-wrap gap-2">
        <Button size="sm" onClick={onLog}>
          <MessageCirclePlus size={14} />
          ثبت تعامل
        </Button>
        <Button size="sm" variant="outline" loading={busy} onClick={onOutreach}>
          <MessageSquareText size={14} />
          ساخت متن معرفی
        </Button>
        <Button size="sm" variant="ghost" onClick={onEdit}>
          <Pencil size={14} />
          ویرایش
        </Button>
      </div>
      <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-300">
        <History size={14} />
        تاریخچه تعامل‌ها
      </h3>
      {error && <p className="mb-3 text-xs text-rose-300">{error}</p>}
      {interactions.length === 0 ? (
        <EmptyState compact icon={History} title="هنوز تعاملی ثبت نشده" />
      ) : (
        <div className="space-y-2">
          {interactions.map((item) => (
            <article
              key={item.id}
              className="rounded-xl border border-line/70 bg-white/[.018] p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-[10px] font-semibold text-cyan-300">
                  {item.channel}
                </span>
                <span className="text-[9px] text-slate-700">
                  {faDate(item.occurred_at)}
                </span>
              </div>
              <p className="mt-2 text-xs leading-6 text-slate-400">
                {item.content}
              </p>
              {item.outcome && (
                <p className="mt-2 text-[10px] text-emerald-300">
                  نتیجه: {item.outcome}
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </Dialog>
  );
}

function InteractionDialog({ open, loading, error, onClose, onSave }) {
  const [channel, setChannel] = useState("whatsapp");
  const [direction, setDirection] = useState("outbound");
  const [content, setContent] = useState("");
  const [outcome, setOutcome] = useState("");
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="ثبت تعامل جدید"
      description="این رویداد هم‌زمان در تاریخچه سالن و حافظه بلندمدت ذخیره می‌شود."
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSave({ channel, direction, content, outcome: outcome || null });
        }}
        className="space-y-4"
      >
        <div className="grid grid-cols-2 gap-4">
          <Field label="کانال">
            <Select
              value={channel}
              onChange={(event) => setChannel(event.target.value)}
            >
              <option value="whatsapp">واتساپ</option>
              <option value="phone">تماس تلفنی</option>
              <option value="instagram">اینستاگرام</option>
              <option value="sms">پیامک</option>
              <option value="email">ایمیل</option>
              <option value="in_person">حضوری</option>
            </Select>
          </Field>
          <Field label="جهت">
            <Select
              value={direction}
              onChange={(event) => setDirection(event.target.value)}
            >
              <option value="outbound">خروجی</option>
              <option value="inbound">ورودی</option>
            </Select>
          </Field>
        </div>
        <Field label="شرح تعامل">
          <Textarea
            required
            value={content}
            onChange={(event) => setContent(event.target.value)}
          />
        </Field>
        <Field label="نتیجه" hint="اختیاری">
          <Input
            value={outcome}
            onChange={(event) => setOutcome(event.target.value)}
            placeholder="مثلاً درخواست نمونه‌کار"
          />
        </Field>
        {error && <p className="text-xs text-rose-300">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
          <Button type="submit" loading={loading}>
            ثبت در حافظه
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function ImportDialog({ open, loading, onClose, onImported, notify }) {
  const [text, setText] = useState(
    "نام سالن,شماره تماس,شهر\nسالن نمونه,+98 912 000 0000,تهران",
  );
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      let rows;
      if (text.trim().startsWith("[")) rows = JSON.parse(text);
      else {
        const lines = text.trim().split("\n").filter(Boolean);
        const hasHeader = /نام|name|شماره|phone/i.test(lines[0] || "");
        rows = lines.slice(hasHeader ? 1 : 0).map((line) => {
          const [name, phone, city] = line
            .split(",")
            .map((item) => item.trim());
          return { name, phone, city: city || null };
        });
      }
      const response = await api.importSalons(rows);
      setResult(response);
      await onImported();
    } catch (reason) {
      notify(reason.message || "فرمت ورودی معتبر نیست", "error");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="ورود گروهی سالن‌ها"
      description="فایل CSV را کپی کن یا یک آرایه JSON قرار بده. ردیف‌های نامعتبر به‌صورت شفاف گزارش می‌شوند."
      size="lg"
    >
      <form onSubmit={submit}>
        <Field label="داده ورودی" hint="CSV یا JSON">
          <Textarea
            dir="ltr"
            className="min-h-56 font-mono text-xs"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </Field>
        {result && (
          <div className="mt-4 rounded-xl border border-line bg-background/60 p-4">
            <div className="flex gap-4 text-xs">
              <span className="text-emerald-300">
                {faNumber(result.created_count)} ایجاد شد
              </span>
              <span
                className={
                  result.error_count ? "text-rose-300" : "text-slate-500"
                }
              >
                {faNumber(result.error_count)} خطا
              </span>
            </div>
            {result.errors?.length > 0 && (
              <ul className="mt-3 space-y-1 text-[10px] text-rose-300">
                {result.errors.map((item) => (
                  <li key={item.index}>
                    ردیف {faNumber(item.index + 1)}:{" "}
                    {item.errors.map((error) => error.msg).join("، ")}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            بستن
          </Button>
          <Button type="submit" loading={busy || loading}>
            <FileUp size={14} />
            پردازش ورودی
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
