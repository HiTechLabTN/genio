# Permissions, Ownership & Security

## 1. الشرح التقني
الـ permissions هو الصوت في الجهاز: من شكون الملف ومتى. مفهوم أساسي على أي نظام نبني عليه النظام.
المجتمع المعمّر يعبر بالـ umask: القيمة التي تُطرح من RWX الافتراضي عند إنشاء ملف أو فاتحة دورة. فالـ umask يمثّل الـ denied بشكل مباشر.

## 2. تفصيل الأوامر
1. `chmod`: تعديل الأعداد الصوتية.
   ```
   chmod 755 file.py  # RWX لصاحب الملف، RX لباقي المستخدمين
   chmod u+x script.sh  # إعطائى التنفيذ للمالك
   ```
2. `chown`: تغيير المالك وال/pdf الملف.
   ```
   chown user:group file.txt  # صبغي الـ : فقط إذا كنت تقصد التغيير.
   chown --changes root:www-data /var/www/html/index.html  # تغيير فقط إذا المجموعة الجديدة موجودة.
   ```
3. `umask`: القيمة الافتراضية التي يُطرح منها RWX عند الإنشاء.
   ```
   umask 027  # الملفات خمسة وحدات مكتومة للمجموعة والبشر، غير لصاحب الملف.
   ```
4. `sudo`: المستخدم محدود في السياق فقط.
   ```
   sudo -u mysql mysqld_safe --skip-grant-tables  # باش MySQL يبدأ بـ skip-password في الوضع الصحيح.
   ```

## 3. سيناريو عملية
السيرفر يعمل `nginx` لكن الملفات مأهولة: `200 OK` بدل `403`.
1. نتحققو من الصوت: `ls -la /etc/nginx/sites-enabled/` — شوف الـ +rwxz.
2. إذا كان الـ group محدّر: `chown root:www-data app.py` و `chmod 750 app.py`.
3. المثال الأكثر شيوعاً: umask ضيق في سياق الـ init.d:
   ```
   #!/bin/bash
   umask 064  # الملفات خمسة ومكتومة للمستخدم فقط.
   /usr/bin/python3 /opt/app/main.py
   ```
4. تحقق نهائي: `sudo -u www-data python3 /opt/app/main.py` و `ps aux | grep main.py` يلزم يعرض الـ UID.

## 4. تمرين المخبر
1. اشرحلي شغّل ملف `backup.sh` باش ينسخ `/etc` إلى حاوية Docker — علاش ماشي رجع `Permission denied`؟
2. كيفاش نجعل الـ cron Job يعمل بالستة من الصباح بسهولة؟
