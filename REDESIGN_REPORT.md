# Dashboard Redesign Report

## هدف

بازطراحی داشبورد از یک نمایش اولیه به یک فضای کاری حرفه‌ای، کاملاً RTL و متصل به API واقعی؛ بدون دکمه نمایشی یا جریان بن‌بست.

## قابلیت‌های افزوده‌شده

### پوسته و ناوبری

- نمای فرماندهی جدید با KPIهای قابل کلیک، تمرکز امروز، نبض سیستم، تصمیم‌های فوری و آخرین حافظه‌ها.
- Sidebar حرفه‌ای دسکتاپ، Bottom Navigation موبایل و منوی کشویی موبایل.
- جستجوی سراسری واقعی میان Task، Salon و PersonalProject با میانبر `Ctrl/Cmd + K`.
- Notification popover واقعی بر اساس Approvalها و deadlineهای نزدیک.
- Toastهای موفقیت/خطا، loading state و refresh بدون reload کامل.
- فونت داخلی Vazirmatn؛ بدون وابستگی به CDN فونت.

### Task Workspace

- ایجاد Task عمومی، سالن یا شخصی.
- ساخت Task تکرارشونده روزانه همراه زمان اجرا.
- جستجو و فیلتر وضعیت.
- مشاهده، ویرایش و حذف Task.
- افزودن Step دستی یا Tool-backed بدون نیاز به Gemini.
- تکمیل Step دستی، حذف Step، اجرای مسیر و اجرای فوری recurrence.
- نمایش ورودی/خروجی Tool و کپی نتیجه.
- تکمیل آخرین Step دستی اکنون وضعیت Task والد را نیز `done` می‌کند.

### Approval Center

- نمایش خوانای ابزار، آرگومان‌ها و Task والد.
- مشاهده Task، تأیید و ادامه Executor، یا رد با Confirm Dialog.
- به‌روزرسانی صف بدون reload و همگام‌سازی Memory/Salon Plan پس از اجرا.

### Memory & Playbooks

- جستجوی معنایی واقعی از `/api/memory/search`.
- فیلتر بر اساس منبع، مشاهده متن کامل و metadata.
- حذف MemoryEntry با تأیید.
- ایجاد، مشاهده و حذف Playbook؛ انتخاب حوزه عمومی/سالن/شخصی.

### Tools & Permissions

- جستجو و فیلتر ابزارها.
- تغییر واقعی `requires_approval` و `enabled`.
- اجرای آزمایشی ابزارهای عمومی و ثبت Task/Step واقعی.

### Salon CRM

- CRUD کامل سالن.
- جستجو و فیلتر وضعیت.
- ورود گروهی CSV یا JSON و گزارش ردیف‌های نامعتبر.
- Detail Dialog و تاریخچه Interaction.
- ثبت Interaction واقعی و ذخیره هم‌زمان در Memory.
- ساخت Outreach Script از فهرست یا برنامه امروز و ارسال به Approval Queue.
- نمایش KPIهای lead/customer و cadence واقعی Playbook.

### Personal/Freelance

- CRUD کامل پروژه.
- جستجو و فیلتر.
- transitionهای مجاز وضعیت با جلوگیری Backend از transition نامعتبر.
- نمایش بودجه، موعد و next action.
- ساخت Proposal واقعی از پروژه و ارسال به Approval Queue.
- فهرست deadlineهای سه روز آینده.

### Settings

- Endpoint جدید و بدون اطلاعات حساس: `GET /api/system/status`.
- نمایش آمادگی API، Scheduler، Gemini، Embedding backend، timezone و SQLite.
- تست اتصال واقعی از خود UI.
- Auto-refresh قابل تنظیم و ذخیره‌شده در localStorage.

## تست‌های خودکار

### Backend

```text
51 passed in 2.32s
```

شامل تست‌های workflow دستی، بازشدن مجدد Task پس از افزودن Step، عدم استفاده مجدد از شناسه‌ها و دو تست status امن سیستم.

### Frontend

```text
Test Files  5 passed (5)
Tests       22 passed (22)
```

تست‌های جدید شامل create سالن، transition پروژه، semantic search، تغییر permission، افزودن Step دستی، تست اتصال تنظیمات، خروج امن از loading هنگام قطع Backend و abort کردن درخواست معلق با پیام قابل فهم است.

## مقاوم‌سازی همگام‌سازی

- تمام درخواست‌های معمول Dashboard حداکثر ۱۲ ثانیه منتظر می‌مانند و سپس abort می‌شوند.
- عملیات واقعاً طولانی مانند Planner، Executor، embedding و tool invocation سقف ۴۵ ثانیه دارند.
- اگر Backend پاسخ ندهد، Dashboard از loading خارج می‌شود، داده‌های قابل دریافت را نشان می‌دهد و Toast خطا می‌سازد.
- پس از ۵ ثانیه، صفحه loading علت احتمالی را توضیح داده و دکمه «تلاش دوباره» نمایش می‌دهد.
- loading اولیه هیچ وابستگی‌ای به Gemini ندارد.
- بررسی Chromium واقعی بعد از اصلاح: بارگذاری کامل در ۲۳۰۶ میلی‌ثانیه، spinner مخفی و صفر خطای Console.

