# Genio 🇹🇳

**مساعد ذكي معمول للتونسي — يفهمو ويحكي معاه بلغتو.**

Genio هو أول صاحب ذكاء اصطناعي تونسي: يفهم الدارجة، ينظّم خدمتك، يبرمج، يراقب السيرفرات، ويخلّيك تتحكم في دارك الذكية — من تليفونك ولا حاسوبك. ومن بعد تنجم تبدّل للفرنسية ولا للإنجليزية وقت ما تحب.

- 🌐 جرّبو مباشرة: **https://genio.hitech.tn** (جرّب Genio توة ←)
- 💻 ركّبو على جهازك: شوف [ركّبو توّا](#ركّبو-توّا)

---

## شنوّة هو Genio؟

Genio وكيل ذكي (agent) يخدم محليًا ولا عبر السحاب حسب اختيارك:

- **يحكي بالدارجة** — اكتب ولا احكي: «نظّملي السيرفر» ولا «شغّل الضو».
- **يخطط وينفّذ** — يحلّل طلبك، يستعمل الأدوات (bash, ملفات, متصفح) ويوريك كل خطوة.
- **يجاوب بالصوت والصورة** — مع ملفات وجداول، وينجم يكمّل وحدو في الخلفية.
- **يحترم خصوصيتك** — المفتاح ما يخرجش من السيرفر، ما فماش API key في المتصفح.

## شنوّة ينجم يعمل؟

| الحاجة | كيفاش |
|---|---|
| احكي بالدارجة | اكتب ولا احكي، Genio يفهم عربي ودارجة وفرنسي وانجليزي |
| برمجة وأتمتة | يكتب وينفّذ السكربتات، يدير Docker وVPN والشبكات |
| مراقبة سيرفرات | CPU/RAM/GPU حية، تنبيهات، صحة النظام |
| منزل ذكي | أوامر صوتية وأتمتة يومية (n8n) |
| تعليم | شرح ومراجعة بالدارجة من الابتدائي للجامعة |

## كيفاش تبدأ؟

1. ادخل لـ **https://genio.hitech.tn/app** (ولا `جرّب Genio توة` من الصفحة الرئيسية).
2. كمّل من غير حساب (الوضع المحلي) ولا ادخل بـ Google (السحاب).
3. اقرا الأذونات ووافق ولا كمّل من غيرها.
4. ابعث أول رسالة بالدارجة، مثال: `شنوّة تنجم تعمللي؟`

## ركّبو توّا

النسخة الحالية: **v5.0.0** ([ملاحظات النسخة](https://github.com/HiTechLabTN/genio/releases/tag/v5.0.0)).

**Linux (AppImage / DEB) — متوفر ✅**

```bash
# AppImage + تحقق SHA-256
curl -fsSL -o genio.AppImage https://github.com/HiTechLabTN/genio/releases/download/v5.0.0/genio-client_4.3.0_amd64.AppImage
curl -fsSL -o genio.AppImage.sha256 https://github.com/HiTechLabTN/genio/releases/download/v5.0.0/genio-client_4.3.0_amd64.AppImage.sha256
sha256sum -c genio.AppImage.sha256
```

**Docker — متوفر ✅**

```bash
docker pull ghcr.io/hitechlabtn/genio:5.0.0
docker run -p 8080:8080 ghcr.io/hitechlabtn/genio:5.0.0
```

**مثبّت CLI (أي Linux)**

```bash
curl -fsSL https://raw.githubusercontent.com/HiTechLabTN/genio/main/installer/bootstrap/install.sh | GENIO_REF=v5.0.0 bash
```

`GENIO_REF` يقبل branch (`main`) ولا tag (`v5.0.0`) ولا commit SHA (كامل ولا مختصر) — المثبت يفرّق بينهم ويتحقق من الـ SHA. للتحقق من ref بدون تثبيت: `GENIO_REF=<ref> GENIO_RESOLVE_ONLY=1 bash installer/bootstrap/install.sh`.

**تحب Genio يعاونك خطوة بخطوة؟** (وضع المساعد — بالدارجة: يفحص جهازك، يفسّر الناقص، يطلب إذنك قبل أي تغيير، يصلّح ويتحقق ويعاود):

```bash
curl -fsSL https://raw.githubusercontent.com/HiTechLabTN/genio/main/installer/bootstrap/install.sh | GENIO_REF=v5.0.0 GENIO_ASSISTANT=1 bash
```

كان حاجة ناقصة (Git، Docker...)، المساعد يقولك علاش لازمته ويقترح الحزمة الصغيرة المناسبة — و`genio doctor` يوريك حالة جهازك في أي وقت. Docker مستحسن أما موش إجباري: من غيرو Genio يخدم محلي (Tier A)، وتنجم تصلّحو بعد.

**Windows / macOS / Android / iOS** — ❌ غير متوفر حالياً (ما فماش نسخ موقعة منشورة، وما نعرضوش أزرار وهمية).

بعد التثبيت تحقق:

```bash
genio doctor
# → HEALTHY (0 FAIL)
```

مساعد التثبيت التفاعلي: https://genio.hitech.tn/install — ومركز التحميل: https://genio.hitech.tn/download

## كيفاش تستعملو؟

- **الدردشة**: افتح الدردشة من زر 💬، اكتب ولا اضغط المايكرو (تحويل الكلام التونسي لنص).
- **الأوضاع**: تقني (لوحة كاملة) / موحّد (محادثة + مهمة) / ماسكوت (شخصية ثلاثية الأبعاد).
- **الكثافة المعرفية**: بسيط / مفصّل / متقدّم — تنبيهات الأمان والأخطاء تبقى ديما ظاهرة.
- **اللغة**: تونسي (افتراضي، RTL) ← فرنسي ← انجليزي، من المبدّل في القائمة.

## الأمان والخصوصية

- العزل fail-closed: من غير Docker ما فماش تنفيذ على الجهاز.
- كل عملية تتعدى على بوابة سياسات ALLOW/DENY/ESCALATE.
- المفاتيح والرموز تتنظف من التليميتري والسجلات.
- **ما ندّعيوش «آمن 100%»** — كل ادعاء مربوط باختبار: شوف [مركز الأمان](https://genio.hitech.tn/security).

## للمطوّرين

```bash
# الباكند (FastAPI :8000)
python genio_server.py

# الواجهة (Vite)
cd genio_client && npm install && npm run dev   # تطوير :1420
npm run build && npm run preview                 # معاينة :8098
```

الاختبارات:

```bash
cd genio_client && npx tsc --noEmit && npx vitest run   # frontend
python3 -m pytest tests/ -q                              # backend (227)
```

- WebSocket الوكيل: `/ws/agent` — ابعث `{action:'prompt', text}` ← استقبل `stats/answer`.
- API: شوف [مستكشف API](https://genio.hitech.tn/api) (مشتق من OpenAPI، للقراءة فقط).
- المعمارية: [استكشف](https://genio.hitech.tn/explore) — كل مجال بغرضو وحدودو وحالتو الصادقة.

## التوثيق

- [التوثيق](https://genio.hitech.tn/docs) — التثبيت، الاستعمال، الإصلاح (منتقى من `docs/` وقت البناء).
- [وثائق التثبيت](https://genio.hitech.tn/install) — مساعد تفاعلي بأوامر حقيقية وحالات صادقة.

## API

المستكشف للقراءة فقط — ما فماش وحدة تحكم حية. التوثيق حسب الـ endpoint (مفتاح API في الترويسة ولا Bearer قصير العمر). الأخطاء: HTTP قياسي + JSON منظف (عمرها ما تتسرب أسرار ولا مسارات ولا stack traces للواجهة).

## Open Source

الكود مفتوح وقابل للتوسيع: أدوات جديدة، سكربتات، أصوات — كل شيء قابل للتخصيص.
المصدر: https://github.com/HiTechLabTN/genio — ملف النسخة والـ SBOM مربوطين من [صفحة النسخة](https://github.com/HiTechLabTN/genio/releases/tag/v5.0.0).

## المساهمة

1. ابنِ الميزة + اختبارها (vitest/pytest خضر).
2. البرهن من متصفح حقيقي (screenshot/dليل)، موش من قراءة الكود فقط.
3. commit واضح، push لـ main — من غير tag ولا release ولا bump version (النسخ لها مسارها الخاص).

## اللغات

- **التونسية (الدارجة)** — اللغة الافتراضية والأولى، RTL.
- **الفرنسية** — ثانوية، LTR.
- **الإنجليزية** — ثانوية، LTR.
- المصطلحات التقنية (API, Docker, WebSocket, CPU, GPU…) تبقى انجليزية كيما في قاموس المطور التونسي، والشرح داير بيها تونسي.

---

## Version française (résumé)

**Genio — premier compagnon IA tunisien.** Il comprend la Darija, organise votre travail, code, surveille vos serveurs et pilote votre maison connectée. Essayez-le : https://genio.hitech.tn — version actuelle **v5.0.0** ([notes](https://github.com/HiTechLabTN/genio/releases/tag/v5.0.0)). Installation Linux/Docker documentée ci-dessus (commandes identiques). Sécurité honnête : [centre de sécurité](https://genio.hitech.tn/security). Langues : tunisien (défaut) → français → anglais.

## English summary

**Genio — first Tunisian AI companion.** It understands Darija, organizes your work, codes, monitors servers and controls your smart home. Try it: https://genio.hitech.tn — current release **v5.0.0** ([notes](https://github.com/HiTechLabTN/genio/releases/tag/v5.0.0)). Linux/Docker install commands above. Honest security posture: [security center](https://genio.hitech.tn/security). Languages: Tunisian (default) → French → English.
