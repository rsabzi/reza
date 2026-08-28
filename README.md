# همراه — هسته دستیار هوشمند شخصی

یک دستیار لوکال و تک‌کاربره با حافظه بلندمدت، برنامه‌ریز Gemini، لایه تأیید اقدام‌ها، زمان‌بندی روزانه و دو Skill مستقل برای بازاریابی سالن‌ها و مدیریت پروژه‌های شخصی/فریلنس.

## قابلیت‌ها

- دریافت تسک طبیعی، شکستن آن به قدم‌ها و اجرای ترتیبی ابزارها
- توقف قطعی پیش از ابزارهای نیازمند تأیید و ادامه خودکار پس از تأیید
- ثبت تمام فراخوانی‌های AI، شامل تلاش‌های ناموفق و retry
- حافظه برداری بلندمدت و جست‌وجوی cosine
- بارگذاری و chunk کردن پلی‌بوک‌ها
- ذخیره خودکار نتیجه قدم‌های تکمیل‌شده در حافظه
- اجرای روزانه تسک‌های تکرارشونده با APScheduler
- ماژول سالن: Bulk Import، تعامل‌ها، اسکریپت ارتباطی و cadence طبق پلی‌بوک
- ماژول شخصی: پروژه‌ها، transition وضعیت، پروپوزال و یادآوری سه‌روزه
- داشبورد حرفه‌ای فارسی، تیره، واکنش‌گرا و کاملاً RTL با فونت Vazirmatn داخلی
- نمای فرماندهی، جستجوی سراسری، اعلان‌ها، Toast، تنظیم Auto-refresh و وضعیت واقعی سرویس‌ها
- مدیریت واقعی Task/Step شامل ویرایش، حذف، قدم دستی، اجرای مسیر و اجرای فوری تسک تکرارشونده
- مدیریت کامل سالن شامل CRUD، ورود گروهی CSV/JSON، تاریخچه تعامل و ساخت متن معرفی
- مدیریت کامل پروژه شامل CRUD، transition معتبر وضعیت و ساخت پروپوزال تأییدمحور
- جستجوی معنایی و حذف حافظه، مدیریت پلی‌بوک و اجرای آزمایشی ابزارهای عمومی
- بدون لاگین؛ مناسب یک کاربر روی دستگاه محلی

## شروع سریع

### Linux / macOS

```bash
./setup.sh
./start_app.sh
```

### Windows

```bat
setup.bat
start_app.bat
```

سپس باز کنید:

- داشبورد: <http://127.0.0.1:8000>
- مستندات تعاملی API: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/api/health>

Dashboard و API عمداً از یک process، یک origin و یک پورت سرو می‌شوند؛ بنابراین مرورگر به Vite proxy یا Backend جداگانه وابسته نیست.

برای اجرای خودکار در ورود Windows، راهنمای [`docs/WINDOWS_STARTUP.md`](docs/WINDOWS_STARTUP.md) را ببینید.

## تنظیم Gemini

روش پیشنهادی نیازی به ویرایش Backend ندارد:

