import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

function response(body, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

test("all-failed sync shows diagnostics with section names and reasons", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(
    new TypeError("network down"),
  );
  render(<App />);
  await waitFor(() =>
    expect(screen.getByTestId("load-diagnostics")).toBeInTheDocument(),
  );
  const panel = screen.getByTestId("load-diagnostics");
  expect(
    within(panel).getByText(/۱۱ بخش از داشبورد بارگذاری نشد/),
  ).toBeInTheDocument();
  expect(within(panel).getByText(/تسک‌ها/)).toBeInTheDocument();
  expect(within(panel).getByText(/ارتباط مرورگر با سرور/)).toBeInTheDocument();
});

test("diagnostics retry button refetches the failed sections", async () => {
  const user = userEvent.setup();
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockRejectedValue(new TypeError("network down"));
  render(<App />);
  await waitFor(() =>
    expect(screen.getByTestId("load-diagnostics")).toBeInTheDocument(),
  );
  const callsBefore = fetchMock.mock.calls.length;
  await user.click(
    within(screen.getByTestId("load-diagnostics")).getByRole("button", {
      name: /تلاش دوباره/,
    }),
  );
  await waitFor(
    () => expect(fetchMock.mock.calls.length).toBeGreaterThan(callsBefore),
    { timeout: 4000 },
  );
});

test("partial failures list only the broken sections", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    const key = String(url);
    if (key.includes("/api/tasks"))
      return Promise.reject(new TypeError("tasks failed"));
    if (key.includes("/api/system/status"))
      return response({ api_ready: true, scheduler_running: true });
    return response([]);
  });
  render(<App />);
  await waitFor(() =>
    expect(screen.getByTestId("load-diagnostics")).toBeInTheDocument(),
  );
  const panel = screen.getByTestId("load-diagnostics");
  expect(
    within(panel).getByText(/۱ بخش از داشبورد بارگذاری نشد/),
  ).toBeInTheDocument();
  expect(
    within(panel).getByText(/ارتباط با هسته همراه برقرار نشد/),
  ).toBeInTheDocument();
});
