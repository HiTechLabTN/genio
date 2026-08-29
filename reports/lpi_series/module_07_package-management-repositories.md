# Package Management & Repositories

## 1. الشرح التقني
الـ package manager يسمّى apt، والـ database الـ local يسمّى dpkg — نفس المبدأ من Debian و Ubuntu: الـ cache على الطاولة والPackages في الخدمة.

## 2. تفصيل الأوامر
1. `sudo apt update` — تحديث السجلات من الركيزة.
2. `sudo apt install -y <pkg>` — نصب باش يقرر ويحل أي缺失ات.
3. `sudo apt remove --purge <pkg>` — إزالة كاملة مع الملفات المنشأة من الـ config.
4. `dpkg -i <deb>` — تثبيت ملف `.deb` محدّر.
5. `apt-cache policy <pkg>` — رؤية الخيارات المتاحة للـ version.

## 3. سيناريو
نحاول نشغّل `aktual` لكن يخرج `Permission denied`. وهنا نكتشف:
1. `which aktual` يجيب خاوي — غير مثبت.
2. `apt search aktual` يبين أن الاسم الصحيح `actual`.
3. ننصبو: `sudo apt install -y actual` — حل المشكلات: `apt` يأخّر أي الملفات المفقودة.
4. نتحققو: `aktual --version` ويجب يجيب مخاطب رسمي.

## 4. تمرين
1. شغّل `sudo apt update && sudo apt upgrade -y` — اشرحلي الفرق بين `update` و `upgrade`.
2. ابحث عن الـ editor الأفضل: نصب `neovim` باش نصبحو يخدمو بالـ .json والـ .py بالـ风格 الذكي.
3. تحقق من الملفات المفقودة: `dpkg -L <pkg> | xargs ls -l` باش تتأكدو من الـ path.
النتيجة: النظام يجيب على الأسئلة بأسلوب طبيعي، والحالة الطبيعية محددة بالقواعد.
