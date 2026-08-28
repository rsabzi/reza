const API_BASE = import.meta.env.VITE_API_BASE || "/api";

function readableError(body, status) {
  if (!body) return `خطای ${status} در ارتباط با سرور`;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    return body.detail.map((item) => item.msg || "ورودی نامعتبر").join("، ");
  }
  if (body.detail?.message) return body.detail.message;
  return `درخواست با خطای ${status} انجام نشد`;
}

export async function request(path, options = {}) {
  const { timeout = 12000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeout);
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        ...(fetchOptions.body ? { "Content-Type": "application/json" } : {}),
        ...fetchOptions.headers,
      },
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(
        "پاسخ Backend بیش از حد طول کشید. اتصال را بررسی و دوباره تلاش کنید.",
      );
    }
    throw new Error(
      "ارتباط با هسته همراه برقرار نشد. وضعیت سرور را بررسی کنید.",
    );
  } finally {
    window.clearTimeout(timeoutId);
  }

  if (!response.ok) {
    let body = null;
    try {
      body = await response.json();
    } catch {
      // A reverse proxy may return a non-JSON error page.
    }
    throw new Error(readableError(body, response.status));
  }
  if (response.status === 204) return null;
  return response.json();
}

const json = (method, payload, timeout = 12000) => ({
  method,
  body: JSON.stringify(payload),
  timeout,
});

