import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CompanionPanel } from "../components/CompanionPanel";
import { AssistantConnections } from "../components/AssistantConnections";

function response(body, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

const emptyConversations = [];
const emptyConversation = {
  id: 1,
  title: "گفتگوی جدید",
  status: "active",
  messages: [],
  action_runs: [],
  created_at: "2026-08-28T10:00:00Z",
  updated_at: "2026-08-28T10:00:00Z",
};

function mockApi(routes) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation((url, options = {}) => {
      const key = `${options.method || "GET"} ${url}`;
      for (const [pattern, handler] of routes) {
        if (typeof pattern === "string" && key === pattern) return handler();
        if (pattern instanceof RegExp && pattern.test(key)) return handler();
      }
      return response([]);
    });
}

test("companion shows greeting and CTA when Gemini key is missing", async () => {
  const onNavigate = vi.fn();
  mockApi([["GET /api/assistant/conversations", () => response([])]]);
  render(
    <CompanionPanel
      system={{
        gemini_configured: false,
        reasoning_model: "",
        timezone: "Asia/Tehran",
      }}
      onNavigate={onNavigate}
    />,
  );

  await waitFor(() =>
    expect(screen.getByText(/سلام، من همراه‌ات هستم/)).toBeInTheDocument(),
  );
  expect(
    screen.getByText(/برای استفاده از همراه، کلید Gemini لازم است/),
  ).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: /رفتن به تنظیمات/ }),
  );
  expect(onNavigate).toHaveBeenCalledWith("settings");
});

test("natural-language command calls chat API and shows action card with record id", async () => {
  const user = userEvent.setup();
  const onChanged = vi.fn().mockResolvedValue(undefined);
  const chatResponse = {
    conversation_id: 12,
    model: "gemini-3.7-flash",
    message: {
      id: 9,
      role: "assistant",
      content: "سالن آفتاب با شناسه ۴۱ اضافه شد.",
      actions: [
        {
          name: "create_salon",
          ok: true,
          needs_approval: false,
          arguments: { name: "سالن آفتاب", phone: "09121234567" },
          result: { salon_id: 41, status: "lead" },
          error: null,
        },
      ],
      created_at: "2026-08-28T10:00:00Z",
    },
    needs_approval: false,
  };
  const fetchMock = mockApi([
    ["GET /api/assistant/conversations", () => response([])],
    ["POST /api/assistant/chat", () => response(chatResponse)],
  ]);
  render(
    <CompanionPanel
      system={{
        gemini_configured: true,
        reasoning_model: "gemini-3.7-flash",
        timezone: "Asia/Tehran",
      }}
      onChanged={onChanged}
    />,
  );

  await waitFor(() =>
    expect(screen.getByText(/سلام، من همراه‌ات هستم/)).toBeInTheDocument(),
  );
  await user.type(
    screen.getByLabelText("پیام به همراه"),
    "یک سالن آفتاب با شماره ۰۹۱۲۱۲۳۴۵۶۷ در تهران اضافه کن",
  );
  await user.keyboard("{Enter}");

  await waitFor(() =>
    expect(
      screen.getByText(/سالن آفتاب با شناسه ۴۱ اضافه شد/),
    ).toBeInTheDocument(),
  );
  expect(screen.getByTestId("action-create_salon")).toBeInTheDocument();
  expect(screen.getByText(/salon_id/)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/assistant/chat",
    expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("سالن آفتاب"),
    }),
  );
  await waitFor(() => expect(onChanged).toHaveBeenCalled());
});

test("Shift+Enter adds a newline without submitting", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi([
    ["GET /api/assistant/conversations", () => response([])],
  ]);
  render(
    <CompanionPanel system={{ gemini_configured: true }} onChanged={vi.fn()} />,
  );
  await waitFor(() =>
    expect(screen.getByText(/سلام، من همراه‌ات هستم/)).toBeInTheDocument(),
  );
  const textarea = screen.getByLabelText("پیام به همراه");
  await user.type(textarea, "خط اول");
  await user.keyboard("{Shift>}{Enter}{/Shift}");
  await user.type(textarea, "خط دوم");
  expect(fetchMock).not.toHaveBeenCalledWith(
    "/api/assistant/chat",
    expect.anything(),
  );
  expect(textarea.value).toContain("\n");
});

