import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BellRing,
  Bot,
  BrainCircuit,
  BriefcaseBusiness,
  ChevronLeft,
  CircleGauge,
  Command,
  LayoutDashboard,
  LayoutGrid,
  ListTodo,
  Menu,
  RefreshCw,
  Scissors,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";
import { api } from "./lib/api";
import { cn } from "./lib/utils";
import { ApprovalQueue } from "./components/ApprovalQueue";
import { CompanionPanel } from "./components/CompanionPanel";
import {
  CommandPalette,
  NotificationPopover,
  ToastStack,
} from "./components/AppOverlays";
import { MemoryPanel } from "./components/MemoryPanel";
import { ModulesPanel } from "./components/ModulesPanel";
import { OverviewDashboard } from "./components/OverviewDashboard";
import { PersonalView } from "./components/PersonalView";
import { SalonView } from "./components/SalonView";
import { SettingsPanel } from "./components/SettingsPanel";
import { TaskDetail } from "./components/TaskDetail";
import { TaskInbox } from "./components/TaskInbox";
import { ToolsPanel } from "./components/ToolsPanel";
import { Button } from "./components/ui/button";

const coreNavigation = [
  { id: "companion", label: "همراه من", icon: Bot },
  { id: "overview", label: "نمای کلی", icon: LayoutDashboard },
  { id: "tasks", label: "تسک‌ها", icon: ListTodo },
  {
    id: "approval",
    label: "مرکز تأیید",
    icon: ShieldCheck,
    badge: "approvals",
  },
  { id: "memory", label: "حافظه و دانش", icon: BrainCircuit },
  { id: "tools", label: "ابزارها", icon: Wrench },
  { id: "modules", label: "ماژول‌ها", icon: LayoutGrid },
];
const skillNavigation = [
  { id: "salon", label: "رشد سالن‌ها", icon: Scissors },
  { id: "personal", label: "پروژه‌های شخصی", icon: BriefcaseBusiness },
];
const panelTitles = {
  companion: "همراه من",
  overview: "نمای کلی",
  tasks: "تسک‌ها",
  detail: "جزئیات تسک",
  approval: "مرکز تأیید",
  memory: "حافظه و دانش",
  tools: "ابزارها",
  modules: "ماژول‌ها",
  salon: "رشد سالن‌ها",
  personal: "پروژه‌های شخصی",
  settings: "تنظیمات",
};
const initialData = {
  tasks: [],
  approvals: [],
  memories: [],
  playbooks: [],
  tools: [],
  salons: [],
  salonPlan: [],
  projects: [],
  reminders: [],
  serverNotifications: [],
  unreadNotifications: 0,
  system: {},
  health: false,
};

