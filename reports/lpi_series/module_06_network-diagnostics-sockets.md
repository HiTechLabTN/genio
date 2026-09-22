# Network Diagnostics & Socket Inspection

## 1. الشرح التقني
Network is like the road in a city — if it's down, everyone stops moving. `ip` lists all your network interfaces and their IPs, while `ss` shows you which ports are busy, just like knowing which streets in town have cars.

## 2. تفصيل الأوامر
1. `ip addr show` — شوف لابدك الـ IP ونوع الواجهة (wan أو lan).
2. `ss -tuln` — شوف الموديل: أي منفذ يعمل وحده؟ `-t` TCP، `-u` UDP، `-l` escuchando، `-n` بلا نوميمات.
3. `ping -c 4 example.com` — تحقق من الـ connectivity: ابعث 4 حزم وراقب الإجابة.
4. `curl -I http://example.com` — شوف الردود الاحتفالية بدون الـ body: كاشف معلومات السيرفر والـ cache.

## 3. سيناريو Self-Healing في الواقع
نحاول نشغّل `./app` وتحاصي على "Permission denied". أشرحلي المخاطر التي يجب الانتباه لها:
1. `ls -l app` — علاش ملف الـ binary مكتوم؟ `chmod +x app`
2. الـ user الذي يخدم ما عندو صلاحية التنفيذ؟ `sudo chown myuser:mygroup app`
3. الـ binary شغّل ماشي، والـ script يعطي خطأ في أول سطر: تحقق من `#!/bin/bash` — الـ shebang صحيح؟
4. آخر حاجة: الـ PATH المعيّن في السيرفر مصغر — ابعث `./app` بدل `app` إذا كان الـ binary في `~/bin` ما شفاهي.

## 4. تمرين المخبر العملي
1. علاش الحاوية ترفض يخدم على المنفذ 8080؟ نتحققو: `ss -tuln` و `sudo journalctl -u docker`.
2. كيفاش نتأكدو من الـ DNS؟ `ping` و `curl` معاكين — شوف الـ ANSWER في `nslookup example.com`.
3. إذا كان الـ binary صغير والـ port مفتوح، اشرحلي المطلوب: الـ app ما تحبس على الـ 80 فوق الـ 443 إلا لو كان HTTPS مكتوم في الكود.
