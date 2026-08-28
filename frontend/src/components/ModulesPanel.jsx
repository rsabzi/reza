import {
  ArrowLeft,
  BriefcaseBusiness,
  CheckCircle2,
  Layers3,
  LayoutGrid,
  Scissors,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { faNumber, toolLabels } from "../lib/format";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import { EmptyState } from "./EmptyState";
import { PanelTitle } from "./PanelTitle";

const moduleMeta = {
  salon: {
    icon: Scissors,
    color: "from-violet-500/16 to-fuchsia-500/[.025]",
    iconClass: "border-violet-400/20 bg-violet-400/[.09] text-violet-300",
    tools: [
      "generate_outreach_script",
      "log_salon_interaction",
      "daily_salon_plan",
    ],
    features: ["مدیریت سرنخ‌ها", "فاصله پیگیری طبق پلی‌بوک", "حافظه تعامل‌ها"],
  },
  personal: {
    icon: BriefcaseBusiness,
    color: "from-cyan-500/14 to-emerald-500/[.02]",
    iconClass: "border-cyan-400/20 bg-cyan-400/[.09] text-cyan-300",
    tools: ["draft_project_proposal", "daily_personal_reminder"],
    features: ["چرخه وضعیت پروژه", "یادآوری ددلاین", "پیش‌نویس پروپوزال"],
  },
};

export function ModulesPanel({ modules = [], tools = [], onOpen = () => {} }) {
  return (
    <div data-testid="modules-panel" className="animate-fade-in">
      <PanelTitle
        eyebrow="SPECIALIZED SKILLS"
        title="مهارت‌های متصل به هسته"
        description="هر ماژول داده و ابزار خودش را دارد، اما از یک حافظه، مجوز و موتور اجرای مشترک استفاده می‌کند."
        meta={
          <span className="text-[10px] text-slate-600">
            معماری ماژولار و قابل توسعه
          </span>
        }
      />
      {modules.length === 0 ? (
        <EmptyState
          icon={LayoutGrid}
          title="ماژولی فعال نیست"
          description="ماژول‌های سالن و شخصی را از تنظیمات نصب فعال کنید."
        />
      ) : (
        <div className="grid gap-5 xl:grid-cols-2">
          {modules.map((module) => {
            const meta = moduleMeta[module.name] || {
              icon: LayoutGrid,
              tools: [],
              features: [],
            };
            const Icon = meta.icon;
            const moduleTools = meta.tools
              .map((name) => tools.find((tool) => tool.name === name))
              .filter(Boolean);
            return (
              <Card
                key={module.name}
                className="group overflow-hidden"
                interactive
              >
                <div
                  className={`relative bg-gradient-to-bl ${meta.color} p-5 sm:p-6`}
                >
                  <div className="absolute -left-12 -top-16 size-52 rounded-full bg-white/[.025] blur-2xl" />
                  <div className="relative flex items-start justify-between gap-4">
                    <span
                      className={`grid size-12 place-items-center rounded-2xl border ${meta.iconClass}`}
                    >
                      <Icon size={22} />
                    </span>
                    <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/15 bg-emerald-400/[.07] px-2.5 py-1 text-[10px] text-emerald-300">
                      <CheckCircle2 size={12} />
                      فعال و سالم
                    </span>
                  </div>
                  <h2 className="relative mt-6 text-xl font-bold text-white">
                    {module.title}
                  </h2>
                  <p className="relative mt-2 min-h-14 text-xs leading-7 text-slate-500">
                    {module.description}
                  </p>
                  <div className="relative mt-5 grid grid-cols-3 gap-2">
                    <ModuleMetric label="رکورد" value={module.count} />
                    <ModuleMetric
                      label="اقدام امروز"
                      value={module.actionCount}
                    />
                    <ModuleMetric
                      label="ابزار فعال"
                      value={moduleTools.filter((tool) => tool.enabled).length}
                    />
                  </div>
                </div>
                <CardContent className="border-t border-line/70">
                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <p className="mb-3 flex items-center gap-2 text-[10px] font-semibold text-slate-500">
                        <Layers3 size={13} />
                        قابلیت‌های اصلی
                      </p>
                      <ul className="space-y-2">
                        {meta.features.map((feature) => (
                          <li
                            key={feature}
                            className="flex items-center gap-2 text-[11px] text-slate-400"
                          >
                            <span className="size-1.5 rounded-full bg-mint" />
                            {feature}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="mb-3 flex items-center gap-2 text-[10px] font-semibold text-slate-500">
                        <Wrench size={13} />
                        ابزارهای متصل
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {moduleTools.map((tool) => (
                          <span
                            key={tool.name}
                            className={`rounded-lg border px-2 py-1 text-[9px] ${tool.enabled ? "border-line bg-elevated/50 text-slate-400" : "border-rose-400/10 bg-rose-400/[.04] text-rose-300"}`}
                          >
                            {toolLabels[tool.name] || tool.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <Button
                    className="mt-5 w-full"
                    variant="secondary"
                    onClick={() => onOpen(module.name)}
                  >
                    ورود به ماژول <ArrowLeft size={15} />
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
      <div className="mt-5 flex gap-3 rounded-2xl border border-primary/12 bg-primary/[.035] p-4">
        <ShieldCheck size={18} className="mt-0.5 shrink-0 text-primary-soft" />
        <p className="text-[11px] leading-6 text-slate-500">
          ماژول‌ها فقط از رابط‌های عمومی Core استفاده می‌کنند. تغییر یا حذف یک
          Skill منطق Planner، Executor، حافظه و رجیستری ابزار را آلوده نمی‌کند.
        </p>
      </div>
    </div>
  );
}

function ModuleMetric({ label, value }) {
  return (
    <div className="rounded-xl border border-white/[.045] bg-black/10 p-3">
      <p className="text-lg font-bold text-white">{faNumber(value)}</p>
      <p className="mt-1 text-[9px] text-slate-600">{label}</p>
    </div>
  );
}
