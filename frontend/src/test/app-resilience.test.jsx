import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { request } from "../lib/api";

test("dashboard leaves loading state when Backend requests fail", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(
    new TypeError("network down"),
  );

  render(<App />);

  await waitFor(() =>
    expect(
      screen.getByText(/امروز روی چه چیزی تمرکز می‌کنیم/),
    ).toBeInTheDocument(),
  );
  expect(screen.queryByText("در حال همگام‌سازی همراه")).not.toBeInTheDocument();
  expect(
    screen.getByText(/بارگذاری ۱۰ بخش با خطا روبه‌رو شد/),
  ).toBeInTheDocument();
});

test("mobile menu has an independent scroll area and hides bottom navigation", async () => {
  const user = userEvent.setup();
  vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    const body = String(url).endsWith("/system/status")
      ? { api_ready: true, scheduler_running: true }
      : [];
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  });
  render(<App />);
  await waitFor(() =>
    expect(
      screen.getByText(/امروز روی چه چیزی تمرکز می‌کنیم/),
    ).toBeInTheDocument(),
  );
  expect(screen.getByTestId("mobile-bottom-nav")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "باز کردن منو" }));

  expect(screen.getByTestId("mobile-menu-scroll-area")).toHaveClass(
    "overflow-y-auto",
    "min-h-0",
  );
  expect(screen.queryByTestId("mobile-bottom-nav")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "بستن منو" }));
  expect(screen.getByTestId("mobile-bottom-nav")).toBeInTheDocument();
});

test("API client aborts a hanging request with a readable timeout", async () => {
  vi.useFakeTimers();
  vi.spyOn(globalThis, "fetch").mockImplementation(
    (_url, options) =>
      new Promise((_resolve, reject) => {
        options.signal.addEventListener("abort", () => {
          const error = new Error("aborted");
          error.name = "AbortError";
          reject(error);
        });
      }),
  );

  const assertion = expect(
    request("/never-responds", { timeout: 25 }),
  ).rejects.toThrow("پاسخ Backend بیش از حد طول کشید");
  await vi.advanceTimersByTimeAsync(25);

  await assertion;
  vi.useRealTimers();
});
