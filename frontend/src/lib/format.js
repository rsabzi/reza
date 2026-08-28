export function faNumber(value) {
  return Number(value || 0).toLocaleString("fa-IR");
}

export function faDate(value, options = {}) {
  if (!value) return "—";
  const date =
    value instanceof Date
      ? value
      : new Date(value.length === 10 ? `${value}T12:00:00` : value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...options,
  }).format(date);
}

export function relativeDate(value) {
  if (!value) return "بدون سابقه";
  const date = new Date(value);
  const days = Math.round((date.getTime() - Date.now()) / 86400000);
  if (days === 0) return "امروز";
  if (days === -1) return "دیروز";
  if (days === 1) return "فردا";
  return days < 0
    ? `${faNumber(Math.abs(days))} روز قبل`
    : `${faNumber(days)} روز دیگر`;
}

export function truncate(value, length = 90) {
  if (!value) return "";
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

export const toolLabels = {
  echo: "بازگرداندن داده",
  generate_outreach_script: "ساخت متن معرفی سالن",
  log_salon_interaction: "ثبت تعامل سالن",
  daily_salon_plan: "برنامه روزانه سالن‌ها",
  draft_project_proposal: "پیش‌نویس پروپوزال",
  daily_personal_reminder: "یادآوری پروژه‌ها",
  delete_application_record: "حذف رکورد",
  send_telegram_message: "ارسال پیام تلگرام",
  prepare_salon_outreach: "آماده‌سازی متن پیگیری سالن",
  prepare_project_proposal: "آماده‌سازی پروپوزال",
  prepare_delete: "بررسی حذف",
  create_salon: "افزودن سالن",
  create_task: "ساخت تسک",
  create_personal_project: "ساخت پروژه",
  create_playbook: "ساخت پلی‌بوک",
  set_tool_policy: "تغییر سیاست ابزار",
  set_model_preference: "انتخاب مدل",
  set_default_reminder_window: "تنظیم بازه یادآوری",
  update_salon: "ویرایش سالن",
  update_task: "ویرایش تسک",
  update_personal_project: "ویرایش پروژه",
  schedule_task: "زمان‌بندی تسک",
  add_task_step: "افزودن مرحله تسک",
  run_task: "اجرای تسک",
  get_current_state: "وضعیت فعلی",
  get_task_details: "جزئیات تسک",
  list_due_tasks: "تسک‌های فعال",
  get_salon_details: "جزئیات سالن",
  get_daily_salon_plan: "برنامه سالن‌ها",
  get_project_details: "جزئیات پروژه",
  get_personal_reminders: "یادآوری پروژه‌ها",
  search_memory: "جستجوی حافظه",
  list_tools_and_policies: "ابزارها و سیاست‌ها",
  summarize_recent_results: "خلاصه نتایج اخیر",
  create_custom_table: "ساخت جدول سفارشی",
  prepare_report_view: "آماده‌سازی نمای گزارش",
  list_custom_schema: "گزارش‌های سفارشی",
};

export const sourceLabels = {
  playbook: "پلی‌بوک",
  task_result: "نتیجه تسک",
  salon_interaction: "تعامل سالن",
};