test("needs_approval action renders badge and links to approval center", async () => {
  const user = userEvent.setup();
  const onNavigate = vi.fn();
  mockApi([
    ["GET /api/assistant/conversations", () => response([])],
    [
      "POST /api/assistant/chat",
      () =>
        response({
          conversation_id: 3,
          model: "gemini-3.7-flash",
          message: {
            id: 5,
            role: "assistant",
            content: "حذف سالن در انتظار تأیید است.",
            actions: [
              {
                name: "delete_application_record",
                ok: true,
                needs_approval: true,
                arguments: { resource_type: "salon", resource_id: 41 },
                result: null,
                error: null,
                step_id: 77,
              },
            ],
            created_at: "2026-08-28T10:00:00Z",
          },
          needs_approval: true,
        }),
    ],
  ]);
  render(
    <CompanionPanel
      system={{ gemini_configured: true }}
      approvals={1}
      onNavigate={onNavigate}
    />,
  );
  await waitFor(() =>
    expect(screen.getByText(/سلام، من همراه‌ات هستم/)).toBeInTheDocument(),
  );
  await user.type(screen.getByLabelText("پیام به همراه"), "این سالن را حذف کن");
  await user.keyboard("{Enter}");
  await waitFor(() =>
    expect(
      screen.getByText("حذف سالن در انتظار تأیید است."),
    ).toBeInTheDocument(),
  );
  const badge = screen.getByTestId("action-delete_application_record");
  await user.click(
    within(badge).getByRole("button", { name: /نیازمند تأیید/ }),
  );
  expect(onNavigate).toHaveBeenCalledWith("approval");
});

test("conversation new/load/delete flows", async () => {
  const user = userEvent.setup();
  const conversation = {
    ...emptyConversation,
    id: 1,
    title: "گفتگوی قبلی",
    messages: [
      { id: 1, role: "user", content: "سلام", actions: [] },
      {
        id: 2,
        role: "assistant",
        content: "سلام! چه کاری انجام دهم؟",
        actions: [],
      },
    ],
  };
  const fetchMock = mockApi([
    [
      "GET /api/assistant/conversations",
      () =>
        response([
          {
            ...emptyConversation,
            id: 1,
            title: "گفتگوی قبلی",
            message_count: 2,
          },
        ]),
    ],
    ["GET /api/assistant/conversations/1", () => response(conversation)],
    [
      "POST /api/assistant/conversations",
      () => response({ id: 2, title: "گفتگوی جدید", status: "active" }, 201),
    ],
    ["DELETE /api/assistant/conversations/2", () => response(null, 204)],
  ]);
  render(
    <CompanionPanel system={{ gemini_configured: true }} notify={vi.fn()} />,
  );
  await waitFor(() =>
    expect(screen.getByText("گفتگوی قبلی")).toBeInTheDocument(),
  );
  await waitFor(() =>
    expect(screen.getByText("سلام! چه کاری انجام دهم؟")).toBeInTheDocument(),
  );

  await user.click(screen.getByRole("button", { name: /گفتگوی جدید/ }));
  await waitFor(() =>
    expect(screen.getByTestId("conversation-2-row")).toBeInTheDocument(),
  );

  await user.click(screen.getByRole("button", { name: "حذف گفتگو 2" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/assistant/conversations/2",
      expect.objectContaining({ method: "DELETE" }),
    ),
  );
  await waitFor(() =>
    expect(screen.queryByTestId("conversation-2-row")).not.toBeInTheDocument(),
  );
});

test("network timeout leaves loading state and offers retry", async () => {
  const user = userEvent.setup();
  mockApi([
    ["GET /api/assistant/conversations", () => response([])],
    [
      "POST /api/assistant/chat",
      () =>
        Promise.reject(
          new Error(
            "پاسخ Backend بیش از حد طول کشید. اتصال را بررسی و دوباره تلاش کنید.",
          ),
        ),
    ],
  ]);
  render(<CompanionPanel system={{ gemini_configured: true }} />);
  await waitFor(() =>
    expect(screen.getByText(/سلام، من همراه‌ات هستم/)).toBeInTheDocument(),
  );
  await user.type(screen.getByLabelText("پیام به همراه"), "سلام");
  await user.keyboard("{Enter}");
  await waitFor(() =>
    expect(screen.getByTestId("chat-error")).toBeInTheDocument(),
  );
  expect(screen.queryByTestId("typing-indicator")).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /تلاش دوباره/ }),
  ).toBeInTheDocument();
});