1. در Dashboard وارد **تنظیمات و سیستم ← اتصال امن Gemini** شوید.
2. یک Auth key جدید از [Google AI Studio](https://aistudio.google.com/api-keys) بسازید.
3. کلید را وارد و «اعتبارسنجی و ذخیره امن» را بزنید.

Backend ابتدا کلید را مستقیماً با Google بررسی می‌کند؛ فقط در صورت موفقیت آن را با Fernet رمز کرده و در SQLite ذخیره می‌کند. کلید رمزگشایی در فایل محلی با permission `0600` قرار می‌گیرد و مقدار خام هیچ‌وقت در status، log یا پاسخ Frontend برگردانده نمی‌شود.

برای سازگاری با نصب‌های قبلی، متغیر محیطی همچنان fallback است:

```dotenv
GEMINI_API_KEY=your-key-here
EMBEDDING_BACKEND=auto
AGENT_TIMEZONE=Asia/Tehran
```

رفتار embedding:

| مقدار | رفتار |
|---|---|
| `auto` | در حضور کلید از مدل متنی فعلی `gemini-embedding-001` با بردار ۱۲۸بعدی سازگار، و در غیر این صورت از بردار محلی deterministic استفاده می‌کند |
| `gemini` | Gemini را اجباری می‌کند و در نبود/خطای کلید پاسخ شفاف 502 می‌دهد |
| `local` | کاملاً آفلاین، سریع و مناسب تست؛ کیفیت معنایی محدودتر از Gemini |

استدلال و برنامه‌ریزی همیشه با `gemini-2.5-flash` انجام می‌شود و بدون کلید با خطای کنترل‌شده متوقف می‌شود؛ خروجی ساختگی تولید نمی‌شود.

## اجرای تست‌ها

Backend:

```bash
EMBEDDING_BACKEND=local .venv/bin/python -m pytest -v
```

Frontend:

```bash
npm test --prefix frontend
npm run build --prefix frontend
npm audit --prefix frontend
```

آخرین اجرای ثبت‌شده: **۵۱ تست Backend + ۲۲ تست Frontend، همگی پاس؛ Build موفق؛ صفر آسیب‌پذیری npm**. علاوه بر تست‌های خودکار، تمام ۹ نمای اصلی در Chromium واقعی بازبینی شده‌اند و جریان ساخت تسک دستی و تأیید/ادامه Executor از داخل مرورگر به‌صورت end-to-end اجرا شده است. جزئیات فازها در `PHASE_1_REPORT.md` تا `PHASE_9_REPORT.md` و گزارش بازطراحی در `REDESIGN_REPORT.md` موجود است.

## پیش‌نمایش رابط کاربری

![نمای فرماندهی داشبورد](docs/screenshots/dashboard-preview.png)

تصاویر Task Workspace، CRM سالن، تنظیمات Gemini و نمای موبایل در [`docs/screenshots/`](docs/screenshots/) قرار دارند.

## ساختار پروژه

```text
backend/
  app/
    agent/                 # Planner و Executor عمومی
    memory/                # embedding، chunking و vector store
    tools/registry.py      # رجیستری عمومی و مستقل از ماژول
    services/              # لایه مجوز ابزار
    routes/                # APIهای Core
    modules/
      salon/               # مدل، API، سرویس و ابزار سالن
      personal/            # مدل، API، سرویس و ابزار شخصی
    database.py
    models.py
    schemas.py
    scheduler.py
    main.py
  tests/                   # تست‌های فاز ۱ تا ۷
frontend/
  src/
    components/            # پنل‌ها و UI primitives
    lib/api.js             # کلاینت نسبی /api
    test/                  # Vitest + RTL
setup.sh / setup.bat
start_app.sh / start_app.bat
```

Core هیچ reference اختصاصی به سالن یا پروژه شخصی ندارد؛ ماژول‌ها فقط در composition root (`main.py`) mount می‌شوند.

## APIهای اصلی

| حوزه | Endpointهای مهم |
|---|---|
| Tasks | `POST/GET /api/tasks`, `GET/PATCH/DELETE /api/tasks/{id}` |
| Steps | `POST/GET /api/steps`, `POST /api/steps/{id}/approve`, `.../reject` |
| Agent | `POST /api/tasks/{id}/plan`, `POST /api/tasks/{id}/execute` |
| Tools | `GET /api/tools`, `PATCH /api/tools/{name}`, `POST .../{name}/invoke` |
| Memory | `POST/GET /api/playbooks`, `GET /api/memory`, `GET /api/memory/search` |
| Scheduler | `POST /api/tasks/{id}/run-now`, `POST /api/scheduler/run-due` |
| Salon | `/api/salons`, `/api/salons/import`, `/{id}/interactions`, `/daily-plan` |
| Personal | `/api/personal/projects`, `/api/personal/reminders` |

برای schema دقیق درخواست/پاسخ، Swagger در `/docs` مرجع نهایی است.

## مدل امنیتی تک‌کاربره

- Auth طبق نیاز پروژه وجود ندارد؛ API را مستقیماً روی اینترنت عمومی publish نکنید.
- ابزارهای حساس با policy دیتابیسی `requires_approval` کنترل می‌شوند.
- Executor پس از اولین قدم نیازمند تأیید، هیچ قدم بعدی را اجرا نمی‌کند.
- فایل `.env` و دیتابیس محلی توسط Git نادیده گرفته می‌شوند.
- Frontend فقط URL نسبی `/api` را صدا می‌زند و Vite آن را در سمت سرور proxy می‌کند.

## وضعیت پذیرش خارجی

تمام تست‌ها و بررسی‌های لوکال اجرا شده‌اند. تنها بررسی‌ای که در محیط ساخت قابل انجام نبود، اجرای دستی واقعی Gemini است، چون هیچ کلید Gemini در runner تنظیم نشده بود. این مورد صریح و با فرمان بازآزمایی در [`PHASE_4_REPORT.md`](PHASE_4_REPORT.md) ثبت شده است.