export default function App() {
  const [active, setActive] = useState("companion");
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [slowLoading, setSlowLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState(initialData);
  const [selectedTask, setSelectedTask] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [refreshInterval, setRefreshInterval] = useState(() =>
    Number(localStorage.getItem("agent-refresh-interval") || 0),
  );

  const notify = useCallback((message, type = "success") => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((items) => [...items, { id, message, type }]);
    window.setTimeout(
      () => setToasts((items) => items.filter((item) => item.id !== id)),
      4500,
    );
  }, []);

  useEffect(() => {
    if (!notificationsOpen || !data.unreadNotifications) return;
    api
      .markAllNotificationsRead()
      .then(() =>
        setData((current) => ({
          ...current,
          unreadNotifications: 0,
          serverNotifications: current.serverNotifications.map((item) => ({
            ...item,
            read_at: item.read_at || new Date().toISOString(),
          })),
        })),
      )
      .catch(() => {});
  }, [notificationsOpen, data.unreadNotifications]);

  const loadDashboard = useCallback(
    async (silent = false) => {
      if (silent) setRefreshing(true);
      else {
        setLoading(true);
        setSlowLoading(false);
      }
      const requests = [
        api.listTasks(),
        api.listApprovals(),
        api.listMemory(),
        api.listPlaybooks(),
        api.listTools(),
        api.listSalons(),
        api.dailySalonPlan(),
        api.listProjects(),
        api.reminders(),
        api.systemStatus(),
        api.getNotifications(),
      ];
      const results = await Promise.allSettled(requests);
      const keys = [
        "tasks",
        "approvals",
        "memories",
        "playbooks",
        "tools",
        "salons",
        "salonPlan",
        "projects",
        "reminders",
        "system",
      ];
      setData((current) => {
        const next = { ...current };
        results.forEach((result, index) => {
          if (result.status === "fulfilled") next[keys[index]] = result.value;
        });
        next.health =
          results[9].status === "fulfilled" && results[9].value.api_ready;
        const notificationsResult = results[10];
        if (notificationsResult.status === "fulfilled") {
          next.serverNotifications =
            notificationsResult.value.notifications || [];
          next.unreadNotifications = notificationsResult.value.unread || 0;
        }
        return next;
      });
      const failures = results.filter((result) => result.status === "rejected");
      if (failures.length)
        notify(
          `بارگذاری ${failures.length.toLocaleString("fa-IR")} بخش با خطا روبه‌رو شد`,
          "error",
        );
      setLoading(false);
      setRefreshing(false);
    },
    [notify],
  );

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);
  useEffect(() => {
    if (!loading) {
      setSlowLoading(false);
      return undefined;
    }
    const timer = window.setTimeout(() => setSlowLoading(true), 5000);
    return () => window.clearTimeout(timer);
  }, [loading]);
  useEffect(() => {
    function openCommand(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
    }
    window.addEventListener("keydown", openCommand);
    return () => window.removeEventListener("keydown", openCommand);
  }, []);
  useEffect(() => {
    if (!refreshInterval) return undefined;
    const timer = window.setInterval(
      () => loadDashboard(true),
      refreshInterval * 1000,
    );
    return () => window.clearInterval(timer);
  }, [refreshInterval, loadDashboard]);

  function navigate(panel) {
    setActive(panel);
    setMenuOpen(false);
    setNotificationsOpen(false);
  }

  async function selectTask(taskOrId) {
    const id = typeof taskOrId === "number" ? taskOrId : taskOrId.id;
    setBusy(true);
    try {
      setSelectedTask(await api.getTask(id));
      navigate("detail");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function planTask(id) {
    setBusy(true);
    try {
      await api.planTask(id);
      const detail = await api.getTask(id);
      setSelectedTask(detail);
      await loadDashboard(true);
      notify("برنامه اجرایی با موفقیت ساخته شد", "success");
    } catch (reason) {
      notify(reason.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function executeTask(id) {
    setBusy(true);
    try {
      const detail = await api.executeTask(id);
      setSelectedTask(detail);
      await loadDashboard(true);
      notify(
        detail.status === "paused"
          ? "اجرا در نقطه امن متوقف و منتظر تصمیم شماست"
          : "مسیر اجرا تکمیل شد",
        "success",
      );
    } catch (reason) {
      notify(reason.message, "error");
      try {
        setSelectedTask(await api.getTask(id));
      } catch {
        /* keep current detail */
      }
      await loadDashboard(true);
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision(step, updatedTask) {
    setSelectedTask((current) =>
      current?.id === updatedTask.id ? updatedTask : current,
    );
    await loadDashboard(true);
  }

  async function handleToolChange(tool, patch) {
    const updated = await api.updateTool(tool.name, patch);
    setData((current) => ({
      ...current,
      tools: current.tools.map((item) =>
        item.name === updated.name ? updated : item,
      ),
    }));
    return updated;
  }

  function handleTaskChanged(fresh, options = {}) {
    setSelectedTask(fresh);
    setData((current) => ({
      ...current,
      tasks: current.tasks.map((task) =>
        task.id === fresh.id ? { ...task, ...fresh } : task,
      ),
    }));
    if (options.refreshAll) loadDashboard(true);
  }

  async function handleTaskDeleted() {
    setSelectedTask(null);
    navigate("tasks");
    await loadDashboard(true);
  }

  async function handleTaskCreated() {
    await loadDashboard(true);
  }

  function changeRefreshInterval(seconds) {
    setRefreshInterval(seconds);
    localStorage.setItem("agent-refresh-interval", String(seconds));
    notify(
      seconds
        ? `همگام‌سازی خودکار هر ${seconds.toLocaleString("fa-IR")} ثانیه فعال شد`
        : "همگام‌سازی خودکار خاموش شد",
      "success",
    );
  }

  const modules = useMemo(
    () => [
      {
        name: "salon",
        title: "رشد سالن‌ها",
        description:
          "مدیریت سرنخ، تعامل، متن ارتباطی و فاصله امن پیگیری بر اساس پلی‌بوک.",
        count: data.salons.length,
        actionCount: data.salonPlan.length,
      },
      {
        name: "personal",
        title: "پروژه‌های شخصی و فریلنس",
        description:
          "چرخه پروژه، پروپوزال قابل تأیید و ددلاین‌های نزدیک در یک فضای منظم.",
        count: data.projects.length,
        actionCount: data.reminders.length,
      },
    ],
    [
      data.salons.length,
      data.salonPlan.length,
      data.projects.length,
      data.reminders.length,
    ],
  );

  const panels = {
    companion: (
      <CompanionPanel
        system={data.system}
        approvals={data.approvals.length}
        onNavigate={navigate}
        onChanged={() => loadDashboard(true)}
        notify={notify}
      />
    ),
    overview: (
      <OverviewDashboard
        data={data}
        onNavigate={navigate}
        onTaskSelect={selectTask}
        notify={notify}
        onRefresh={() => loadDashboard(true)}
      />
    ),
    tasks: (
      <TaskInbox
        tasks={data.tasks}
        onCreated={async (task) => {
          setData((current) => ({
            ...current,
            tasks: [task, ...current.tasks],
          }));
          notify("تسک جدید ثبت شد", "success");
        }}
        onSelect={selectTask}
      />
    ),
    detail: (
      <TaskDetail
        task={selectedTask}
        tools={data.tools}
        busy={busy}
        onBack={() => navigate("tasks")}
        onPlan={planTask}
        onExecute={executeTask}
        onChanged={handleTaskChanged}
        onDeleted={handleTaskDeleted}
        onDecision={handleDecision}
        notify={notify}
      />
    ),
    approval: (
      <ApprovalQueue
        steps={data.approvals}
        onApproved={handleDecision}
        onRejected={handleDecision}
        onViewTask={selectTask}
      />
    ),
    memory: (
      <MemoryPanel
        memories={data.memories}
        playbooks={data.playbooks}
        onPlaybookAdded={(book) =>
          setData((current) => ({
            ...current,
            playbooks: [book, ...current.playbooks],
          }))
        }
        onChanged={() => loadDashboard(true)}
        notify={notify}
      />
    ),
    tools: (
      <ToolsPanel
        tools={data.tools}
        onChange={handleToolChange}
        onInvoked={handleTaskCreated}
        notify={notify}
      />
    ),
    modules: (
      <ModulesPanel modules={modules} tools={data.tools} onOpen={navigate} />
    ),
    salon: (
      <SalonView
        salons={data.salons}
        dailyPlan={data.salonPlan}
        onCreated={() => {}}
        onChanged={() => loadDashboard(true)}
        onTaskCreated={handleTaskCreated}
        notify={notify}
      />
    ),
    personal: (
      <PersonalView
        projects={data.projects}
        reminders={data.reminders}
        onCreated={() => {}}
        onChanged={() => loadDashboard(true)}
        onTaskCreated={handleTaskCreated}
        notify={notify}
      />
    ),
    settings: (
      <SettingsPanel
        status={data.system}
        refreshInterval={refreshInterval}
        onRefreshInterval={changeRefreshInterval}
        onRefresh={() => loadDashboard(true)}
        onStatusChanged={() => loadDashboard(true)}
        notify={notify}
      />
    ),
  };

  return (
    <div dir="rtl" className="min-h-screen">
      <div className="app-grid pointer-events-none fixed inset-0" />
      <Sidebar
        active={active}
        selectedTask={selectedTask}
        onNavigate={navigate}
        approvals={data.approvals.length}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        system={data.system}
      />
      {menuOpen && (
        <button
          aria-label="بستن پوشش منو"
          className="fixed inset-0 z-30 bg-black/70 backdrop-blur-sm lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <Topbar
        active={active}
        loading={refreshing}
        notificationCount={
          data.approvals.length +
          data.reminders.length +
          (data.unreadNotifications || 0)
        }
        notificationsOpen={notificationsOpen}
        approvals={data.approvals}
        reminders={data.reminders}
        serverNotifications={data.serverNotifications}
        onMenu={() => setMenuOpen(true)}
        onRefresh={() => loadDashboard(true)}
        onSearch={() => setSearchOpen(true)}
        onNotifications={() => setNotificationsOpen((value) => !value)}
        onCloseNotifications={() => setNotificationsOpen(false)}
        onNavigate={navigate}
      />
      <main className="relative px-4 pb-24 pt-6 sm:px-7 lg:mr-[264px] lg:pb-10 lg:pt-8">
        <div className="mx-auto max-w-[1320px]">
          {loading ? (
            <LoadingScreen slow={slowLoading} onRetry={() => loadDashboard()} />
          ) : (
            panels[active] || panels.overview
          )}
        </div>
      </main>
      <MobileNav
        hidden={menuOpen}
        active={active}
        approvals={data.approvals.length}
        onNavigate={navigate}
      />
      <CommandPalette
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        tasks={data.tasks}
        salons={data.salons}
        projects={data.projects}
        onTask={selectTask}
        onNavigate={navigate}
      />
      <ToastStack
        toasts={toasts}
        onDismiss={(id) =>
          setToasts((items) => items.filter((item) => item.id !== id))
        }
      />
    </div>
  );
}

function Sidebar({
  active,
  selectedTask,
  onNavigate,
  approvals,
  open,
  onClose,
  system,
}) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 right-0 z-40 flex w-[278px] flex-col overflow-hidden border-l border-line/75 bg-[#090d15]/96 shadow-2xl backdrop-blur-xl transition-transform lg:w-[264px] lg:translate-x-0",
        open ? "translate-x-0" : "translate-x-full",
      )}
      aria-label="ناوبری اصلی"
    >
      <div className="flex h-[76px] shrink-0 items-center justify-between border-b border-line/50 px-5">
        <button
          onClick={() => onNavigate("companion")}
          className="flex items-center gap-3 text-right"
        >
          <span className="relative grid size-10 place-items-center rounded-[14px] bg-gradient-to-br from-[#9178ff] to-[#5d3bdb] text-white shadow-[0_10px_35px_rgba(124,92,255,.32)]">
            <Sparkles size={18} />
            <span className="absolute -left-0.5 -top-0.5 size-2.5 rounded-full border-2 border-[#090d15] bg-mint" />
          </span>
          <span>
            <strong className="block text-[17px] tracking-tight text-white">
              همراه
            </strong>
            <span className="text-[9px] font-medium tracking-[.18em] text-slate-700">
              PERSONAL AGENT
            </span>
          </span>
        </button>
        <Button
          variant="ghost"
          size="icon"
          className="size-9 lg:hidden"
          onClick={onClose}
          aria-label="بستن منو"
        >
          <X size={18} />
        </Button>
      </div>

      <div
        className="no-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain px-3.5 py-4"
        data-testid="mobile-menu-scroll-area"
      >
        <p className="mb-2 px-3 text-[9px] font-bold tracking-[.15em] text-slate-700">
          فضای کار
        </p>
        <nav className="space-y-1">
          {coreNavigation.map((item) => (
            <NavItem
              key={item.id}
              {...item}
              active={
                active === item.id ||
                (item.id === "tasks" && active === "detail")
              }
              count={item.badge ? approvals : 0}
              onClick={() => onNavigate(item.id)}
            />
          ))}
        </nav>
        {selectedTask && active === "detail" && (
          <button
            onClick={() => onNavigate("detail")}
            className="mr-8 mt-1 flex w-[calc(100%-2rem)] items-center gap-2 rounded-lg border border-primary/10 bg-primary/[.04] px-3 py-2 text-right text-[10px] text-primary-soft"
          >
            <span className="size-1.5 shrink-0 rounded-full bg-primary" />
            <span className="truncate">{selectedTask.title}</span>
          </button>
        )}

        <p className="mb-2 mt-6 px-3 text-[9px] font-bold tracking-[.15em] text-slate-700">
          مهارت‌های تخصصی
        </p>
        <nav className="space-y-1">
          {skillNavigation.map((item) => (
            <NavItem
              key={item.id}
              {...item}
              active={active === item.id}
              onClick={() => onNavigate(item.id)}
            />
          ))}
        </nav>
      </div>

      <div className="shrink-0 space-y-2 border-t border-line/60 bg-[#090d15] px-3.5 pb-3.5 pt-3">
        <NavItem
          id="settings"
          label="تنظیمات و سیستم"
          icon={Settings2}
          active={active === "settings"}
          onClick={() => onNavigate("settings")}
        />
        <button
          onClick={() => onNavigate("settings")}
          className="w-full rounded-2xl border border-line/80 bg-gradient-to-bl from-white/[.035] to-transparent p-3.5 text-right transition hover:border-slate-600"
        >
          <div className="flex items-center gap-2.5">
            <span
              className={`grid size-8 place-items-center rounded-lg ${system.api_ready ? "bg-emerald-400/[.08] text-emerald-300" : "bg-amber-400/[.08] text-amber-300"}`}
            >
              <Bot size={15} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-medium text-slate-300">
                Agent Core
              </p>
              <p
                className={`mt-0.5 text-[9px] ${system.api_ready ? "text-emerald-400" : "text-amber-300"}`}
              >
                ● {system.api_ready ? "آنلاین و آماده" : "در حال اتصال"}
              </p>
            </div>
            <ChevronLeft size={13} className="text-slate-700" />
          </div>
          <div className="mt-3 flex items-center justify-between text-[9px] text-slate-700">
            <span>
              {system.embedding_backend === "gemini"
                ? "Gemini Embedding"
                : "Local Embedding"}
            </span>
            <span>{system.timezone || "—"}</span>
          </div>
        </button>
      </div>
    </aside>
  );
}

function NavItem({ label, icon: Icon, active, count = 0, onClick }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "group flex h-10 w-full items-center gap-3 rounded-xl px-3 text-xs transition",
        active
          ? "bg-primary/[.10] text-violet-100 ring-1 ring-inset ring-primary/15"
          : "text-slate-500 hover:bg-white/[.035] hover:text-slate-300",
      )}
    >
      <Icon
        size={16}
        strokeWidth={active ? 2.2 : 1.8}
        className={active ? "text-primary-soft" : "text-slate-650"}
      />
      <span className="flex-1 text-right">{label}</span>
      {count > 0 && (
        <span className="grid min-w-5 place-items-center rounded-full bg-primary px-1.5 py-0.5 text-[9px] text-white">
          {count.toLocaleString("fa-IR")}
        </span>
      )}
      {active && <ChevronLeft size={13} className="text-primary-soft" />}
    </button>
  );
}

function Topbar({
  active,
  loading,
  notificationCount,
  notificationsOpen,
  serverNotifications = [],
  approvals,
  reminders,
  onMenu,
  onRefresh,
  onSearch,
  onNotifications,
  onCloseNotifications,
  onNavigate,
}) {
  const date = new Intl.DateTimeFormat("fa-IR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());
  return (
    <header className="sticky top-0 z-20 flex h-[70px] items-center justify-between border-b border-line/65 bg-background/78 px-4 backdrop-blur-xl sm:px-7 lg:mr-[264px]">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          variant="secondary"
          size="icon"
          className="lg:hidden"
          onClick={onMenu}
          aria-label="باز کردن منو"
        >
          <Menu size={18} />
        </Button>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-200">
            {panelTitles[active]}
          </p>
          <p className="mt-1 hidden text-[9px] text-slate-650 sm:block">
            {date}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onSearch}
          className="hidden h-10 w-64 items-center gap-2 rounded-xl border border-line bg-surface/70 px-3 text-right text-xs text-slate-600 transition hover:border-slate-600 hover:text-slate-400 md:flex"
        >
          <Search size={15} />
          <span className="flex-1">جستجوی سراسری…</span>
          <span
            dir="ltr"
            className="rounded border border-line px-1.5 py-0.5 text-[9px]"
          >
            ⌘ K
          </span>
        </button>
        <Button
          variant="secondary"
          size="icon"
          className="md:hidden"
          onClick={onSearch}
          aria-label="جستجو"
        >
          <Search size={16} />
        </Button>
        <Button
          variant="secondary"
          size="icon"
          onClick={onRefresh}
          disabled={loading}
          aria-label="تازه‌سازی"
        >
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
        </Button>
        <div className="relative">
          <Button
            variant="secondary"
            size="icon"
            onClick={onNotifications}
            aria-label="اعلان‌ها"
          >
            <BellRing size={16} />
            {notificationCount > 0 && (
              <span className="absolute -left-1 -top-1 grid min-w-4 place-items-center rounded-full border-2 border-background bg-rose-500 px-1 text-[8px] text-white">
                {notificationCount.toLocaleString("fa-IR")}
              </span>
            )}
          </Button>
          <NotificationPopover
            open={notificationsOpen}
            approvals={approvals}
            reminders={reminders}
            serverNotifications={serverNotifications}
            onClose={onCloseNotifications}
            onNavigate={onNavigate}
          />
        </div>
        <Button
          variant="secondary"
          size="icon"
          onClick={() => onNavigate("settings")}
          aria-label="تنظیمات"
        >
          <Settings2 size={16} />
        </Button>
      </div>
    </header>
  );
}

function MobileNav({ active, approvals, onNavigate, hidden = false }) {
  if (hidden) return null;
  const items = [
    coreNavigation[0],
    { id: "tasks", label: "تسک‌ها", icon: ListTodo },
    coreNavigation[2],
    skillNavigation[0],
    skillNavigation[1],
  ];
  return (
    <nav
      data-testid="mobile-bottom-nav"
      className="fixed inset-x-3 bottom-3 z-30 flex h-16 items-center justify-around rounded-2xl border border-line bg-[#0b1019]/95 px-2 shadow-popover backdrop-blur-xl lg:hidden"
    >
      {items.map((item) => {
        const Icon = item.icon;
        const isActive =
          active === item.id || (item.id === "tasks" && active === "detail");
        return (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`relative flex min-w-12 flex-col items-center gap-1 rounded-xl px-2 py-2 text-[9px] transition ${isActive ? "bg-primary/[.10] text-primary-soft" : "text-slate-600"}`}
          >
            <Icon size={17} />
            <span>{item.label.split(" ")[0]}</span>
            {item.id === "approval" && approvals > 0 && (
              <span className="absolute left-1 top-1 size-2 rounded-full bg-rose-500" />
            )}
          </button>
        );
      })}
    </nav>
  );
}

function LoadingScreen({ slow, onRetry }) {
  return (
    <div className="grid min-h-[68vh] place-items-center">
      <div className="max-w-sm text-center">
        <span className="relative mx-auto grid size-16 place-items-center rounded-2xl border border-primary/15 bg-primary/[.06] text-primary-soft">
          <CircleGauge className="animate-spin" size={25} />
          <span className="absolute inset-0 animate-pulse-soft rounded-2xl ring-1 ring-primary/20" />
        </span>
        <p className="mt-4 text-sm font-medium text-slate-400">
          در حال همگام‌سازی همراه
        </p>
        <p className="mt-1 text-[10px] text-slate-700">
          تسک‌ها، حافظه و ماژول‌ها
        </p>
        {slow && (
          <div className="mt-5 animate-slide-up rounded-xl border border-amber-400/15 bg-amber-400/[.04] p-4">
            <p className="text-xs font-medium text-amber-200">
              اتصال به Backend بیشتر از معمول طول کشیده است
            </p>
            <p className="mt-1 text-[10px] leading-5 text-slate-600">
              این مرحله به Gemini وابسته نیست. سرور API یا اتصال Preview را
              بررسی کنید.
            </p>
            <Button
              className="mt-3"
              size="sm"
              variant="secondary"
              onClick={onRetry}
            >
              <RefreshCw size={14} /> تلاش دوباره
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
