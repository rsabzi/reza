import { useMemo, useState } from "react";
import {
  Activity,
  Bot,
  CheckCircle2,
  Filter,
  LockKeyhole,
  Play,
  Power,
  Search,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { api } from "../lib/api";
import { faNumber, toolLabels } from "../lib/format";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { Input, Select } from "./ui/input";
import { EmptyState } from "./EmptyState";
import { PanelTitle } from "./PanelTitle";

const runnableArgs = {
  echo: { value: "آزمایش موفق ابزار از داشبورد" },
  daily_salon_plan: {},
  daily_personal_reminder: {},
};

function Switch({ checked, onChange, label, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 rounded-full border transition focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50 ${checked ? "border-primary/40 bg-primary" : "border-slate-700 bg-slate-800"}`}
    >
      <span
        className={`absolute top-[3px] size-4 rounded-full bg-white shadow transition ${checked ? "right-[22px]" : "right-[3px]"}`}
      />
    </button>
  );
}

export function ToolsPanel({
  tools = [],
  onChange = () => {},
  onInvoked = () => {},
  notify = () => {},
}) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(null);
  const visible = useMemo(
    () =>
      tools.filter((tool) => {
        const match =
          !search ||
          `${tool.name} ${tool.description}`
            .toLowerCase()
            .includes(search.toLowerCase());
        const state =
          filter === "all" ||
          (filter === "approval"
            ? tool.requires_approval
            : filter === "enabled"
              ? tool.enabled
              : !tool.enabled);
        return match && state;
      }),
    [tools, search, filter],
  );

  async function change(tool, patch) {
    setBusy(`${tool.name}-policy`);
    try {
      await onChange(tool, patch);
      notify("سیاست ابزار ذخیره شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(null);
    }
  }

  async function runTest(tool) {
    setBusy(`${tool.name}-run`);
    try {
      const task = await api.createTask({
        title: `آزمایش ابزار: ${toolLabels[tool.name] || tool.name}`,
        description: "ایجادشده از پنل ابزارها",
      });
      const step = await api.invokeTool(tool.name, {
        task_id: task.id,
        arguments: runnableArgs[tool.name],
      });
      onInvoked(task, step);
      notify(
        step.status === "needs_approval"
          ? "آزمایش به صف تأیید اضافه شد"
          : "ابزار با موفقیت اجرا شد",
        "success",
      );
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(null);
    }
  }

  const enabledCount = tools.filter((tool) => tool.enabled).length;
  const approvalCount = tools.filter((tool) => tool.requires_approval).length;

  return (
    <div data-testid="tools-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="CAPABILITY CONTROL"
        title="ابزارها و مرز اختیار"
        description="مشخص کن همراه چه کاری را خودکار انجام دهد و برای کدام اقدام حتماً از شما اجازه بگیرد."
        meta={
          <span className="text-[10px] text-slate-600">
            {faNumber(enabledCount)} ابزار فعال
          </span>
        }
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <ToolStat icon={Wrench} label="ابزار ثبت‌شده" value={tools.length} />
        <ToolStat
          icon={Power}
          label="دسترسی فعال"
          value={enabledCount}
          tone="text-emerald-300"
        />
        <ToolStat
          icon={ShieldCheck}
          label="محافظت‌شده"
          value={approvalCount}
          tone="text-amber-300"
        />
      </div>

      <Card className="mb-5">
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search
              className="absolute right-3 top-3 text-slate-600"
              size={15}
            />
            <Input
              aria-label="جستجوی ابزار"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="h-10 pr-9"
              placeholder="جستجوی نام یا کاربرد ابزار…"
            />
          </div>
          <div className="relative">
            <Filter
              className="pointer-events-none absolute right-3 top-3 text-slate-600"
              size={14}
            />
            <Select
              aria-label="فیلتر ابزار"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              className="h-10 w-full pr-8 sm:w-48"
            >
              <option value="all">همه ابزارها</option>
              <option value="enabled">فقط فعال‌ها</option>
              <option value="approval">نیازمند تأیید</option>
              <option value="disabled">غیرفعال‌ها</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      {tools.length === 0 ? (
        <EmptyState
          icon={Wrench}
          title="ابزاری ثبت نشده"
          description="با بارگذاری ماژول‌ها، ابزارهای آن‌ها اینجا ظاهر می‌شوند."
        />
      ) : visible.length === 0 ? (
        <EmptyState compact icon={Search} title="ابزار مطابق فیلتر پیدا نشد" />
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {visible.map((tool) => (
            <Card
              key={tool.name}
              className={`transition ${!tool.enabled ? "opacity-60" : ""}`}
            >
              <CardContent>
                <div className="flex items-start gap-3">
                  <span
                    className={`grid size-11 shrink-0 place-items-center rounded-xl border ${tool.enabled ? "border-primary/15 bg-primary/[.07] text-primary-soft" : "border-line bg-slate-800/60 text-slate-600"}`}
                  >
                    <Wrench size={18} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <code
                        dir="ltr"
                        className="text-sm font-semibold text-white"
                      >
                        {tool.name}
                      </code>
                      <Badge status={tool.enabled ? "active" : "inactive"}>
                        {tool.enabled ? "فعال" : "خاموش"}
                      </Badge>
                    </div>
                    <p className="mt-2 text-xs leading-6 text-slate-500">
                      {tool.description}
                    </p>
                  </div>
                </div>

                <div className="mt-5 grid gap-2 sm:grid-cols-2">
                  <div className="flex items-center justify-between rounded-xl border border-line/70 bg-background/45 p-3">
                    <span className="flex items-center gap-2 text-[11px] text-slate-400">
                      <LockKeyhole
                        size={14}
                        className={
                          tool.requires_approval
                            ? "text-amber-300"
                            : "text-slate-600"
                        }
                      />
                      تأیید قبل از اجرا
                    </span>
                    <Switch
                      label={`مجوز ${tool.name}`}
                      checked={tool.requires_approval}
                      disabled={busy === `${tool.name}-policy`}
                      onChange={(value) =>
                        change(tool, { requires_approval: value })
                      }
                    />
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-line/70 bg-background/45 p-3">
                    <span className="flex items-center gap-2 text-[11px] text-slate-400">
                      <Power
                        size={14}
                        className={
                          tool.enabled ? "text-emerald-300" : "text-slate-600"
                        }
                      />
                      دسترسی ابزار
                    </span>
                    <Switch
                      label={`فعال بودن ${tool.name}`}
                      checked={tool.enabled}
                      disabled={busy === `${tool.name}-policy`}
                      onChange={(value) => change(tool, { enabled: value })}
                    />
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between gap-3 border-t border-line/60 pt-4">
                  <span className="flex items-center gap-1.5 text-[10px] text-slate-600">
                    <Activity size={12} />
                    سیاست در فراخوانی بعدی اعمال می‌شود
                  </span>
                  {Object.hasOwn(runnableArgs, tool.name) && (
                    <Button
                      variant="ghost"
                      size="xs"
                      disabled={!tool.enabled}
                      loading={busy === `${tool.name}-run`}
                      onClick={() => runTest(tool)}
                    >
                      <Play size={13} />
                      اجرای آزمایشی
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function ToolStat({ icon: Icon, label, value, tone = "text-primary-soft" }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-line/70 bg-surface/75 p-4">
      <span
        className={`grid size-9 place-items-center rounded-xl bg-white/[.035] ${tone}`}
      >
        <Icon size={16} />
      </span>
      <div>
        <p className="text-lg font-bold text-white">{faNumber(value)}</p>
        <p className="text-[10px] text-slate-600">{label}</p>
      </div>
    </div>
  );
}
