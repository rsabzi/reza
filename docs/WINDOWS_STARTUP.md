# اجرای خودکار در Windows

## پیش‌نیاز اولیه

یک‌بار از داخل PowerShell یا Command Prompt در پوشه پروژه اجرا کنید:

```bat
setup.bat
```

برای استفاده از Gemini، پس از اجرا وارد «تنظیمات و سیستم» Dashboard شوید و کلید را همان‌جا اعتبارسنجی و ذخیره کنید؛ ویرایش دستی `.env` لازم نیست.

## روش پیشنهادی: Task Scheduler

1. در Start عبارت **Task Scheduler** را جست‌وجو و باز کنید.
2. از پنل Actions گزینه **Create Task…** را انتخاب کنید.
3. نام را `Personal AI Agent Core` بگذارید و گزینه **Run only when user is logged on** را انتخاب کنید.
4. در تب **Triggers** یک Trigger با گزینه **At log on** برای کاربر فعلی بسازید.
5. در تب **Actions** گزینه **Start a program** را بسازید:
   - Program/script: مسیر کامل `start_app.bat`
   - Start in: مسیر پوشه همین پروژه
6. در تب **Conditions** در صورت لپ‌تاپ، گزینه اجرای صرفاً هنگام اتصال برق را غیرفعال کنید.
7. Task را ذخیره کنید و با گزینه **Run** یک‌بار آزمایش کنید.
8. آدرس `http://127.0.0.1:8000` را باز کنید؛ سلامت API در `http://127.0.0.1:8000/api/health` قابل بررسی است.

## روش ساده: پوشه Startup

1. کلیدهای `Win + R` را بزنید و `shell:startup` را اجرا کنید.
2. از `start_app.bat` یک Shortcut بسازید و Shortcut را در پوشه بازشده قرار دهید.
3. در Properties میانبر، فیلد **Start in** را روی مسیر پروژه تنظیم کنید.

Task Scheduler قابل‌اعتمادتر است، چون پوشه کاری و زمان اجرا را صریح نگه می‌دارد.

## توقف و عیب‌یابی

- برای توقف، پنجره `Agent Core Dashboard + API` را ببندید.
- اگر پورت اشغال بود، پیش از اجرا متغیر را تنظیم کنید:

```bat
set APP_PORT=8100
start_app.bat
```

- مستندات تعاملی API: `http://127.0.0.1:8000/docs`
- دیتابیس محلی: `agent_core.db`
