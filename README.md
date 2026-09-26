# 🇹🇳 جينيو (Genio v2.0-RC1) — الذكاء الاصطناعي السيادي التونسي
> **"المهندس المستقل: في دارك، تحت يدك، وبسيادتك الكاملة."**


[![Status](https://img.shields.io/badge/Release-v2.0.0--sovereign--rc1-00ffcc?style=for-the-badge)](https://github.com/HiTechLabTN/genio/releases)
[![Tests](https://img.shields.io/badge/Tests-269%20Passed-brightgreen?style=for-the-badge)](tests/)
[![Security](https://img.shields.io/badge/Security-Fail--Closed%20Sandbox-red?style=for-the-badge)](docs/SECURITY.md)
[![Voice](https://img.shields.io/badge/Voice-Tunisian%20VODER%20140Hz-blue?style=for-the-badge)](engines/voder/)


---


## 📖 القصة والروح (The Sovereign Vision)


في وقت ولات فيه كبرى منصات الذكاء الاصطناعي تستعمل في معطيات المستخدمين وتتحكم في الوصول لبياناتهم، خرج **جينيو (Genio)** كمشروع سيادي تونسي 100%.


جينيو موش مجرّد واجهة فوق نموذج سحابي، بل هو **محرك تشغيلي لوكلاء الذكاء الاصطناعي (Sovereign Autonomous Agent Runtime)** مخدوم باش يتنصب محلياً على أجهزتك وسيرفراتك الخاصة. يفهمك بالدارجة التونسية، يخدم معاك كمهندس برمجيات ونظم، وما يخرج حتى بايت من دارك بدون موافقتك.


يمثل جينيو "العقل المفكر" المتصل بنظام التشغيل المستقبلي **HiTech-OS** ومستودع التخزين السحابي السيادي **HiTech Drive**.


---


## ⚡ ميزات الإصدار (v2.0-RC1)


* **🗣️ تواصل تونسي قح (VODER Jarvis Voice):** فهم للدارجة التونسية، مع صوت رجالي سيادي عميق بتردد 140Hz.
* **🧠 تفكير شفاف وتوليد سريع:** مسار ردود سريعة (Fast-path Reflex) في أقل من **14ms**.
* **🛡️ أمان سيادي قطعي (Fail-Closed Architecture):** محرك سياسات مستقل (Policy Engine) وعزل كامل (Strict Sandbox).
* **🎨 واجهة 2.5D سينمائية وخفيفة:** أفاتار سينمائي عالي الدقة يتفاعل مع وضعيات النظام.
* **🔌 جاهز للاندماج مع HiTech-OS:** عقد تواصل محلي عبر Unix Domain Socket (`/run/hitechos/ai.sock`).


---


## 🚀 التثبيت والتشغيل السريع (Quickstart)


```bash
# 1. استنساخ المستودع
git clone https://github.com/HiTechLabTN/genio.git
cd genio


# 2. إعداد المتغيرات والبيئة
cp .env.example .env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.lock


# 3. تشغيل الخادم والواجهة
python3 -m genio_server.main &
cd genio_client && npm ci && npm run build && npm run preview -- --port 8098 --host 0.0.0.0


فخر الصناعة البرمجية التونسية المستقلة 🇹🇳 — HiTechLab
```
