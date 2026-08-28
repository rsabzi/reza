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
};

export const sourceLabels = {
  playbook: "پلی‌بوک",
  task_result: "نتیجه تسک",
  salon_interaction: "تعامل سالن",
};
