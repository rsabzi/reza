import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryPanel } from "../components/MemoryPanel";
import { PersonalView } from "../components/PersonalView";
import { SalonView } from "../components/SalonView";
import { SettingsPanel } from "../components/SettingsPanel";
import { TaskDetail } from "../components/TaskDetail";
import { ToolsPanel } from "../components/ToolsPanel";

function response(body, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

test("Salon panel creates a real salon through the API", async () => {
  const user = userEvent.setup();
  const created = {
    id: 8,
    name: "سالن تست",
    phone: "09121111111",
    city: "تهران",
    status: "lead",
    tags: [],
  };
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockReturnValue(response(created, 201));
  const onChanged = vi.fn().mockResolvedValue(undefined);
  const onCreated = vi.fn();
  render(
    <SalonView
      salons={[]}
      dailyPlan={[]}
      onChanged={onChanged}
      onCreated={onCreated}
    />,
  );

  await user.click(screen.getByRole("button", { name: "سالن جدید" }));
  await user.type(screen.getByLabelText("نام سالن"), created.name);
  await user.type(screen.getByLabelText("تلفن سالن"), created.phone);
  await user.click(screen.getByRole("button", { name: "ثبت سالن" }));

  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(created));
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/salons",
    expect.objectContaining({ method: "POST" }),
  );
  expect(onChanged).toHaveBeenCalled();
});

test("Personal panel performs a valid status transition through the API", async () => {
  const user = userEvent.setup();
  const project = {
    id: 4,
    title: "پروژه نمونه",
    client_name: "آوا",
    description: null,
    status: "lead",
    due_date: null,
    budget: null,
    next_action: null,
  };
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockReturnValue(response({ ...project, status: "active" }));
  const onChanged = vi.fn().mockResolvedValue(undefined);
  render(
    <PersonalView projects={[project]} reminders={[]} onChanged={onChanged} />,
  );

  await user.selectOptions(
    screen.getByLabelText("تغییر وضعیت پروژه نمونه"),
    "active",
  );

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/personal/projects/4",
      expect.objectContaining({ method: "PATCH" }),
    ),
  );
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
    status: "active",
  });
  expect(onChanged).toHaveBeenCalled();
});

test("Memory panel performs semantic search and displays API results", async () => {
  const user = userEvent.setup();
  const original = {
    id: 1,
    content: "متن اولیه",
    source: "playbook",
    created_at: "2026-08-20T10:00:00Z",
    entry_metadata: {},
  };
  const result = {
    ...original,
    id: 2,
    content: "پیگیری سالن آریانا بعد از هفت روز",
    score: 0.91,
  };
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockReturnValue(response([result]));
  render(<MemoryPanel memories={[original]} playbooks={[]} />);

  await user.type(screen.getByLabelText("جستجوی معنایی حافظه"), "پیگیری سالن");
  await user.click(screen.getByRole("button", { name: "جستجو" }));

  await waitFor(() =>
    expect(screen.getByText(/پیگیری سالن آریانا/)).toBeInTheDocument(),
  );
  expect(fetchMock.mock.calls[0][0]).toContain("/api/memory/search?q=");
});

test("Tools panel persists approval policy changes", async () => {
  const user = userEvent.setup();
  const tool = {
    name: "echo",
    description: "Return value",
    enabled: true,
    requires_approval: false,
  };
  const onChange = vi
    .fn()
    .mockResolvedValue({ ...tool, requires_approval: true });
  render(<ToolsPanel tools={[tool]} onChange={onChange} />);

  await user.click(screen.getByRole("switch", { name: "مجوز echo" }));

  await waitFor(() =>
    expect(onChange).toHaveBeenCalledWith(tool, { requires_approval: true }),
  );
});

test("Task detail can add a manual step without Gemini", async () => {
  const user = userEvent.setup();
  const task = {
    id: 11,
    title: "تسک دستی",
    description: null,
    status: "pending",
    module_name: null,
    recurrence_rule: null,
    steps: [],
    created_at: "2026-08-20T10:00:00Z",
    updated_at: "2026-08-20T10:00:00Z",
  };
  const createdStep = {
    id: 30,
    task_id: 11,
    title: "بررسی انسانی",
    position: 0,
    status: "pending",
    tool_name: null,
    arguments: {},
  };
  const freshTask = { ...task, steps: [createdStep] };
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockReturnValueOnce(response(createdStep, 201))
    .mockReturnValueOnce(response(freshTask));
  const onChanged = vi.fn();
  render(<TaskDetail task={task} tools={[]} onChanged={onChanged} />);

  await user.click(screen.getByRole("button", { name: "افزودن قدم دستی" }));
  const dialog = screen.getByRole("dialog");
  await user.type(
    within(dialog).getByLabelText("عنوان قدم"),
    createdStep.title,
  );
  await user.click(within(dialog).getByRole("button", { name: "افزودن قدم" }));

  await waitFor(() => expect(onChanged).toHaveBeenCalledWith(freshTask));
  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "/api/steps",
    expect.objectContaining({ method: "POST" }),
  );
});

test("Settings panel validates and stores Gemini key through Backend", async () => {
  const user = userEvent.setup();
  const rawKey = "dashboard-auth-key-that-stays-server-side-9876";
  const subPanels = {
    "/api/settings/telegram": { configured: false, source: "none", hint: null },
    "/api/contacts": [],
    "/api/outbound-messages": [],
    "/api/custom-schema": { tables: [], views: [] },
  };
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    if (url in subPanels) return response(subPanels[url]);
    return response({
      configured: true,
      source: "dashboard",
      hint: "••••9876",
      validated: true,
      model: "gemini-3.7-flash",
      models: ["gemini-3.7-flash"],
    });
  });
  const onStatusChanged = vi.fn().mockResolvedValue(undefined);
  const notify = vi.fn();
  render(
    <SettingsPanel
      status={{ api_ready: true, gemini_configured: false }}
      onStatusChanged={onStatusChanged}
      notify={notify}
    />,
  );

  await user.type(screen.getByLabelText("کلید API جمنای"), rawKey);
  await user.click(
    screen.getByRole("button", { name: /اعتبارسنجی و ذخیره امن/ }),
  );

  await waitFor(() => expect(onStatusChanged).toHaveBeenCalled());
  const geminiCall = fetchMock.mock.calls.find(
    (call) => call[0] === "/api/settings/gemini",
  );
  expect(geminiCall).toBeDefined();
  expect(geminiCall[1]).toEqual(expect.objectContaining({ method: "PUT" }));
  expect(JSON.parse(geminiCall[1].body)).toEqual({ api_key: rawKey });
  expect(screen.getByLabelText("کلید API جمنای")).toHaveValue("");
  expect(notify).toHaveBeenCalledWith(
    "کلید توسط Google تأیید و به‌صورت رمز‌شده ذخیره شد",
    "success",
  );
});

test("Settings panel tests the live API connection", async () => {
  const user = userEvent.setup();
  const notify = vi.fn();
  const responses = {
    "/api/settings/telegram": { configured: false, source: "none", hint: null },
    "/api/contacts": [],
    "/api/outbound-messages": [],
    "/api/custom-schema": { tables: [], views: [] },
    "/api/health": { status: "ok" },
  };
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation((url) => response(responses[url] || {}));
  render(<SettingsPanel status={{ api_ready: true }} notify={notify} />);

  await user.click(screen.getByRole("button", { name: /آزمایش ارتباط واقعی/ }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith("/api/health", expect.any(Object)),
  );
  expect(notify).toHaveBeenCalledWith(
    "ارتباط Dashboard و Agent Core سالم است",
    "success",
  );
});
