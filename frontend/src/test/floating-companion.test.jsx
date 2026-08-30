import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FloatingCompanion } from "../components/FloatingCompanion";

function response(body, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

function mockApi(routes) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation((url, options = {}) => {
      const key = `${options.method || "GET"} ${url}`;
      for (const [pattern, handler] of routes) {
        if (typeof pattern === "string" && key === pattern)
          return handler(url, options);
        if (pattern instanceof RegExp && pattern.test(key))
          return handler(url, options);
      }
      return response([]);
    });
}

const system = {
  gemini_configured: true,
  reasoning_model: "gemini-3.7-flash",
  timezone: "Asia/Tehran",
};

test("launcher opens the floating companion", async () => {
  const onOpenChange = vi.fn();
  mockApi([["GET /api/assistant/conversations", () => response([])]]);
  render(
    <FloatingCompanion
      open={false}
      onOpenChange={onOpenChange}
      system={system}
    />,
  );
  const launcher = screen.getByTestId("companion-launcher");
  await userEvent.click(launcher);
  expect(onOpenChange).toHaveBeenCalledWith(true);
});

test("collapse button minimizes the docked companion to launcher", async () => {
  const onOpenChange = vi.fn();
  mockApi([["GET /api/assistant/conversations", () => response([])]]);
  render(
    <FloatingCompanion
      open={true}
      onOpenChange={onOpenChange}
      system={system}
    />,
  );
  await waitFor(() =>
    expect(screen.getByTestId("floating-companion")).toBeInTheDocument(),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "جمع کردن همراه" }),
  );
  expect(onOpenChange).toHaveBeenCalledWith(false);
});

test("stop button aborts generation, keeps draft and marks stopped message", async () => {
  const user = userEvent.setup();
  mockApi([
    ["GET /api/assistant/conversations", () => response([])],
    [
      "POST /api/assistant/chat",
      (_url, options) =>
        new Promise((_resolve, reject) => {
          options.signal?.addEventListener("abort", () => {
            const error = new Error("Aborted");
            error.name = "AbortError";
            reject(error);
          });
        }),
    ],
  ]);
  render(
    <FloatingCompanion open={true} onOpenChange={vi.fn()} system={system} />,
  );
  const textarea = await screen.findByLabelText("پیام به همراه");
  await user.type(textarea, "یک گزارش کامل از امروز بساز");
  await user.keyboard("{Enter}");

  await waitFor(() =>
    expect(screen.getByTestId("typing-indicator")).toBeInTheDocument(),
  );
  await user.click(screen.getByRole("button", { name: /توقف/ }));

  await waitFor(() =>
    expect(screen.getByText(/تولید پاسخ متوقف شد/)).toBeInTheDocument(),
  );
  expect(screen.queryByTestId("chat-error")).not.toBeInTheDocument();
  expect(screen.getByLabelText("پیام به همراه")).toHaveValue(
    "یک گزارش کامل از امروز بساز",
  );
  expect(screen.getByTestId("message-user")).toBeInTheDocument();
});

test("assistant messages expose a copy button that copies the content", async () => {
  const user = userEvent.setup();
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
  const chatResponse = {
    conversation_id: 4,
    model: "gemini-3.7-flash",
    message: {
      id: 10,
      role: "assistant",
      content: "تسک جدید **ثبت شد** و شناسه آن ۱۲ است.",
      actions: [],
      created_at: "2026-08-30T08:00:00Z",
    },
    needs_approval: false,
  };
  mockApi([
    ["GET /api/assistant/conversations", () => response([])],
    ["POST /api/assistant/chat", () => response(chatResponse)],
  ]);
  render(
    <FloatingCompanion open={true} onOpenChange={vi.fn()} system={system} />,
  );
  const textarea = await screen.findByLabelText("پیام به همراه");
  await user.type(textarea, "یک تسک بساز");
  await user.keyboard("{Enter}");

  await waitFor(() =>
    expect(
      screen.getByText(/تسک جدید/, { exact: false }),
    ).toBeInTheDocument(),
  );
  const copyButton = screen.getByRole("button", { name: "کپی پاسخ" });
  await user.click(copyButton);
  await waitFor(() =>
    expect(writeText).toHaveBeenCalledWith(
      "تسک جدید **ثبت شد** و شناسه آن ۱۲ است.",
    ),
  );
});
