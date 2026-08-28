<div align="center">

# 🇹🇳 Genio — Autonomous Multimodal AI Systems Engineer

<img src="genio-logo.svg" width="180" alt="Genio 3D Mascot"/>

### أول مهندس ذكاء اصطناعي مستقل في تونس والعالم العربي (v4.0)
**منظومة أوتونوموس كاملة • تخدم وحدها، تصلّح كودها وحدها، وتتكلم بالدارجة التونسية والعربية البيضاء**

[🌐 قمرة القيادة الحية (genio.hitech.tn)](https://genio.hitech.tn) &nbsp;|&nbsp; [📦 تحميل التطبيقات (Releases)](https://github.com/HiTechLabTN/genio/releases/latest)

---

</div>

<div dir="rtl" align="right">

### 🚀 شنوة هو Genio بالضبط؟

منظومة **Genio** هي **مهندس بنية تحتية وذكاء اصطناعي مستقل (Autonomous AI Systems Engineer)** مبنية لإدارة السيرفرات وصناعة المحتوى التقني:

* 🧠 **اتخاذ القرار وتوجيه النماذج (<bdi>Dynamic Model Routing</bdi>):** يراقب حرارة كارت الشاشة (<bdi>RTX 3060</bdi>) والـ <bdi>VRAM</bdi> ويقرر تلقائياً وقتاش يخدم بالموديلات المحلية على <bdi>Ollama</bdi> ووقت الذروة يخدم بالسحاب.
* 🛡️ **الإصلاح والترقيع الذاتي (<bdi>Self-Healing Pipeline</bdi>):** يكتشف أخطاء الران تايم، يحلل الـ <bdi>Traceback</bdi>، يستشير نماذج الكودينغ، ويصلح السكريبت في البلاصة ويعاود يخدم.
* 🎬 **إنتاج الميديا والفيديو 1080p (<bdi>Full Media Pipeline</bdi>):** يسجل لقطات التيرمينال الحية، يركب تعليقاً صوتياً بالدارجة التونسية، وينشر أوتوماتيكياً على <bdi>Ghost</bdi> و <bdi>YouTube</bdi> عبر <bdi>n8n</bdi>.
* 🔄 **الذاكرة التراكمية (<bdi>Evolving Memory</bdi>):** يحفظ الأخطاء السابقة كقواعد برمجية ويحقنها في كل تشغيل لمنع تكرار الخطأ.

---

### 📲 تحميل التطبيقات لجميع الأنظمة (Download Universal Clients)

<div align="center">

| المنصة والنظام | نوع الحزمة | رابط التحميل المباشر |
| :--- | :--- | :--- |
| 🐧 **Linux (Pop!_OS / Ubuntu / Debian)** | حزمة تثبيت `.deb` | [تحميل genio-desktop-linux.deb](https://github.com/HiTechLabTN/genio/releases/latest/download/genio-desktop-linux.deb) |
| 📱 **Android** | تطبيق موبايل `.apk` | [تحميل genio-mobile.apk](https://github.com/HiTechLabTN/genio/releases/latest/download/genio-mobile.apk) |
| 🪟 **Windows (10 / 11)** | مثبت برامج `.exe` | [تحميل genio-setup-windows.exe](https://github.com/HiTechLabTN/genio/releases/latest/download/genio-setup-windows.exe) |
| 📦 **Linux Standalone** | حزمة محمولة `.AppImage` | [تحميل genio-desktop-linux.AppImage](https://github.com/HiTechLabTN/genio/releases/latest/download/genio-desktop-linux.AppImage) |
| 🍎 **iOS / iPhone** | تطبيق ويب PWA | افتح [genio.hitech.tn](https://genio.hitech.tn) واضغط **Add to Home Screen** |

</div>

---

### ⚡ التثبيت التفاعلي السريع (Interactive Setup)

```bash
git clone https://github.com/HiTechLabTN/genio.git
cd genio
chmod +x bootstrap.sh
./bootstrap.sh
```

---

### 🏗️ البنية التنفيذية للسيستيم (8-Node Autonomous DAG)

```text
    ┌─────────────┐
    │  env_check   │ ← فحص جاهزية Docker و FFmpeg والموديلات المحلية
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │   content    │ ← توليد المقال والسيناريو بالدارجة التونسية
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

### 🧩 دليل الوحدات البرمجية الأساسية (Core Modules)

| المسار البرمجي | الوظيفة التقنية |
| :--- | :--- |
| `core/evolution/model_router.py` | التوجيه الذكي للموديلات حسب حرارة الـ GPU والـ VRAM. |
| `core/evolution/self_healing.py` | تشخيص الأخطاء وترقيع الكود وإعادة التنفيذ ذاتياً. |
| `core/skills/power_guard.py` | قفل الحفاظ على الطاقة ومنع النوم أثناء معالجة المهام. |
| `media/voice_synth.py` | توليد الصوت التونسي المتزامن مع خطوات الشرح والتطبيق. |
| `sandbox/livetest_recorder.py` | تسجيل شاشة التيرمينال الحية بدقة 1080p داخل بيئة دوكر. |

</div>

---

<div align="center">
  صُنع بكل فخر بواسطة <b>HiTech Lab 🇹🇳</b> — تونس
</div>
