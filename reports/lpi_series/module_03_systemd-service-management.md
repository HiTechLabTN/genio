# Service Management with Systemd & Journalctl

## 1. الشرح التقني
Systemd يخدم كنظام تشغيل ووحدة إدارة المهام على Linux الحديث. جدول مصغّرات الخدمة: فعّل/وقف، حالتها، والـ logs بأسلوب طبيعي.

## 2. تفصيل الأوامر
1. `sudo systemctl start|stop|restart <unit>` — إجراءات أساسية.
2. `systemctl status <unit> -l` — حالة الخدمة بالتفاصيل.
3. `journalctl -u <unit> -b --no-pager` — logs لساعة الأخيرة بأسلوب مباشر.
4. `sudo systemctl enable|disable <unit>` — تفعيل وحدة في الـ boot.
5. `systemctl list-units --type=service --state=failed` — رجاء الخدمة المعلّمة.

## 3. سيناريو حقيقي
نفترضو أن `nginx` يعطي "Permission denied" في الـ log. أول نتحققو من الـ user:
1. `sudo systemctl status nginx` — شوف الـ User= في unit file.
2. تحقق من الملفات: `ls -l /etc/nginx/` — الـ uid المنفذ لا يتوافق.
3. نحلو: `sudo chown -R www-data:www-data /etc/nginx` و `systemctl restart nginx`.
4. نتأكدو: `journalctl -u nginx -b -n 50` — إذا ظهر "denied" مرة أخرى، نضيف الحل أعلاه.

## 4. تمرين مختبر
1. انشئ ملف unit يخدم `python3 -m http.server 80` بالاسم `httpd.service`.
2. جرب `File=/usr/bin/python3` و `ExecStart=/usr/bin/python3 -m http.server 80`.
3. سؤال: شنو الفرق بين `Restart=` y `On-failure=`؟ فكر في الحالات المرتبطة.
4. إجابة: `On-failure` يمحل بالـ exit code، و `Restart=on-failure` يضمن إعادة التشغيل.