test("telegram token flow saves with getMe and shows provider receipt in outbound list", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi([
    [
      "GET /api/settings/telegram",
      () => response({ configured: false, source: "none", hint: null }),
    ],
    ["GET /api/contacts", () => response([])],
    [
      "GET /api/outbound-messages",
      () =>
        response([
          {
            id: 1,
            content: "پیام تست",
            status: "sent",
            provider_message_id: "777",
            provider_response: { ok: true, message_id: "777" },
          },
        ]),
    ],
    [
      "PUT /api/settings/telegram",
      () =>
        response({
          configured: true,
          source: "dashboard",
          hint: "••••KKK",
          validated: true,
        }),
    ],
  ]);
  render(
    <AssistantConnections
      status={{ gemini_configured: true }}
      onStatusChanged={vi.fn().mockResolvedValue(undefined)}
      notify={vi.fn()}
    />,
  );
  const token = "123456789:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKK";
  await user.type(screen.getByLabelText("توکن ربات تلگرام"), token);
  await user.click(
    screen.getByRole("button", { name: /تست با getMe و ذخیره/ }),
  );
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/settings/telegram",
      expect.objectContaining({
        method: "PUT",
        body: expect.stringContaining("AAAbbbCCC"),
      }),
    ),
  );
  await waitFor(() =>
    expect(screen.getByTestId("outbound-status-1")).toHaveTextContent(
      "ارسال شد",
    ),
  );
  expect(screen.getByText(/msg_id: 777/)).toBeInTheDocument();
  const note = screen.getByTestId("telegram-status-note");
  expect(note).toBeInTheDocument();
});

test("Gemini model preference can be changed from settings", async () => {
  const user = userEvent.setup();
  const fetchMock = mockApi([
    [
      "GET /api/settings/telegram",
      () => response({ configured: false, source: "none", hint: null }),
    ],
    ["GET /api/contacts", () => response([])],
    ["GET /api/outbound-messages", () => response([])],
    [
      "PUT /api/settings/gemini/model",
      () =>
        response({
          configured: true,
          source: "dashboard",
          hint: "••••9876",
          validated: true,
          model: "gemini-3.6-flash",
          models: ["gemini-3.7-flash", "gemini-3.6-flash"],
        }),
    ],
  ]);
  render(
    <AssistantConnections
      status={{
        gemini_configured: true,
        reasoning_model: "gemini-3.7-flash",
        default_model: "gemini-3.7-flash",
        supported_models: ["gemini-3.7-flash", "gemini-3.6-flash"],
      }}
      onStatusChanged={vi.fn().mockResolvedValue(undefined)}
      notify={vi.fn()}
    />,
  );
  await user.selectOptions(
    screen.getByLabelText("مدل Gemini"),
    "gemini-3.6-flash",
  );
  await user.click(screen.getByRole("button", { name: /ذخیره مدل/ }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/settings/gemini/model",
      expect.objectContaining({
        method: "PUT",
        body: expect.stringContaining("gemini-3.6-flash"),
      }),
    ),
  );
});
