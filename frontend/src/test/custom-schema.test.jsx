import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CustomSchemaPanel } from "../components/CustomSchemaPanel";
import { SettingsPanel } from "../components/SettingsPanel";

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
        if (typeof pattern === "string" && key === pattern) return handler();
        if (pattern instanceof RegExp && pattern.test(key)) return handler();
      }
      return response([]);
    });
}

test("custom schema panel shows empty state with agent guidance", async () => {
  mockApi([
    ["GET /api/custom-schema", () => response({ tables: [], views: [] })],
  ]);
  render(<CustomSchemaPanel />);
  await waitFor(() =>
    expect(
      screen.getByText(/هنوز جدول یا نمای سفارشی‌ای نساخته‌اید/),
    ).toBeInTheDocument(),
  );
  expect(screen.getByText(/custom_leads/)).toBeInTheDocument();
  expect(screen.getByText(/مرکز تأیید/)).toBeInTheDocument();
});

test("custom schema panel lists tables/views and previews rows", async () => {
  const user = userEvent.setup();
  mockApi([
    [
      "GET /api/custom-schema",
      () =>
        response({
          tables: [
            {
              id: 1,
              name: "custom_leads",
              columns: [
                { name: "name", type: "text" },
                { name: "score", type: "integer", primary_key: false },
              ],
              purpose: "سرنخ‌ها",
            },
          ],
          views: [
            {
              id: 1,
              name: "report_active_salons",
              source: "salons",
              columns: ["id", "name"],
              purpose: null,
            },
          ],
        }),
    ],
    [
      "GET /api/custom-schema/custom_table/custom_leads/rows?limit=50",
      () =>
        response({
          kind: "custom_table",
          name: "custom_leads",
          count: 1,
          rows: [{ name: "آفتاب", score: 9 }],
        }),
    ],
  ]);
  render(<CustomSchemaPanel />);
  await waitFor(() =>
    expect(screen.getByText("custom_leads")).toBeInTheDocument(),
  );
  expect(screen.getByText("report_active_salons")).toBeInTheDocument();
  expect(screen.getByText(/score:integer/)).toBeInTheDocument();

  await user.click(screen.getAllByRole("button", { name: /پیش‌نمایش/ })[0]);
  await waitFor(() =>
    expect(screen.getByTestId("custom-schema-preview")).toBeInTheDocument(),
  );
  expect(screen.getByText("آفتاب")).toBeInTheDocument();
  expect(screen.getByText("9")).toBeInTheDocument();
});

test("custom schema panel delete calls API and refreshes list", async () => {
  const user = userEvent.setup();
  let schemaCalls = 0;
  const fetchMock = mockApi([
    [
      "GET /api/custom-schema",
      () => {
        schemaCalls += 1;
        return response(
          schemaCalls === 1
            ? {
                tables: [
                  { id: 7, name: "custom_x", columns: [], purpose: null },
                ],
                views: [],
              }
            : { tables: [], views: [] },
        );
      },
    ],
    [
      "DELETE /api/custom-schema/custom_table/custom_x",
      () => response(null, 204),
    ],
  ]);
  render(<CustomSchemaPanel notify={vi.fn()} />);
  await waitFor(() => expect(screen.getByText("custom_x")).toBeInTheDocument());
  await user.click(screen.getByRole("button", { name: "حذف custom_x" }));
  await user.click(screen.getByRole("button", { name: /^حذف$/ }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/custom-schema/custom_table/custom_x",
      expect.objectContaining({ method: "DELETE" }),
    ),
  );
  await waitFor(() =>
    expect(
      screen.getByText(/هنوز جدول یا نمای سفارشی‌ای نساخته‌اید/),
    ).toBeInTheDocument(),
  );
});

test("companion action card labels custom schema tools", async () => {
  // SettingsPanel renders the CustomSchemaPanel sub-section (regression guard).
  mockApi([
    [
      "GET /api/settings/telegram",
      () => response({ configured: false, source: "none", hint: null }),
    ],
    ["GET /api/contacts", () => response([])],
    ["GET /api/outbound-messages", () => response([])],
    ["GET /api/custom-schema", () => response({ tables: [], views: [] })],
  ]);
  render(
    <SettingsPanel
      status={{
        supported_models: ["gemini-3.7-flash"],
        default_model: "gemini-3.7-flash",
      }}
      onStatusChanged={vi.fn()}
      notify={vi.fn()}
    />,
  );
  await waitFor(() =>
    expect(screen.getByTestId("custom-schema-panel")).toBeInTheDocument(),
  );
});
