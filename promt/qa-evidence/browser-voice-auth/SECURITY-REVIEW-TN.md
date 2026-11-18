# المراجعة الأمنية المفصّلة — الصوت + OAuth + الهوية (2026-10-11)

منهجية: قراءة سطر-بسطر للملفات الجديدة/المعدّلة + إثبات حيّ حيث أمكن
(متصفح حقيقي، sockets حقيقية). بلا commit. الخلاصة أولًا: **3 نتائج
تستحق الإصلاح قبل الاعتماد** (واحدة عالية في prod، واحدة متوسطة، واحدة
توافرية) + ملاحظات مقبولة موثقة.

## F1 (عالية — تكسر الدخول في prod): فحص Origin/Referer يرفض callbacks الشرعية

`oauth_login.py:331 _check_origin` يشترط أن يكون host الـOrigin/Referer هو
مضيفنا. لكن تدفق OAuth الشرعي: Google/GitHub يعملان 302 → المتصفح يتنقل
(GET علوي) إلى `/callback` حاملًا `Referer: https://accounts.google.com/`
(أو github.com) في prod (HTTPS→HTTPS). النتيجة: **كل تسجيل دخول حقيقي
في prod يُرفض بـ`bad_request`**، بينما dev (HTTP) يمرّ لأن الـdowngrade
يحذف الـReferer — عطل خفي لا يظهر في الاختبار المحلي.
الدفاع الصحيح موجود أصلًا: `state` العشوائي أحادي الاستعمال + PKCE +
SameSite (وهو المعيار لـOAuth callbacks). الإصلاح: حذف البوابة (5 أسطر).

## F2 (متوسطة — انحراف عن العقد): GitHub بلا PKCE

`_PENDING` يخزّن `verifier` للطرفين، لكن `oauth_start` لا يرسل
`code_challenge` لـGitHub ولا الـexchange يرسل `code_verifier` (GitHub
يدعم PKCE لكل العملاء اليوم). الإصلاح: سطران في البدء + سطر في التبادل.

## F3 (توافرية — تجميد event loop حتى 20s): جلب JWKS متزامن داخل مسار async

`_jwks_keys()` يعمل `httpx.Client` المتزامن + `verify_google_id_token`
داخل `_exchange_google` (async). عند انتهاء الكاش (كل ساعة) أول دخول
يجمّد كل الاتصالات (WS/telemetry/kill) حتى `_TIMEOUT`. الإصلاح:
`await asyncio.to_thread(...)` للجلب والتحقق.

## سليمة (مثبتة بالقراءة + الاختبار)

- **state:** عشوائي، TTL 10د، استهلاك ذري (`pop` وحيد الرابح)، replay مرفوض (مختبر).
- **Google:** توقيع RS256 + iss/aud/exp/nonce + kid مجهول مرفوض (مختبرة فرادى). لا tokeninfo. `azp` غير لازم (aud مفرد).
- **GitHub:** التوكن لاستدعاءين فقط ولا يُخزّن/يُسجَّل/يُرجع؛ البريد primary+verified فقط والمخفي None (مختبر).
- **لا ربط بالبريد** (مفتاح `(provider, sub)` فقط — مختبر)، **لا fixation** (توكن جديد كل دخول)، **إبطال** عند الخروج/الانتهاء (مختبر)، **أسرار**: لا client_secret/token في frontend (grep bundle+src)، لا logs (مختبر caplog + مسح console المتصفح).
- **user_store:** تخزين hash فقط، SQL مُعامَل كلها، أول كاتب يربح الملكية، رفض متقاطع في `resume` و`prompt` مع تصفير `_ACTIVE_RUNS` قبل الرفض (سطر 878 — تحققت: لا busy عالق)، تنظيف `_WS_USERS` عند القطع.
- **main.py WS:** البوابة جمعية (`api-key` القديمة تعمل كما كانت + cookie)، تحليل Cookie متزامن والتحقق async، لا credentials في query (الـlegacy `?token=` للـBearer القديم بقي كما كان — خارج نطاق التغيير).
- **الصوت:** bind loopback فقط، سقف 2000 حرف، 400/422/503 صادقة، CORS `*` على خدمة loopback (الـbind هو الحد — مقبول لصندوق أحادي المستخدم، موثق).
- **Frontend:** URLs يبنيها الـbackend، الجلسة cookie HttpOnly، الدخول اختياري دائمًا، `?login=` يُستهلك ويُمسح من الـURL، RTL مثبت حيًّا.

## ملاحظات مقبولة (ليست blockers)

- `_PENDING` في الذاكرة: محدود بـTTL + rate-limit العام (~12k مدخل كحد أقصى نظري). مقبول.
- `compare_digest` التافه في `get_session_user` (مقارنة digest بنفسه): كود ميت مضلّل — تنظيف تجميلي مقترح، لا ثغرة (الفحص الحقيقي هو lookup الـhash).
- جلسات متزامنة متعددة للمستخدم الواحد مسموحة (الخروج يبطل واحدة). تصميم مقبول.
- `delete_cookie` بلا `samesite`/`secure` مطابقة: الحذف يطابق (name, path, domain) — يعمل على نفس الـscheme. لا مشكلة عملية.
- CSP `style-src` (inline styles قائمة): تجميلية مسبقة، خارج النطاق.

## النطاق (مثبت طازجًا)

المعدّل في هذه المهمة: `App.tsx`، `GoogleAuthOnboarding.tsx`، `googleAuth.ts`، `lang.ts`، `main.py`، `index.html` (إصلاح CSP المكتشف بالاختبار) + ملفات جديدة (OAuth ×2، voice ×1، frontend ×6، tests ×3، evidence ×1). **الملفات الأمنية السابقة غائبة كلها** عن كل diff. الـindex فارغ (لا staging جديد). لا commit/push/release/version.

## الحكم

الكود **غير جاهز للاعتماد** قبل F1 (يجب)، ويُستحسن F2+F3 معه (صغيرة، نفس الملف). كل شيء آخر سليم ومثبت. بعد الإصلاحات الثلاث + إعادة الاختبار المركّز، يُعاد تقييم الدمج.
