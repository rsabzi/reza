import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  BriefcaseBusiness,
  CalendarDays,
  CircleDollarSign,
  FileSignature,
  Filter,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Target,
  Trash2,
  TrendingUp,
} from "lucide-react";
import { api } from "../lib/api";
import { faDate, faNumber } from "../lib/format";
import { Badge, statusLabels } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { ConfirmDialog, Dialog } from "./ui/dialog";
import { Field, Input, Select, Textarea } from "./ui/input";
import { DraftPreviewDialog } from "./DraftPreviewDialog";
import { EmptyState } from "./EmptyState";
import { PanelTitle } from "./PanelTitle";

const initialProject = {
  title: "",
  client_name: "",
  description: "",
  status: "lead",
  due_date: "",
  budget: "",
  next_action: "",
  external_url: "",
};
const transitions = {
  lead: ["active", "lost", "paused"],
  active: ["submitted", "completed", "lost", "paused"],
  submitted: ["active", "won", "lost", "paused"],
  paused: ["active", "lost"],
  won: [],
  lost: [],
  completed: [],
};

export function PersonalView({
  projects = [],
  reminders = [],
  onCreated = () => {},
  onChanged = () => {},
  onTaskCreated = () => {},
  notify = () => {},
}) {
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [viewing, setViewing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(null);
  const [draft, setDraft] = useState({
    open: false,
    title: "",
    text: "",
    loading: false,
    error: "",
  });
  const [error, setError] = useState("");

  const visible = useMemo(
    () =>
      projects.filter((project) => {
        const matches =
          !search ||
          `${project.title} ${project.client_name || ""} ${project.description || ""}`
            .toLowerCase()
            .includes(search.toLowerCase());
        return matches && (filter === "all" || project.status === filter);
      }),
    [projects, search, filter],
  );
  const active = projects.filter((project) =>
    ["active", "submitted"].includes(project.status),
  ).length;
  const totalBudget = projects
    .filter((project) => !["lost"].includes(project.status))
    .reduce((sum, project) => sum + Number(project.budget || 0), 0);

  async function save(values) {
    setBusy("save");
    setError("");
    try {
      const payload = {
        ...values,
        client_name: values.client_name || null,
        description: values.description || null,
        due_date: values.due_date || null,
        budget: values.budget || null,
        next_action: values.next_action || null,
        external_url: values.external_url || null,
      };
      if (editing) await api.updateProject(editing.id, payload);
      else {
        const created = await api.createProject(payload);
        onCreated(created);
      }
      await onChanged();
      setFormOpen(false);
      setEditing(null);
      notify(editing ? "پروژه به‌روزرسانی شد" : "پروژه جدید ثبت شد", "success");
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(null);
    }
  }

  async function changeStatus(project, status) {
    setBusy(`status-${project.id}`);
    try {
      const updated = await api.updateProject(project.id, { status });
      if (viewing?.id === project.id) setViewing(updated);
      await onChanged();
      notify(`وضعیت به «${statusLabels[status]}» تغییر کرد`, "success");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!deleting) return;
    setBusy("delete");
    try {
      await api.deleteProject(deleting.id);
      setDeleting(null);
      setViewing(null);
      await onChanged();
      notify("پروژه حذف شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(null);
    }
  }

  async function draftProposal(project) {
    setDraft({
      open: true,
      title: `پروپوزال ${project.title}`,
      text: "",
      loading: true,
      error: "",
    });
    try {
      const preview = await api.previewTool("draft_project_proposal", {
        project_id: project.id,
        approach: project.next_action || "تحویل مرحله‌ای و شفاف",
      });
      setDraft({
        open: true,
        title: `پروپوزال ${project.title}`,
        text: preview?.result?.proposal || "",
        loading: false,
        error: "",
      });
    } catch (reason) {
      setDraft({
        open: true,
        title: `پروپوزال ${project.title}`,
        text: "",
        loading: false,
        error: reason.message,
      });
    }
  }

  return (
    <div data-testid="personal-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="PERSONAL PIPELINE"
        title="پروژه‌ها و کار فریلنس"
        description="فرصت‌ها را از سرنخ تا تحویل مدیریت کن، ددلاین نزدیک را ببین و پروپوزال قابل بازبینی بساز."
        meta={
          <span className="text-[10px] text-slate-600">
            {faNumber(reminders.length)} موعد نزدیک
          </span>
        }
        action={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus size={16} />
            پروژه جدید
          </Button>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <ProjectStat
          icon={BriefcaseBusiness}
          label="کل پروژه‌ها"
          value={projects.length}
        />
        <ProjectStat
          icon={TrendingUp}
          label="در جریان"
          value={active}
          tone="text-cyan-300"
        />
        <ProjectStat
          icon={CalendarDays}
          label="موعد نزدیک"
          value={reminders.length}
          tone="text-amber-300"
        />
        <ProjectStat
          icon={CircleDollarSign}
          label="ارزش فرصت‌ها"
          value={faNumber(totalBudget)}
          suffix=" واحد"
          tone="text-emerald-300"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.45fr_.55fr]">
        <Card>
          <CardHeader className="flex-col items-stretch lg:flex-row lg:items-center">
            <div>
              <h2 className="font-semibold text-white">خط لوله پروژه‌ها</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                {faNumber(visible.length)} پروژه قابل مشاهده
              </p>
            </div>
            <div className="flex gap-2">
              <div className="relative flex-1 lg:w-56">
                <Search
                  size={14}
                  className="absolute right-3 top-3 text-slate-600"
                />
                <Input
                  aria-label="جستجوی پروژه"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="h-10 pr-9"
                  placeholder="عنوان یا کارفرما…"
                />
              </div>
              <div className="relative">
                <Filter
                  size={13}
                  className="pointer-events-none absolute right-3 top-3 text-slate-600"
                />
                <Select
                  aria-label="فیلتر وضعیت پروژه"
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                  className="h-10 w-36 pr-8"
                >
                  <option value="all">همه وضعیت‌ها</option>
                  <option value="lead">سرنخ</option>
                  <option value="active">فعال</option>
                  <option value="submitted">ارسال‌شده</option>
                  <option value="paused">متوقف</option>
                  <option value="won">برنده</option>
                  <option value="completed">تکمیل‌شده</option>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-2 sm:p-3">
            {projects.length === 0 ? (
              <EmptyState
                icon={BriefcaseBusiness}
                title="هنوز پروژه‌ای ثبت نشده"
                description="فرصت فریلنس یا پروژه شخصی بعدی را همین‌جا اضافه کن."
                action={
                  <Button size="sm" onClick={() => setFormOpen(true)}>
                    <Plus size={14} />
                    ثبت اولین پروژه
                  </Button>
                }
              />
            ) : visible.length === 0 ? (
              <EmptyState
                compact
                icon={Search}
                title="پروژه‌ای مطابق جستجو پیدا نشد"
              />
            ) : (
              <div className="space-y-1">
                {visible.map((project) => (
                  <ProjectRow
                    key={project.id}
                    project={project}
                    busy={busy}
                    onOpen={() => setViewing(project)}
                    onEdit={() => {
                      setEditing(project);
                      setFormOpen(true);
                    }}
                    onDelete={() => setDeleting(project)}
                    onStatus={(status) => changeStatus(project, status)}
                    onDraft={() => draftProposal(project)}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="self-start">
          <CardHeader>
            <div>
              <h2 className="font-semibold text-white">سه روز آینده</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                تمرکز روی موعدهای نزدیک
              </p>
            </div>
            <CalendarDays size={18} className="text-amber-300" />
          </CardHeader>
          <CardContent>
            {reminders.length === 0 ? (
              <EmptyState
                compact
                icon={CalendarDays}
                title="ددلاین نزدیکی نیست"
                description="فقط کارهای سه روز آینده اینجا نمایش داده می‌شوند."
              />
            ) : (
              <div className="space-y-3">
                {reminders.map((item) => (
                  <button
                    key={item.project.id}
                    onClick={() => setViewing(item.project)}
                    className="w-full rounded-xl border border-amber-400/10 bg-amber-400/[.035] p-4 text-right transition hover:bg-amber-400/[.06]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="grid size-9 place-items-center rounded-xl bg-amber-400/10 text-sm font-bold text-amber-300">
                        {faNumber(item.days_until_due)}
                      </span>
                      <Badge status={item.project.status} />
                    </div>
                    <h3 className="mt-3 text-xs font-semibold text-slate-200">
                      {item.project.title}
                    </h3>
                    <p className="mt-1 text-[10px] text-slate-600">
                      {item.days_until_due === 0
                        ? "موعد امروز"
                        : `${faNumber(item.days_until_due)} روز تا موعد`}{" "}
                      • {item.project.client_name || "شخصی"}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <ProjectFormDialog
        open={formOpen}
        project={editing}
        loading={busy === "save"}
        error={error}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
          setError("");
        }}
        onSave={save}
      />
      <ProjectDetailDialog
        project={viewing}
        open={Boolean(viewing)}
        busy={busy}
        onClose={() => setViewing(null)}
        onEdit={() => {
          setEditing(viewing);
          setViewing(null);
          setFormOpen(true);
        }}
        onDelete={() => setDeleting(viewing)}
        onStatus={(status) => changeStatus(viewing, status)}
        onDraft={() => draftProposal(viewing)}
      />
      <DraftPreviewDialog
        open={draft.open}
        title={draft.title}
        text={draft.text}
        loading={draft.loading}
        error={draft.error}
        onClose={() =>
          setDraft({
            open: false,
            title: "",
            text: "",
            loading: false,
            error: "",
          })
        }
        onCopy={() => notify("متن پروپوزال کپی شد", "success")}
      />

      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        loading={busy === "delete"}
        title="حذف پروژه؟"
        description={`پروژه «${deleting?.title || ""}» از فضای شخصی حذف خواهد شد.`}
      />
    </div>
  );
}

function ProjectStat({
  icon: Icon,
  label,
  value,
  suffix = "",
  tone = "text-primary-soft",
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-line/70 bg-surface/75 p-4">
      <span
        className={`grid size-10 place-items-center rounded-xl bg-white/[.035] ${tone}`}
      >
        <Icon size={17} />
      </span>
      <div className="min-w-0">
        <p className="truncate text-xl font-bold text-white">
          {typeof value === "number" ? faNumber(value) : value}
          {suffix}
        </p>
        <p className="text-[10px] text-slate-600">{label}</p>
      </div>
    </div>
  );
}

function ProjectRow({
  project,
  busy,
  onOpen,
  onEdit,
  onDelete,
  onStatus,
  onDraft,
}) {
  const options = transitions[project.status] || [];
  return (
    <div className="group flex items-center gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[.03]">
      <button
        onClick={onOpen}
        className="flex min-w-0 flex-1 items-center gap-3 text-right"
      >
        <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-line bg-elevated/50 text-slate-500">
          <BriefcaseBusiness size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-medium text-slate-200 group-hover:text-white">
              {project.title}
            </h3>
            <Badge status={project.status} />
          </div>
          <div className="mt-1.5 flex flex-wrap gap-3 text-[10px] text-slate-600">
            <span>{project.client_name || "پروژه شخصی"}</span>
            {project.due_date && (
              <span className="flex items-center gap-1">
                <CalendarDays size={10} />
                {faDate(project.due_date, { year: undefined })}
              </span>
            )}
            {project.budget && <span>{faNumber(project.budget)} واحد</span>}
          </div>
        </div>
      </button>
      <div className="hidden items-center gap-1 lg:flex lg:opacity-0 lg:transition lg:group-hover:opacity-100">
        {options.length > 0 && (
          <Select
            aria-label={`تغییر وضعیت ${project.title}`}
            value=""
            disabled={busy === `status-${project.id}`}
            onChange={(event) =>
              event.target.value && onStatus(event.target.value)
            }
            className="h-8 w-28 rounded-lg px-2 text-[10px]"
          >
            <option value="">تغییر وضعیت</option>
            {options.map((status) => (
              <option key={status} value={status}>
                {statusLabels[status]}
              </option>
            ))}
          </Select>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-primary-soft"
          onClick={onDraft}
          loading={busy === `draft-${project.id}`}
          aria-label="ساخت پروپوزال"
        >
          <FileSignature size={14} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onEdit}
          aria-label="ویرایش پروژه"
        >
          <Pencil size={14} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-slate-600 hover:text-rose-300"
          onClick={onDelete}
          aria-label="حذف پروژه"
        >
          <Trash2 size={14} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onOpen}
          aria-label="جزئیات پروژه"
        >
          <ArrowLeft size={14} />
        </Button>
      </div>
    </div>
  );
}

function ProjectFormDialog({ open, project, loading, error, onClose, onSave }) {
  const [values, setValues] = useState(initialProject);
  useEffect(() => {
    setValues(
      project
        ? { ...initialProject, ...project, budget: project.budget || "" }
        : initialProject,
    );
  }, [project, open]);
  function set(key, value) {
    setValues((current) => ({ ...current, [key]: value }));
  }
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={project ? "ویرایش پروژه" : "پروژه جدید"}
      description="اطلاعات فرصت، موعد و قدم بعدی را ثبت کن."
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
          <Field label="عنوان پروژه">
            <Input
              aria-label="عنوان پروژه"
              required
              value={values.title}
              onChange={(event) => set("title", event.target.value)}
            />
          </Field>
          <Field label="کارفرما">
            <Input
              aria-label="نام کارفرما"
              value={values.client_name || ""}
              onChange={(event) => set("client_name", event.target.value)}
            />
          </Field>
          <Field label="وضعیت">
            <Select
              value={values.status}
              onChange={(event) => set("status", event.target.value)}
              disabled={Boolean(project)}
            >
              <option value="lead">سرنخ</option>
              <option value="active">فعال</option>
              <option value="submitted">ارسال‌شده</option>
              <option value="paused">متوقف</option>
              <option value="won">برنده</option>
              <option value="lost">از دست‌رفته</option>
              <option value="completed">تکمیل‌شده</option>
            </Select>
          </Field>
          <Field label="موعد">
            <Input
              aria-label="موعد پروژه"
              type="date"
              value={values.due_date || ""}
              onChange={(event) => set("due_date", event.target.value)}
            />
          </Field>
          <Field label="بودجه">
            <Input
              type="number"
              min="0"
              step="0.01"
              value={values.budget || ""}
              onChange={(event) => set("budget", event.target.value)}
            />
          </Field>
          <Field label="لینک خارجی">
            <Input
              dir="ltr"
              value={values.external_url || ""}
              onChange={(event) => set("external_url", event.target.value)}
              placeholder="https://…"
            />
          </Field>
          <Field label="قدم بعدی" className="sm:col-span-2">
            <Input
              value={values.next_action || ""}
              onChange={(event) => set("next_action", event.target.value)}
            />
          </Field>
          <Field label="شرح پروژه" className="sm:col-span-2">
            <Textarea
              value={values.description || ""}
              onChange={(event) => set("description", event.target.value)}
            />
          </Field>
        </div>
        {error && <p className="text-xs text-rose-300">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
          <Button type="submit" loading={loading}>
            {project ? "ذخیره تغییرات" : "ثبت پروژه"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function ProjectDetailDialog({
  project,
  open,
  busy,
  onClose,
  onEdit,
  onDelete,
  onStatus,
  onDraft,
}) {
  if (!project) return null;
  const options = transitions[project.status] || [];
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={project.title}
      description={project.client_name || "پروژه شخصی"}
      size="lg"
    >
      <div className="flex flex-wrap gap-2">
        <Badge status={project.status} />
        {project.due_date && (
          <span className="rounded-full border border-line px-2.5 py-1 text-[10px] text-slate-500">
            موعد {faDate(project.due_date)}
          </span>
        )}
        {project.budget && (
          <span className="rounded-full border border-line px-2.5 py-1 text-[10px] text-emerald-300">
            {faNumber(project.budget)} واحد
          </span>
        )}
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-line bg-background/50 p-4">
          <p className="text-[10px] text-slate-600">قدم بعدی</p>
          <p className="mt-2 text-xs leading-6 text-slate-300">
            {project.next_action || "تعیین نشده"}
          </p>
        </div>
        <div className="rounded-xl border border-line bg-background/50 p-4">
          <p className="text-[10px] text-slate-600">شرح</p>
          <p className="mt-2 text-xs leading-6 text-slate-300">
            {project.description || "بدون توضیح"}
          </p>
        </div>
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        <Button onClick={onDraft} loading={busy === `draft-${project.id}`}>
          <Sparkles size={15} />
          ساخت پروپوزال
        </Button>
        <Button variant="secondary" onClick={onEdit}>
          <Pencil size={14} />
          ویرایش
        </Button>
        {options.length > 0 && (
          <Select
            value=""
            onChange={(event) =>
              event.target.value && onStatus(event.target.value)
            }
            className="h-11 w-40"
          >
            <option value="">تغییر وضعیت…</option>
            {options.map((status) => (
              <option key={status} value={status}>
                {statusLabels[status]}
              </option>
            ))}
          </Select>
        )}
        <Button variant="danger" onClick={onDelete}>
          <Trash2 size={14} />
          حذف
        </Button>
      </div>
    </Dialog>
  );
}
