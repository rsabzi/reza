import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryPanel } from "../components/MemoryPanel";
import { ModulesPanel } from "../components/ModulesPanel";
import { PersonalView } from "../components/PersonalView";
import { SalonView } from "../components/SalonView";
import { TaskDetail } from "../components/TaskDetail";
import { ToolsPanel } from "../components/ToolsPanel";

const cases = [
  ["Task Detail", <TaskDetail task={null} />, "یک تسک را انتخاب کنید"],
  [
    "Memory and Playbooks",
    <MemoryPanel memories={[]} playbooks={[]} />,
    "حافظه هنوز خالی است",
  ],
  ["Tools", <ToolsPanel tools={[]} />, "ابزاری ثبت نشده"],
  ["Modules", <ModulesPanel modules={[]} />, "ماژولی فعال نیست"],
  ["Salon", <SalonView salons={[]} dailyPlan={[]} />, "هنوز سالنی ثبت نشده"],
  [
    "Personal",
    <PersonalView projects={[]} reminders={[]} />,
    "هنوز پروژه‌ای ثبت نشده",
  ],
];

test.each(cases)(
  "%s panel renders a stable empty state",
  (_name, component, message) => {
    render(component);
    expect(screen.getByText(message)).toBeInTheDocument();
  },
);

test("memory panel independently handles no playbooks", async () => {
  const user = userEvent.setup();
  render(<MemoryPanel memories={[]} playbooks={[]} />);
  await user.click(screen.getByRole("button", { name: /پلی‌بوک‌ها/ }));
  expect(screen.getByText("پلی‌بوکی بارگذاری نشده")).toBeInTheDocument();
});

test("salon and personal secondary empty sections do not crash", () => {
  const { unmount } = render(<SalonView salons={[]} dailyPlan={[]} />);
  expect(screen.getByText("پیگیری‌ای برای امروز نیست")).toBeInTheDocument();
  unmount();
  render(<PersonalView projects={[]} reminders={[]} />);
  expect(screen.getByText("ددلاین نزدیکی نیست")).toBeInTheDocument();
});