### Build و کیفیت

```text
Prettier: all files formatted
Vite production build: success
npm audit: 0 vulnerabilities
Ruff: all checks passed
```

## بررسی مرورگر واقعی

Chromium headless روی نسخه زنده اجرا شد و تمام صفحات زیر باز شدند:

```json
{
  "tasks": "صندوق کارهای هوشمند",
  "approvals": "مرکز تصمیم و تأیید",
  "memory": "حافظه و دانش ماندگار",
  "tools": "ابزارها و مرز اختیار",
  "modules": "مهارت‌های متصل به هسته",
  "salon": "رشد و ارتباط با سالن‌ها",
  "personal": "پروژه‌ها و کار فریلنس",
  "settings": "تنظیمات و وضعیت سیستم",
  "consoleErrors": []
}
```

### E2E واقعی Task دستی

```json
{
  "createdTask": 5,
  "manualStepCompleted": true,
  "taskDeleted": true,
  "consoleErrors": []
}
```

### E2E واقعی Approval/Executor

```json
{
  "stepStatus": "done",
  "result": {"value": "اجرا پس از تأیید"},
  "queueUpdatedWithoutReload": true,
  "consoleErrors": []
}
```

### موبایل

```json
{
  "innerWidth": 390,
  "scrollWidth": 390,
  "mobileNav": true,
  "errors": []
}
```

هیچ overflow افقی در عرض 390px وجود ندارد.

## تصاویر واقعی خروجی

- `docs/screenshots/dashboard-preview.png` — نمای فرماندهی دسکتاپ
- `docs/screenshots/dashboard-tasks.png` — فضای Task
- `docs/screenshots/dashboard-salons.png` — CRM سالن
- `docs/screenshots/dashboard-settings.png` — تنظیمات سیستم
- `docs/screenshots/dashboard-mobile.png` — نمای موبایل

## حذف بن‌بست اتصال Preview

پس از مشاهده اینکه Backend و Vite هر دو در داخل Sandbox سالم‌اند اما درخواست مرورگر Preview گاهی در proxy معلق می‌ماند، معماری اجرای محلی تغییر کرد:

- Vite فقط برای توسعه و build استفاده می‌شود.
- FastAPI فایل‌های build‌شده React و تمام `/api`ها را از یک process، یک origin و یک پورت سرو می‌کند.
- `start_app.sh` و `start_app.bat` اکنون ابتدا build می‌گیرند و سپس فقط سرویس یکپارچه را اجرا می‌کنند.
- `setup` نیز build تولیدی را آماده می‌کند.
- بررسی واقعی سرویس یکپارچه: صفحه، asset جاوااسکریپت، API و Swagger همگی از Uvicorn روی پورت 3000 پاسخ 200 دادند.
- بارگذاری Chromium پس از حذف proxy: **755ms**، spinner مخفی و صفر خطای Console.

## اصلاح منوی موبایل و مدیریت کلید Gemini

- Sidebar به سه ناحیه مستقل تبدیل شد: Header ثابت، navigation اسکرول‌شونده با `min-height: 0` و `overflow-y: auto`، و Footer ثابت.
- هنگام باز بودن Sidebar، Bottom Navigation پنهان می‌شود و دیگر از سمت چپ روی منو دیده نمی‌شود.
- بررسی واقعی در viewport برابر `489×659`: ارتفاع ناحیه 421px، محتوای 443px، scrollTop تا 22px و صفر overflow افقی/خطای Console.
- Endpointهای `GET/PUT/DELETE /api/settings/gemini` و `POST /api/settings/gemini/test` اضافه شدند.
- کلید ابتدا بدون تولید محتوا با Google Gen AI Model API اعتبارسنجی، سپس با Fernet رمز و در SQLite ذخیره می‌شود.
- کلید رمزگشایی جداگانه با permission `0600` نگه‌داری می‌شود؛ raw key در status، log یا پاسخ Frontend بازگردانده نمی‌شود.
- Dashboard امکان ثبت، جایگزینی، تست و حذف کلید را دارد؛ ویرایش دستی `.env` دیگر لازم نیست.
- SDK به `google-genai 2.20.0` و embedding متنی به `gemini-embedding-001` با خروجی سازگار 128بعدی ارتقا یافت.
- چهار تست Backend برای encryption/validation/removal/no-leak و دو تست Frontend برای ذخیره کلید و منوی موبایل افزوده شد.

## محدودیت خارجی

برای اجرای واقعی Planner همچنان یک کلید معتبر لازم است، اما اکنون کلید مستقیماً از صفحه تنظیمات وارد و مدیریت می‌شود. بدون کلید، تمام CRUDها، workflow دستی، Scheduler، Approval/Executor، ابزارهای deterministic و embedding محلی فعال‌اند.
