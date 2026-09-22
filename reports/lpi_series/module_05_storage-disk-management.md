# Storage & Disk Management

## 1. الشرح التقني
الـ disk هي المساحة الحية على القرص اللي يستخدمها النظام. الـ partition محددة بحجم ونجمة تخدم، والـ filesystem يحمل البيانات بالطريقة المحددة. df يعرض الجدول الرئيسي: `df -h` — العمود %Use يبين اللمس.

## 2. تفصيل الأوامر
1. `df -h`: عرض الـ disk usage بأسلوب مقروء.
2. `du -sh /path`: مجموع الـ space المستعمل في المسار الواحد.
3. `mount | column -t`: قائمة التثبيقات الافتراضية.
4. `fdisk -l`: خدمة منصّة عرض partitions على القرص сыр.
5. `sudo fdisk /dev/sdb` ثم `n`, `p`, وحدات، ثم `w`: إنشاء partition جديدة ويُطبق.

## 3. سيناريو Self-Healing
السيرفر يعطي Permission denied على ملف `/data/logs`.
1. نعرّفو الوضع: `df -h` يبين %Use صغير والـ inodes ممتلئين.
2. نتحققو من التثبيقات: `mount | grep /data` — إذا ما شاهدنا الـ bind mount، ننجمو: `/data` رايح على نقطة صغيرة و`/data/logs` يخدم مؤشر.
3. الحل: نضيف partition جديد في الموضع الحر: `fdisk`, `mkfs`, ثم نضيف سطر في `/etc/fstab` و `mount -a`.
4. تحقق آخر: `ls -ld /data/logs` يبين المسار الحقيقي والـ filesystem الصحيح.

## 4. تمرين المخبر
1. اشرح مسارك الـ home — شوف `df ~` وما رايحش فوق حد الغرض.
2. نبنيو مجلد كبير: `sudo mkdir -m 750 /data && sudo chown $USER:$USER /data`.
3. نربوطو ملفات مبسطة في `/etc/fstab`: `echo "/dev/sdb1 /data ext4 defaults 0 2" | sudo tee -a /etc/fstab`.
4. نتحققو: `mount -va` و `df -h` — الموقف الجديد بين الأغراض.
5. تحقق آخر: `du -sh /data` يجيب صغير الـ size، و `lsblk` يبين partition المحدّة.
