# Token Usage Tracking

This module tracks OpenAI API token usage, providing insights into API costs and usage patterns.

## Features

- **Detailed Token Tracking**: Records input tokens, output tokens, and total tokens for each API request
- **Cost Estimation**: Calculates estimated costs based on current OpenAI pricing
- **Usage Reports**: Generate daily and model-specific usage summaries
- **Admin Command**: Use `/token_usage [days]` to view token usage statistics (admin only)
- **Persistent Storage**: Stores usage data in an SQLite database for historical analysis

## Setup

1. Add your Telegram user ID to the `.env` file:
   ```
   ADMIN_USER_ID=your_telegram_user_id
   ```

2. To get your Telegram user ID, you can:
   - Use [@userinfobot](https://t.me/userinfobot) on Telegram
   - Forward a message from yourself to @userinfobot

## Usage

### Viewing Token Usage Statistics

As an admin, you can use the command:
```
/token_usage [days]
```

Where `[days]` is an optional parameter specifying how many days of data to include (default: 30).

### Programmatic Access

```python
import token_tracking

# Get a summary of token usage for the last 30 days
summary = token_tracking.get_token_usage_summary(days=30)

# Get formatted report
report = token_tracking.format_token_usage_report(days=7)  # Last week
print(report)

# Get current session usage
session_stats = token_tracking.get_session_token_usage()
```

## Database Structure

Token usage data is stored in an SQLite database at `data/token_usage.db` with two tables:

1. **token_usage**: Detailed logs of each API call
2. **daily_summary**: Aggregated usage by day

---

<div dir="rtl">

# پیگیری مصرف توکن

این ماژول مصرف توکن‌های API OpenAI را پیگیری می‌کند و اطلاعاتی درباره هزینه‌ها و الگوهای استفاده ارائه می‌دهد.

## ویژگی‌ها

- **پیگیری دقیق توکن**: ثبت توکن‌های ورودی، توکن‌های خروجی و کل توکن‌ها برای هر درخواست API
- **تخمین هزینه**: محاسبه هزینه‌های تخمینی بر اساس قیمت‌گذاری فعلی OpenAI
- **گزارش‌های استفاده**: تولید خلاصه‌های استفاده روزانه و مدل-محور
- **دستور مدیریتی**: استفاده از `token_usage/` برای مشاهده آمار استفاده از توکن (فقط مدیر)
- **ذخیره‌سازی دائمی**: ذخیره داده‌های استفاده در یک پایگاه داده SQLite برای تحلیل تاریخی

## راه‌اندازی

1. شناسه کاربری تلگرام خود را به فایل `.env` اضافه کنید:
   ```
   ADMIN_USER_ID=شناسه_کاربری_تلگرام_شما
   ```

2. برای دریافت شناسه کاربری تلگرام خود، می‌توانید:
   - از [@userinfobot](https://t.me/userinfobot) در تلگرام استفاده کنید
   - یک پیام از خودتان را به @userinfobot فوروارد کنید

## استفاده

### مشاهده آمار استفاده از توکن

به عنوان مدیر، می‌توانید از این دستور استفاده کنید:
```
/token_usage [تعداد_روز]
```

که `[تعداد_روز]` یک پارامتر اختیاری است که مشخص می‌کند چند روز از داده‌ها شامل شود (پیش‌فرض: 30).

### دسترسی برنامه‌نویسی

```python
import token_tracking

# دریافت خلاصه استفاده از توکن برای 30 روز گذشته
summary = token_tracking.get_token_usage_summary(days=30)

# دریافت گزارش فرمت‌شده
report = token_tracking.format_token_usage_report(days=7)  # هفته گذشته
print(report)

# دریافت آمار جلسه فعلی
session_stats = token_tracking.get_session_token_usage()
```

## ساختار پایگاه داده

داده‌های استفاده از توکن در یک پایگاه داده SQLite در `data/token_usage.db` با دو جدول ذخیره می‌شوند:

1. **token_usage**: گزارش‌های دقیق هر تماس API
2. **daily_summary**: استفاده تجمیعی بر اساس روز

</div> 