export const api = {
  health: () => request("/health"),
  systemStatus: () => request("/system/status"),
  schedulerStatus: () => request("/scheduler/status"),
  getGeminiSetting: () => request("/settings/gemini"),
  saveGeminiKey: (apiKey) =>
    request("/settings/gemini", json("PUT", { api_key: apiKey }, 45000)),
  getGeminiKeys: () => request("/settings/gemini/keys"),
  addGeminiKey: (apiKey) =>
    request("/settings/gemini/keys", json("PUT", { api_key: apiKey }, 45000)),
  removeGeminiKeySlot: (slot) =>
    request(`/settings/gemini/keys/${slot}`, { method: "DELETE" }),
  setGeminiModel: (model) =>
    request("/settings/gemini/model", json("PUT", { model }, 15000)),
  testGeminiKey: () =>
    request("/settings/gemini/test", { method: "POST", timeout: 45000 }),
  removeGeminiKey: () => request("/settings/gemini", { method: "DELETE" }),

  getTelegramSetting: () => request("/settings/telegram"),
  saveTelegramToken: (botToken) =>
    request("/settings/telegram", json("PUT", { bot_token: botToken }, 30000)),
  testTelegramToken: () =>
    request("/settings/telegram/test", { method: "POST", timeout: 30000 }),
  removeTelegramToken: () =>
    request("/settings/telegram", { method: "DELETE" }),
  getReminderWindow: () => request("/settings/reminder-window"),
  setReminderWindow: (days) =>
    request("/settings/reminder-window", json("PUT", { days })),

  assistantChat: (payload) =>
    request("/assistant/chat", json("POST", payload, 180000)),
  previewTool: (name, args = {}) =>
    request(`/tools/${name}/preview`, json("POST", { arguments: args }, 30000)),
  getDailyPlan: () => request("/daily/plan"),
  setDailySettings: (settings) =>
    request("/daily/settings", json("PUT", settings, 15000)),
  assignDailyDeadlines: () =>
    request("/daily/deadlines/assign", { method: "POST", timeout: 15000 }),
  submitDailyReport: (content) =>
    request("/daily/report", json("POST", { content }, 15000)),
  listDailyReports: (limit = 14) => request(`/daily/reports?limit=${limit}`),
  getNotifications: (limit = 30) => request(`/notifications?limit=${limit}`),
  markNotificationRead: (id) =>
    request(`/notifications/${id}/read`, { method: "POST" }),
  markAllNotificationsRead: () =>
    request("/notifications/read-all", { method: "POST" }),
  listConversations: () => request("/assistant/conversations"),
  createConversation: (title) =>
    request("/assistant/conversations", json("POST", { title })),
  getConversation: (id) => request(`/assistant/conversations/${id}`),
  deleteConversation: (id) =>
    request(`/assistant/conversations/${id}`, { method: "DELETE" }),
  archiveConversation: (id) =>
    request(`/assistant/conversations/${id}/archive`, { method: "POST" }),
  listActionRuns: (conversationId) =>
    request(
      `/assistant/actions${conversationId ? `?conversation_id=${conversationId}` : ""}`,
    ),

  listContacts: () => request("/contacts"),
  createContact: (payload) => request("/contacts", json("POST", payload)),
  updateContact: (id, payload) =>
    request(`/contacts/${id}`, json("PATCH", payload)),
  deleteContact: (id) => request(`/contacts/${id}`, { method: "DELETE" }),

  listCustomSchema: () => request("/custom-schema"),
  createCustomTable: (payload) =>
    request("/custom-schema/tables", json("POST", payload, 45000)),
  createCustomView: (payload) =>
    request("/custom-schema/views", json("POST", payload, 45000)),
  customSchemaRows: (kind, name, limit = 50) =>
    request(
      `/custom-schema/${kind}/${encodeURIComponent(name)}/rows?limit=${limit}`,
    ),
  deleteCustomSchema: (kind, name) => {
    // eslint-disable-next-line no-useless-escape
    return request(`/custom-schema/${kind}/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
  },

  listOutboundMessages: (status) =>
    request(`/outbound-messages${status ? `?status=${status}` : ""}`),
  getOutboundMessage: (id) => request(`/outbound-messages/${id}`),

  listTasks: () => request("/tasks"),
  getTask: (id) => request(`/tasks/${id}`),
  createTask: (payload) => request("/tasks", json("POST", payload)),
  updateTask: (id, payload) => request(`/tasks/${id}`, json("PATCH", payload)),
  deleteTask: (id) => request(`/tasks/${id}`, { method: "DELETE" }),
  planTask: (id) =>
    request(`/tasks/${id}/plan`, { method: "POST", timeout: 45000 }),
  executeTask: (id) =>
    request(`/tasks/${id}/execute`, { method: "POST", timeout: 45000 }),
  runTaskNow: (id) => request(`/tasks/${id}/run-now`, { method: "POST" }),

  listSteps: (taskId) => request(`/steps${taskId ? `?task_id=${taskId}` : ""}`),
  createStep: (payload) => request("/steps", json("POST", payload)),
  updateStep: (id, payload) => request(`/steps/${id}`, json("PATCH", payload)),
  deleteStep: (id) => request(`/steps/${id}`, { method: "DELETE" }),
  listApprovals: () => request("/steps?step_status=needs_approval"),
  approveStep: (id) => request(`/steps/${id}/approve`, { method: "POST" }),
  rejectStep: (id) => request(`/steps/${id}/reject`, { method: "POST" }),

  listMemory: (query = "") => request(`/memory?limit=100${query}`),
  searchMemory: (query, limit = 20) =>
    request(`/memory/search?q=${encodeURIComponent(query)}&limit=${limit}`, {
      timeout: 45000,
    }),
  deleteMemory: (id) => request(`/memory/${id}`, { method: "DELETE" }),
  listPlaybooks: () => request("/playbooks"),
  uploadPlaybook: (payload) =>
    request("/playbooks", json("POST", payload, 45000)),
  deletePlaybook: (id) => request(`/playbooks/${id}`, { method: "DELETE" }),

  listTools: () => request("/tools"),
  updateTool: (name, payload) =>
    request(`/tools/${name}`, json("PATCH", payload)),
  invokeTool: (name, payload) =>
    request(`/tools/${name}/invoke`, json("POST", payload, 45000)),

  listSalons: () => request("/salons"),
  getSalon: (id) => request(`/salons/${id}`),
  createSalon: (payload) => request("/salons", json("POST", payload)),
  updateSalon: (id, payload) =>
    request(`/salons/${id}`, json("PATCH", payload)),
  deleteSalon: (id) => request(`/salons/${id}`, { method: "DELETE" }),
  importSalons: (salons) => request("/salons/import", json("POST", { salons })),
  dailySalonPlan: (cadenceDays) =>
    request(
      `/salons/daily-plan${cadenceDays ? `?cadence_days=${cadenceDays}` : ""}`,
    ),
  listSalonInteractions: (id) => request(`/salons/${id}/interactions`),
  logSalonInteraction: (id, payload) =>
    request(`/salons/${id}/interactions`, json("POST", payload, 45000)),

  listProjects: () => request("/personal/projects"),
  getProject: (id) => request(`/personal/projects/${id}`),
  createProject: (payload) =>
    request("/personal/projects", json("POST", payload)),
  updateProject: (id, payload) =>
    request(`/personal/projects/${id}`, json("PATCH", payload)),
  deleteProject: (id) =>
    request(`/personal/projects/${id}`, { method: "DELETE" }),
  reminders: (withinDays = 3) =>
    request(`/personal/reminders?within_days=${withinDays}`),

  listAILogs: (taskId) =>
    request(`/ai-logs${taskId ? `?task_id=${taskId}` : ""}`),
};
