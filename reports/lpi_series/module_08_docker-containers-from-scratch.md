# Docker Containers from Scratch

## 1. الشرح التقني
Container هو نمط وحدة معزولة من التطبيق والبيانات — فكرة Box يحمل الـ Code وأمنياً الـ State. بناءً على Image، Container معدّل ومباشر.

## 2. تفصيل الأوامر
1. `docker run -d --name myapp nginx:latest`: تشغيل Image `nginx` باسم `myapp` في عزلة وبدون شاشة.
2. `docker ps`: نظرة على الحاويات اللي يخدموا — `-a` تعرض الكل، `-q` فقط الـ ID.
3. `docker exec -it myapp curl -I localhost`: تشغيل `curl` داخل الحاوية بحالة TTY وصbia.
4. `docker volume create data`: إنشاء وحدة بيانات مرتبطة — `-L` لمشاهدة المكان الحقيقي.
5. `docker network create frontend`: شبكة معزولة للوصول المشترك — `--attachable` بعد الإنشاء.

## 3. سيناريو حية
الحاوية ترفض الـ exec بـ Permission denied: نتحققو من الجذر:
1. `docker ps -a`: رجع الـ Status و Owner.
2. `docker inspect --format '{{ .Config.User }}' myapp`: إذا خاوي أو غير معيّن، الـ UID المطلوب في Image نفسه.
3. الحل: إنشاء Image نسخة مع `USER` صحيح — `Dockerfile: USER 101` ثم `docker build --build-arg UID=101 .`.

## 4. تمرين المخبر
1. بنجمة سيرفر جديد، اشرحلي الـ filesystem مائل للـ readonly باستثناء `/var/lib/docker` و `/tmp`.
2. نبنيو Image يصدر `500 Internal Server Error` — شنو تفعّلوا الـ healthcheck؟
3. بعد التحقق، أشرحلي المهام: نضيفو خدمة مسبقاً في شبكة معزولة ونزيدو بيانات محفوظة.
4. السؤال: شنو الفرق بين `restart: unless-stopped` و `always` — اشرحلي الحالات المطلقة.
