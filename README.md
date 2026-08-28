# Genio — Autonomous Multimodal AI Systems Engineer 🇹🇳

<p align="center">
  <img src="genio-logo.svg" width="180" alt="Genio Logo"/>
  <br>
  <b>أول مهندس ذكاء اصطناعي مستقل في تونس والعالم العربي (v4.0)</b>
  <br>
  منظومة مستقلة بالكامل: تخدم وحدها، تصلّح كودها وحدها، وتتكلم بالدارجة التونسية والعربية البيضاء.
  <br><br>
  <a href="https://genio.hitech.tn"><b>🌐 قمرة القيادة الحية: genio.hitech.tn</b></a> | 
  <a href="https://github.com/HiTechLabTN/genio/releases/latest"><b>📦 تحميل التطبيقات (Releases)</b></a>
</p>

---

## 📌 شنوة هو Genio؟

**Genio** هو مهندس بنية تحتية وذكاء اصطناعي مستقل بالكامل (Autonomous AI Systems Engineer):

* 🧠 **اتخاذ القرار وتوجيه الموديلات (Dynamic Model Routing):** يراقب حرارة كارت الشاشة (RTX 3060) والـ VRAM ويختار تلقائياً بين الموديلات المحلية على Ollama أو السحابية.
* 🛡️ **الإصلاح البرمجي الذاتي (Self-Healing Pipeline):** يكتشف أخطاء الران تايم والأوامر المكسورة، يحلل الـ Traceback، يستشير نماذج الكودينغ، ويصلح السكريبت ذاتياً ويعيد التنفيذ.
* 🎬 **إنتاج ومونتاج الميديا بدقة 1080p (Full Media Pipeline):** يسجل لقطات التيرمينال الحية، يركب تعليقاً صوتياً بالدارجة التونسية، وينشر أوتوماتيكياً على Ghost و YouTube عبر n8n.
* 🔄 **الذاكرة التراكمية (Evolving Memory):** يحفظ الأخطاء السابقة كقواعد برمجية ويحقنها في كل عملية تشغيل لمنع تكرار الخطأ.

---

## 📲 تحميل التطبيقات لجميع الأنظمة (Download Universal Clients)

| المنصة والنظام | نوع الحزمة | رابط التحميل المباشر |
| :--- | :--- | :--- |
| 🐧 **Linux (Pop!_OS / Ubuntu / Debian)** | حزمة تثبيت `.deb` | [تحميل genio-desktop-linux.deb](https://github.com/HiTechLabTN/genio/releases/latest/download/genio-desktop-linux.deb) |
| 📱 **Android** | تطبيق موبايل `.apk` | [تحميل genio-mobile.apk](https://github.com/HiTechLabTN/genio/releases/latest/download/genio-mobile.apk) |
| 🪟 **Windows (10 / 11)** | مثبت برامج `.exe` | [تحميل genio-setup-windows.exe](https://github.com/HiTechLabTN/genio/releases/latest/download/genio-setup-windows.exe) |
| 📦 **Linux Standalone** | حزمة محمولة `.AppImage` | [تحميل genio-desktop-linux.AppImage](https://github.com/HiTechLabTN/genio/releases/latest/download/genio-desktop-linux.AppImage) |
| 🍎 **iOS / iPhone** | تطبيق ويب PWA | افتح [genio.hitech.tn](https://genio.hitech.tn) واضغط **Add to Home Screen** |

---

## ⚡ التثبيت السريع عبر المساعد التفاعلي (Interactive Setup)

```bash
git clone [https://github.com/HiTechLabTN/genio.git](https://github.com/HiTechLabTN/genio.git)
cd genio
chmod +x bootstrap.sh
./bootstrap.sh
```

---

## 🏗️ البنية التنفيذية للسيستيم (8-Node Autonomous DAG)

```text
    ┌─────────────┐
    │  env_check   │ ← فحص جاهزية Docker و FFmpeg والموديلات المحلية
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │   content    │ ← كتابة المقال والسيناريو بالدارجة التونسية
    └──────┬──────┘
           │
     ┌─────┼─────┬──────────┐
     │     │     │          │
  ┌──▼──┐┌─▼─┐┌──▼──┐┌─────▼─────┐
  │video││aud ││cover││livetest    │ ← تسجيل تيرمينال ومونتاج وتوليد صوت
  └──┬──┘└─┬─┘└──┬──┘│recording   │
     │     │     │   └─────┬─────┘
     │     │     │         │
  ┌──▼─────▼─────▼─────────▼──┐
  │        audit + publish     │ ← تدقيق الجودة والأمان والنشر المباشر
  └────────────┬───────────────┘
               │
        ┌──────▼──────┐
        │   youtube    │ ← رفع الفيديو مع الفصول والوصف عبر n8n
        └─────────────┘
```

---

## 🧩 دليل الوحدات البرمجية الأساسية (Core Modules)

| المسار البرمجي | الوظيفة التقنية |
| :--- | :--- |
| `core/evolution/model_router.py` | التوجيه الذكي للموديلات حسب حرارة الـ GPU والـ VRAM. |
| `core/evolution/self_healing.py` | تشخيص الأخطاء وترقيع الكود وإعادة التنفيذ ذاتياً. |
| `core/skills/power_guard.py` | قفل الحفاظ على الطاقة ومنع النوم أثناء معالجة المهام. |
| `media/voice_synth.py` | توليد الصوت التونسي المتزامن مع خطوات الشرح والتطبيق. |
| `sandbox/livetest_recorder.py` | تسجيل شاشة التيرمينال الحية بدقة 1080p داخل بيئة دوكر. |

---

<p align="center">
  صُنع بكل فخر بواسطة <b>HiTech Lab 🇹🇳</b> — تونس
</p>
