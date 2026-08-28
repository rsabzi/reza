# گزارش ارتقای Agentic — «همراه من»

- **Branch:** `arena/01a046a3-reza`
- **PR:** https://github.com/rsabzi/reza/pull/2
- **مبنا:** `aacc744` (Merge PR #1 روی `main`)
- **تاریخ:** 2026-08-28
- **وضعیت:** تمام تست‌های Backend/Frontend، Build، Audit، Lint و Setup بررسی و پاس شدند.

---

## ۱. خلاصه معماری (بعد از ارتقا)

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend (React/Vite + Tailwind)                            │
│   • صفحه پیش‌فرض «همراه من» (CompanionPanel)                 │
│   • Action cards + Badge «نیازمند تأیید» + Retry             │
│   • Settings: مدل Gemini، توکن تلگرام، مخاطبین، پیام‌های خروجی│
│   • بدون Reload کامل بعد از Action (onChanged → loadDashboard)│
└──────────────────────────┬───────────────────────────────────┘
                           │ POST /api/assistant/chat (timeout 90s)
┌──────────────────────────▼───────────────────────────────────┐
│  FastAPI — یک Origin / یک Port (Dashboard + API)             │
│  routes/assistant.py  →  assistant/service.py                │
│     ├─ context.py        ساخت Context واقعی و فشرده          │
│     ├─ dispatcher.py     Allowlist + Pydantic/بایند +        │
│     │                    AgentActionRun (idempotency) +      │
│     │                    Approval (Step تأیید)               │
│     └─ tools.py          Composition Layer (۳۴ ابزار)        │
│  agent/ai_client.py      Gemini Interactions API + Fallback  │
│  services/{secrets,telegram,preferences}.py                  │
│  SQLite: +AgentConversation/+AgentMessage/+AgentActionRun/   │
│          +AppPreference/+ContactEndpoint/+OutboundMessage     │
└──────────────┬──────────────────────────────┬────────────────┘
               │                              │
        Google Gemini                 Telegram Bot API
        (Interactions API)             (getMe / sendMessage)
```

### نکات کلیدی

- **Interactions API:** همه مسیرهای runtime (گفتگو و Planner) از
  `client.aio.interactions.create(..., store=False)` استفاده می‌کنند؛
  پاسخ متنی از `interaction.output_text` و Function Callها از
  `interaction.steps` (فیلتر `step.type == "function_call"`) خوانده می‌شوند.
- **Stateless + محلی:** `store=False`؛ تاریخچه از `AgentMessage` و
  `AgentActionRun` بازسازی و هر round با ساختار رسمی
  `function_result {name, call_id, result:[{type:"text", text}]}` ادامه می‌یابد.
- **Model:** Default = `gemini-3.7-flash` (پایدار فعلی طبق مستندات رسمی).
  Chain fallback: `3.7 → 3.6 → 3.5 → 3.1-flash-lite → 2.5-flash → gemini-flash-latest`.
  404 / «no longer available» ⇒ مدل مرده Retry نمی‌شود؛ Timeout/Rate-limit ⇒
  Backoff (۱، ۲، ۴ ثانیه × حداکثر ۳ تلاش). هر تلاش در `AILog` ثبت می‌شود.
  اعتبارسنجی کلید با Discovery مدل‌ها (مستقل از مدل مرده) و اولین مدل سازگار را برمی‌گرداند.
- **Idempotency/Approval:** `AgentActionRun.provider_call_id` یکتا.
  عملیات حساس («حذف»، «آماده‌سازی خروجی خارجی»، «ارسال واقعی») فقط یک
  `Step` با `status=needs_approval` می‌سازند؛ `POST /api/steps/{id}/approve`
  همان ابزار را **دقیقاً یک‌بار** اجرا می‌کند (و `AgentActionRun` و
  `OutboundMessage` را به‌روز می‌کند). Approve دوباره 409 می‌دهد.
- **Telegram:** توکن فقط Fernet + Master-key با chmod 0600؛ هرگز به Frontend/AILog/Gemini نمی‌رود.
  `send_telegram_message`: `OutboundMessage(needs_approval)` → Approve →
  یک `sendMessage` → فقط با `ok=true` و `result.message_id` ⇐ `sent` + Receipt.
  اگر chat_id/توکن نباشد، ابزار دقیقاً می‌گوید چه چیزی کم است و ارسال را جعل نمی‌کند.
- **امنیت Prompt Injection:** Context و Memory به‌صراحت «فقط داده، نه دستور» علامت‌گذاری
  می‌شوند و قواعد سیستمی در پایان مجدداً تأکید می‌شوند. هیچ ابزار `set_api_key` /
  `read_secret` وجود ندارد و خطاهای Provider قبل از ذخیره Redact می‌شوند.
- **Migration:** فقط جدول‌های جدید اضافه شده‌اند (`create_all` در startup)؛
  داده موجود پاک نمی‌شود.

---

## ۲. فایل‌های تغییرکرده/جدید

### Backend (جدید)
| فایل | نقش |
|---|---|
| `backend/app/agent/ai_client.py` | بازنویسی کامل: Interactions API، Fallback مدل، Backoff، Discovery |
| `backend/app/agent/planner.py` | استفاده از `ChatClient.generate` + `AILog` برای هر تلاش Provider |
| `backend/app/assistant/__init__.py` | Composition root |
| `backend/app/assistant/service.py` | حلقه Tool Calling (۴ round، سقف ۱۲ Action) |
| `backend/app/assistant/dispatcher.py` | اجرای امن/Idempotent + Approval + Redaction |
| `backend/app/assistant/context.py` | Context فشرده و بازسازی History |
| `backend/app/assistant/tools.py` | ۳۴ ابزار (Read/Task/Salon/Personal/Memory/Settings/Telegram) |
| `backend/app/assistant/timeparse.py` | استخراج HH:MM و تاریخ نسبی فارسی |
| `backend/app/assistant/schemas.py` | Schemaهای گفتگو |
| `backend/app/routes/assistant.py` | Chat + Conversation CRUD + Actions |
| `backend/app/routes/contacts.py` | CRUD `contact_endpoints` |
| `backend/app/routes/outbound.py` | Status/Receipt پیام‌های خروجی |
| `backend/app/services/telegram.py` | getMe/sendMessage با Redaction |
| `backend/app/services/preferences.py` | تنظیمات غیرمحرمانه (مدل، پنجره یادآوری) |

### Backend (ویرایش)
`models.py` (۶ جدول جدید)، `tools/registry.py` (schema/declaration)،
`agent/executor.py` (پیوند ActionRun در اجرای پس از تأیید)،
`routes/{settings,system,tasks,agent,memory}.py`، `services/secrets.py`
(توکن تلگرام)، `main.py`، `backend/requirements.txt`.

### Frontend
`src/components/CompanionPanel.jsx` (جدید)،
`src/components/AssistantConnections.jsx` (جدید)،
`src/App.jsx` (Nav + Landing + MobileNav)، `src/lib/api.js`،
`src/lib/format.js`، `src/components/SettingsPanel.jsx`، `src/styles.css`،
`src/test/companion.test.jsx` (جدید)، `src/test/app-resilience.test.jsx`.

### مستندات
`README.md`، `.env.example`، `AGENTIC_UPGRADE_REPORT.md`.

---

## ۳. نتیجه دقیق تست‌ها

```bash
EMBEDDING_BACKEND=local .venv/bin/python -m pytest -v
# 72 passed (51 قبلی + 21 جدید/به‌روز)
```
پوشش‌های جدید (خلاصه):
- Interactions API و مدل جدید در Planner/Chat
- 404 مدل ⇒ رفتن به Candidate بعدی **بدون Retry همان مدل** (۲ تلاش)
- Timeout/حد Rate ⇒ Backoff + ۳ تلاش + `AILog` برای هر تلاش
- `create_salon` واقعاً ردیف می‌سازد و `function_result` با همان `call_id` برمی‌گردد
- Multi-action (سالن + تسک روزانه)
- Create/schedule Task، Create/update PersonalProject، Search Memory، تغییر Tool policy
- Advice-only بدون mutation تجاری
- `provider_call_id` تکراری ⇒ بدون اجرای دوباره
- Delete قبل از Approve اجرا نمی‌شود؛ بعد از Approve دقیقاً یک‌بار و دوباره 409
- Outreach/Proposal ⇒ `needs_approval`
- Chat بدون Gemini Key ⇒ 409 روشن
- Conversation CRUD + Cascade
- Secret در هیچ Response/AILog/ActionRun نمی‌ماند
- Telegram: getMe success/invalid/timeout؛ صفر sendMessage قبل از Approve؛
  دقیقاً یک sendMessage بعد از Approve + Receipt؛ failure ⇒ `failed` بدون Crash

```bash
npm test --prefix frontend           # 29 passed (22 قبلی + 7 جدید)
npm run build --prefix frontend      # ✓ (dist ساخته شد)
npm audit --prefix frontend          # 0 vulnerabilities
ruff format --check backend          # ✓
ruff check backend                   # ✓
bash -n setup.sh start_app.sh        # ✓
git diff --check                     # ✓
./setup.sh (چک کامل)                 # ✓ بدون Conflict Dependency
```

### E2E مرورگر واقعی
در این Sandbox هیچ Chromium/Playwright قابل نصب نبود (دانلود Block شد)، بنابراین:
- جریان‌های UI با **Vitest + Testing Library** در jsdom اجرا شدند
  (send, Enter/Shift+Enter، Action card، Approval navigation، New/Load/Delete،
  Timeout+Retry، Telegram/Receipt).
- سرور واقعی (`uvicorn`) اجرا و بررسی شد: Dashboard 200 از `/`، `/api/health` OK،
  `/api/system/status` بدون Secret، `POST /api/assistant/chat` بدون کلید ⇒ 409 فارسی.
- هیچ خروجی واقعی Gemini/Telegram جعل نشده است؛ فرمان‌های Verification دستی پایین.

---

## ۴. محدودیت واقعی

- هیچ Credential واقعی Gemini/Telegram در محیط در دسترس نبود؛ همه Providerها
  در تست‌ها Mock شده‌اند. تحویل واقعی نیازمند کلید کاربر است (Security).
- مرورگر Headless در Sandbox قابل نصب نبود؛ E2E کامل مرورگر در سطح
  Component/API + بررسی زنده سرور انجام شد.
- Email/WhatsApp عمداً Stub نشده‌اند؛ معماری Adapter فقط برای Telegram منطقی
  پیاده‌سازی شده تا Channel غیرمتصل هرگز «sent» اعلام نشود.

## ۵. Verification دستی (بعد از نصب)

```bash
./setup.sh && ./start_app.sh        # → http://127.0.0.1:8000
```
1. Settings ← Gemini: کلید را وارد و «اعتبارسنجی و ذخیره امن»؛ مدل پیشنهادی را ببین.
2. «همراه من»: `یک سالن آفتاب با شماره 09121234567 در تهران اضافه کن`
   ⇒ کارت Action سبز + ID؛ سالن در CRM ظاهر شود (بدون Reload).
3. `برای پیگیری پروژه‌ها یک تسک روزانه ساعت ۹ صبح بساز` ⇒ تسک با `daily/09:00`.
4. `پروژه فروشگاه سپهر را بساز و فعال کن` ⇒ پروژه + transition معتبر.
5. `این سالن را حذف کن` ⇒ Badge «نیازمند تأیید»؛ قبل از Approve سالن می‌ماند؛
   بعد از Approve حذف می‌شود و Approve دوباره 409.
6. Telegram: توکن Bot ← `getMe`؛ در Settings مخاطب chat_id ثبت کن؛
   `این پیام را برای کارفرما در تلگرام بفرست` ⇒ Approve ⇒ Receipt `message_id` در
   «پیام‌های خروجی» و «sent».
7. موبایل 390px: منو Scroll مستقل، Bottom Nav هنگام باز بودن منو مخفی،
   Composer بالای Bottom Nav و بدون Horizontal overflow.
