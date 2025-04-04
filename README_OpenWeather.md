# راهنمای پیکربندی کلید API سرویس OpenWeather

این راهنما مراحل لازم برای دریافت کلید API سرویس OpenWeather و پیکربندی آن در فایل `.env` را توضیح می‌دهد. این کلید برای فعال‌سازی قابلیت نمایش اطلاعات آب و هوا در ربات ضروری است.

## دریافت کلید API از OpenWeather

برای دریافت کلید API از سرویس OpenWeather، مراحل زیر را دنبال کنید:

### گام 1: ایجاد حساب کاربری

1. به وب‌سایت [OpenWeather](https://home.openweathermap.org/users/sign_up) مراجعه کنید.
2. فرم ثبت‌نام را تکمیل کنید و یک حساب کاربری جدید ایجاد نمایید.
3. ایمیل تأیید حساب خود را بررسی کنید و روی لینک فعال‌سازی کلیک نمایید.

### گام 2: دریافت کلید API

1. وارد حساب کاربری خود در OpenWeather شوید.
2. به بخش "API Keys" در منوی حساب کاربری خود مراجعه کنید.
3. در صفحه "API Keys"، می‌توانید یک نام برای کلید API خود وارد کنید و سپس دکمه "Generate" را کلیک کنید.
4. کلید API تولید شده را کپی کنید. این کلید یک رشته از حروف و اعداد است (مانند `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`).

> **نکته مهم**: پس از ثبت‌نام، ممکن است فعال‌سازی کلید API شما چند ساعت (حداکثر 24 ساعت) طول بکشد. در این مدت، ممکن است با پیام خطای `401 Unauthorized` مواجه شوید.

### گام 3: افزودن کلید API به فایل `.env`

1. به دایرکتوری اصلی پروژه بروید.
2. فایل `.env` را پیدا کنید، یا اگر وجود ندارد، یک فایل جدید با این نام ایجاد کنید.
3. خط زیر را به فایل `.env` اضافه کنید:

```
OPENWEATHER_API_KEY=کلید_API_شما
```

(به جای `کلید_API_شما`، کلید API واقعی که از OpenWeather دریافت کرده‌اید را قرار دهید)

4. فایل را ذخیره کنید.

## تست پیکربندی

برای اطمینان از صحت پیکربندی، می‌توانید یک پرسش مرتبط با آب و هوا از ربات بپرسید. برای مثال:

```
آب و هوای تهران چطور است؟
```

اگر همه چیز به درستی پیکربندی شده باشد، ربات باید اطلاعات به روز آب و هوای تهران را نمایش دهد.

## عیب‌یابی

اگر با مشکلی مواجه شدید:

1. مطمئن شوید که کلید API را به درستی در فایل `.env` قرار داده‌اید.
2. بررسی کنید که فایل `.env` در دایرکتوری اصلی پروژه قرار دارد.
3. توجه داشته باشید که فعال‌سازی کلید API ممکن است تا 24 ساعت طول بکشد.
4. اگر همچنان مشکل دارید، لاگ‌های برنامه را بررسی کنید تا پیام‌های خطای دقیق را مشاهده نمایید.

## مستندات بیشتر

برای اطلاعات بیشتر در مورد API سرویس OpenWeather، به [مستندات رسمی](https://openweathermap.org/api) مراجعه کنید. 