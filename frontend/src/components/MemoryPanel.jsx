import { useMemo, useState } from "react";
import {
  BookOpen,
  BrainCircuit,
  Database,
  Eye,
  Filter,
  Layers3,
  Plus,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import { api } from "../lib/api";
import { faDate, faNumber, sourceLabels, truncate } from "../lib/format";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import { ConfirmDialog, Dialog } from "./ui/dialog";
import { Field, Input, Select, Textarea } from "./ui/input";
import { EmptyState } from "./EmptyState";
import { PanelTitle } from "./PanelTitle";

export function MemoryPanel({
  memories = [],
  playbooks = [],
  onPlaybookAdded = () => {},
  onChanged = () => {},
  notify = () => {},
}) {
  const [tab, setTab] = useState("memory");
  const [createOpen, setCreateOpen] = useState(false);
  const [viewing, setViewing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const visibleMemories = useMemo(() => {
    const base = searchResults || memories;
    return source === "all"
      ? base
      : base.filter((entry) => entry.source === source);
  }, [memories, searchResults, source]);

  async function search(event) {
    event?.preventDefault();
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    setError("");
    try {
      setSearchResults(await api.searchMemory(query.trim()));
    } catch (reason) {
      setError(reason.message);
    } finally {
      setSearching(false);
    }
  }

  async function remove() {
    if (!deleting) return;
    setSaving(true);
    try {
      if (deleting.type === "playbook")
        await api.deletePlaybook(deleting.item.id);
      else await api.deleteMemory(deleting.item.id);
      setDeleting(null);
      setSearchResults(null);
      await onChanged();
      notify("مورد انتخاب‌شده از حافظه حذف شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div data-testid="memory-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="KNOWLEDGE VAULT"
        title="حافظه و دانش ماندگار"
        description="راهبردها، تعامل‌ها و خروجی‌های مهم را پیدا، مدیریت و برای تصمیم‌های بعدی قابل استفاده کن."
        meta={
          <span className="text-[10px] text-slate-600">
            {faNumber(memories.length)} بردار ذخیره‌شده
          </span>
        }
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={16} />
            پلی‌بوک جدید
          </Button>
        }
      />

      <div className="mb-5 grid grid-cols-3 gap-3">
        <MemoryStat
          icon={BrainCircuit}
          label="کل حافظه"
          value={memories.length}
          tone="text-mint"
        />
        <MemoryStat
          icon={BookOpen}
          label="پلی‌بوک"
          value={playbooks.length}
          tone="text-primary-soft"
        />
        <MemoryStat
          icon={Layers3}
          label="نتایج تسک"
          value={
            memories.filter((item) => item.source === "task_result").length
          }
          tone="text-cyan-300"
        />
      </div>

      <div className="mb-5 flex w-fit rounded-xl border border-line bg-surface p-1">
        <Tab
          active={tab === "memory"}
          onClick={() => setTab("memory")}
          icon={Database}
        >
          حافظه برداری
        </Tab>
        <Tab
          active={tab === "playbooks"}
          onClick={() => setTab("playbooks")}
          icon={BookOpen}
        >
          پلی‌بوک‌ها
        </Tab>
      </div>

      {tab === "memory" ? (
        <Card>
          <CardHeader className="flex-col items-stretch lg:flex-row lg:items-center">
            <form onSubmit={search} className="flex flex-1 gap-2">
              <div className="relative flex-1">
                <Search
                  className="absolute right-3 top-3 text-slate-600"
                  size={15}
                />
                <Input
                  aria-label="جستجوی معنایی حافظه"
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    if (!event.target.value) setSearchResults(null);
                  }}
                  className="h-10 pr-9"
                  placeholder="جستجوی معنایی؛ مثلاً پیگیری سالن علاقه‌مند…"
                />
              </div>
              <Button type="submit" size="sm" loading={searching}>
                جستجو
              </Button>
            </form>
            <div className="relative">
              <Filter
                className="pointer-events-none absolute right-3 top-3 text-slate-600"
                size={14}
              />
              <Select
                aria-label="فیلتر منبع حافظه"
                value={source}
                onChange={(event) => setSource(event.target.value)}
                className="h-10 w-full pr-8 lg:w-44"
              >
                <option value="all">همه منابع</option>
                <option value="playbook">پلی‌بوک</option>
                <option value="task_result">نتیجه تسک</option>
                <option value="salon_interaction">تعامل سالن</option>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            {error && (
              <p className="mb-4 rounded-xl border border-rose-400/15 bg-rose-400/[.06] p-3 text-xs text-rose-300">
                {error}
              </p>
            )}
            {memories.length === 0 ? (
              <EmptyState
                icon={Database}
                title="حافظه هنوز خالی است"
                description="نتیجه تسک‌ها، پلی‌بوک‌ها و تعامل‌های مهم به‌صورت خودکار اینجا ثبت می‌شوند."
              />
            ) : visibleMemories.length === 0 ? (
              <EmptyState
                compact
                icon={Search}
                title="نتیجه مرتبطی پیدا نشد"
                description="عبارت یا فیلتر دیگری امتحان کن."
              />
            ) : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {visibleMemories.map((memory) => (
                  <MemoryCard
                    key={memory.id}
                    memory={memory}
                    onView={() => setViewing({ type: "memory", item: memory })}
                    onDelete={() =>
                      setDeleting({ type: "memory", item: memory })
                    }
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <div>
              <h2 className="font-semibold text-white">کتابچه‌های راهبردی</h2>
              <p className="mt-1 text-[11px] text-slate-600">
                متن هر پلی‌بوک هنگام بارگذاری به بخش‌های برداری تبدیل می‌شود.
              </p>
            </div>
            <span className="text-xs text-slate-600">
              {faNumber(playbooks.length)} مورد
            </span>
          </CardHeader>
          <CardContent>
            {playbooks.length === 0 ? (
              <EmptyState
                icon={BookOpen}
                title="پلی‌بوکی بارگذاری نشده"
                description="یک‌بار استراتژی خود را ثبت کن تا همراه در تصمیم‌های روزانه از آن استفاده کند."
                action={
                  <Button size="sm" onClick={() => setCreateOpen(true)}>
                    <Plus size={14} />
                    ساخت پلی‌بوک
                  </Button>
                }
              />
            ) : (
              <div className="grid gap-3 lg:grid-cols-2">
                {playbooks.map((book) => (
                  <article
                    key={book.id}
                    className="group rounded-2xl border border-line/70 bg-white/[.018] p-5 transition hover:border-slate-600"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <span className="grid size-10 place-items-center rounded-xl border border-primary/15 bg-primary/[.08] text-primary-soft">
                        <BookOpen size={17} />
                      </span>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          onClick={() =>
                            setViewing({ type: "playbook", item: book })
                          }
                          aria-label="مشاهده پلی‌بوک"
                        >
                          <Eye size={14} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8 text-slate-600 hover:text-rose-300"
                          onClick={() =>
                            setDeleting({ type: "playbook", item: book })
                          }
                          aria-label="حذف پلی‌بوک"
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </div>
                    <h3 className="mt-4 font-semibold text-slate-200">
                      {book.title}
                    </h3>
                    <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-600">
                      <span>
                        {book.module_name === "salon"
                          ? "ماژول سالن"
                          : book.module_name === "personal"
                            ? "ماژول شخصی"
                            : "دانش عمومی"}
                      </span>
                      <span>•</span>
                      <span>{faNumber(book.chunk_count)} بخش برداری</span>
                    </div>
                    <p className="mt-4 line-clamp-3 text-xs leading-7 text-slate-500">
                      {book.content}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <CreatePlaybookDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        loading={saving}
        onCreate={async (payload) => {
          setSaving(true);
          setError("");
          try {
            const book = await api.uploadPlaybook(payload);
            onPlaybookAdded(book);
            await onChanged();
            setCreateOpen(false);
            notify("پلی‌بوک بردارسازی و ذخیره شد", "success");
          } catch (reason) {
            setError(reason.message);
          } finally {
            setSaving(false);
          }
        }}
        error={error}
      />
      <Dialog
        open={Boolean(viewing)}
        onClose={() => setViewing(null)}
        size="lg"
        title={
          viewing?.type === "playbook"
            ? viewing.item.title
            : sourceLabels[viewing?.item?.source] || "جزئیات حافظه"
        }
        description={
          viewing ? `ثبت‌شده در ${faDate(viewing.item.created_at)}` : ""
        }
      >
        <div className="whitespace-pre-wrap text-sm leading-8 text-slate-300">
          {viewing?.item?.content}
        </div>
        {viewing?.type === "memory" && (
          <div className="mt-5 rounded-xl border border-line bg-background/60 p-4">
            <p className="text-[10px] font-semibold text-slate-600">
              اطلاعات منبع
            </p>
            <pre
              dir="ltr"
              className="mt-2 overflow-auto text-left text-[10px] text-slate-500"
            >
              {JSON.stringify(viewing.item.entry_metadata, null, 2)}
            </pre>
          </div>
        )}
      </Dialog>
      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        loading={saving}
        title={
          deleting?.type === "playbook" ? "حذف پلی‌بوک؟" : "حذف این حافظه؟"
        }
        description={
          deleting?.type === "playbook"
            ? "متن پلی‌بوک و تمام بخش‌های برداری وابسته به آن حذف می‌شوند."
            : "این داده دیگر در جستجو و زمینه تصمیم‌های آینده استفاده نخواهد شد."
        }
      />
    </div>
  );
}

function Tab({ active, icon: Icon, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`flex h-9 items-center gap-2 rounded-lg px-3 text-xs font-medium transition ${active ? "bg-elevated text-white shadow-sm" : "text-slate-600 hover:text-slate-300"}`}
    >
      <Icon size={14} />
      {children}
    </button>
  );
}

function MemoryStat({ icon: Icon, label, value, tone }) {
  return (
    <div className="rounded-xl border border-line/70 bg-surface/75 p-3 sm:flex sm:items-center sm:gap-3 sm:p-4">
      <span
        className={`grid size-9 place-items-center rounded-xl bg-white/[.035] ${tone}`}
      >
        <Icon size={16} />
      </span>
      <div className="mt-2 sm:mt-0">
        <p className="text-lg font-bold text-white">{faNumber(value)}</p>
        <p className="text-[10px] text-slate-600">{label}</p>
      </div>
    </div>
  );
}

function MemoryCard({ memory, onView, onDelete }) {
  return (
    <article className="group flex min-h-44 flex-col rounded-2xl border border-line/70 bg-white/[.015] p-4 transition hover:border-slate-600">
      <div className="flex items-center justify-between gap-3">
        <span className="rounded-lg bg-emerald-400/[.07] px-2 py-1 text-[9px] font-bold text-mint">
          {sourceLabels[memory.source] || memory.source}
        </span>
        {memory.score != null && (
          <span className="text-[9px] text-slate-600">
            شباهت {faNumber(Math.round(memory.score * 100))}٪
          </span>
        )}
      </div>
      <p className="mt-4 flex-1 text-xs leading-7 text-slate-400">
        {truncate(memory.content, 145)}
      </p>
      <div className="mt-3 flex items-center justify-between border-t border-line/60 pt-3">
        <span className="text-[9px] text-slate-700">
          {faDate(memory.created_at, { year: undefined })}
        </span>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={onView}
            aria-label="مشاهده حافظه"
          >
            <Eye size={13} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-slate-700 hover:text-rose-300"
            onClick={onDelete}
            aria-label="حذف حافظه"
          >
            <Trash2 size={13} />
          </Button>
        </div>
      </div>
    </article>
  );
}

function CreatePlaybookDialog({ open, onClose, onCreate, loading, error }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [moduleName, setModuleName] = useState("");
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="پلی‌بوک جدید"
      description="قوانین و تجربه‌ای را ثبت کن که همراه باید در تصمیم‌های آینده همیشه به یاد داشته باشد."
      size="lg"
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onCreate({ title, content, module_name: moduleName || null });
        }}
        className="space-y-4"
      >
        <div className="grid gap-4 sm:grid-cols-[1fr_220px]">
          <Field label="عنوان پلی‌بوک">
            <Input
              aria-label="عنوان پلی‌بوک"
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="مثلاً استراتژی پیگیری سالن‌ها"
            />
          </Field>
          <Field label="حوزه دانش">
            <Select
              value={moduleName}
              onChange={(event) => setModuleName(event.target.value)}
            >
              <option value="">عمومی</option>
              <option value="salon">بازاریابی سالن</option>
              <option value="personal">کارهای شخصی</option>
            </Select>
          </Field>
        </div>
        <Field label="متن پلی‌بوک" hint={`${faNumber(content.length)} نویسه`}>
          <Textarea
            aria-label="متن پلی‌بوک"
            required
            value={content}
            onChange={(event) => setContent(event.target.value)}
            className="min-h-64"
            placeholder="قوانین، فاصله پیگیری، لحن، معیار اولویت‌بندی و تجربه‌های مهم…"
          />
        </Field>
        <div className="flex gap-3 rounded-xl border border-cyan-400/10 bg-cyan-400/[.035] p-3 text-[11px] leading-6 text-slate-500">
          <Sparkles className="mt-0.5 shrink-0 text-cyan-300" size={15} />
          متن پس از ذخیره به بخش‌های کوچک تقسیم و بردارسازی می‌شود تا جستجوی
          معنایی و زمینه‌سازی Planner ممکن باشد.
        </div>
        {error && <p className="text-xs text-rose-300">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
          <Button
            type="submit"
            loading={loading}
            disabled={!title.trim() || !content.trim()}
          >
            ذخیره و بردارسازی
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
