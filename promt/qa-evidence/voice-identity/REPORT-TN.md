# تقرير GENIO — الصوت العربي + هوية Google/GitHub (2026-10-11)

## 1. سبب مشكلة النطق (مثبت بالكود والاختبارات)

ثلاث طبقات، كل وحدة مكسورة بطريقة مختلفة:
- **الموديل ما يعرفش العربية:** `Qwen3-TTS` يدعم (zh/en/ja/ko/de/fr/ru/pt/es/it + auto) — لا `ar`. الـ`422` عند طلب `ar` **مقصود** (RC-gate صريح في `voder_service.py:47` يرفض بدل ما يفشل بـ500). تغيير الـlocale وحده ما كانش باش يصلّح شيء.
- **خدمة VODER طايحة:** الـvenv متاعها محذوف (`engines/voder/venv_voder` غير موجود) وبروسيس زومبي من 7 أكتوبر (pid 4074) ترجع `500 Internal Server Error` حتى على `/health`. الـsystemd unit يشير للـvenv المحذوف. إصلاحها = إعادة بناء venv (torch 2.8.0 + CUDA + pyqt، غيغابايتات) — خارج نسبة هذه المهمة، وموثق كـrunbook أدناه.
- **متصفح لينكس ما فيهش صوت عربي:** الإخراج كان `SpeechSynthesis` بـ`ar-TN` — على دسكتوب لينكس بلا أصوات عربية يفشل بصمت. زر `speakViaVoder` اليدوي يطلب `language:"auto"` من خدمة طايحة → no-op صامت.

## 2. محرك الصوت المستعمل (عربي)

- **facebook/mms-tts-ara** (VITS، CPU فقط، يخدم على user-python الموجود: torch 2.11 + transformers 5.17).
- **القدرات:** ~150MB تنزيل واحد (278MB على القرص مع الصيغتين)، ترخيص **CC-BY-NC-4.0** (شخصي OK، تجاري ممنوع)، صوت MSA واحد، 16kHz.
- **المتطلبات:** لا GPU (تعمّدًا، لتفادي التنازع مع Ollama)، خدمة جانبية على `127.0.0.1:5051` (ملف جديد `genio_server/voice/arabic_tts_service.py`).
- **ما تم التحقق منه فعليًا:** 3 جمل (تونسية بسيطة، مختلطة فرنسي/تقني، أرقام وترقيم) → `200` + WAV صالح قابل للتشغيل (5.4s/6.7s/7.3s، peak ~0.64، RMS ~0.1 — موش مجرد HTTP 200). حالات `400` (فارغ)، `422` (لغة غير عربية / نص بلا حروف عربية)، و`503` (موديل غائب — مستحيل صوت مزيّف).
- **القيد المصرح به:** الصوت ينطق **MSA** — النص التونسي مفهوم بفونيتيك فصحى، موش أصالة لهجية. ما ندّعيش "تونسي منطوق" كامل.

## 3. ملفات الصوت التي تغيرت

- جديد: `genio_server/voice/arabic_tts_service.py` (sidecar :5051).
- جديد: `genio_client/src/lib/arabicVoice.ts` (توجيه العربية + أخطاء TN) و`arabicVoice.test.ts`.
- تعديل صغير: `genio_client/src/App.tsx` (الإجابات العربية → sidecar، FR/EN على المسار القديم، fallback للمتصفح عند الفشل + `stopArabic`).
- جديد: `tests/test_arabic_tts.py` (8 اختبارات).
- **ما تمسّش:** `useVoiceOutput.ts` (FR/EN)، `audio.ts` (STT)، `voder_service.py` (يستنى runbook الإصلاح)، ملفات العمل الأمني الخمسة.

## 4. ملفات OAuth والهوية التي تغيرت

- جديد: `genio_server/server/oauth_login.py` (Google OIDC: code+PKCE+state+nonce، تحقق RS256 محلي عبر JWKS؛ GitHub: code+state، exchange، `/user`+`/user/emails`، البريد المخفي يبقى None، **لا ربط بالبريد**).
- جديد: `genio_server/server/user_store.py` (جداول `users`+`login_sessions`+`session_owners` على `sessions.db` القائمة، `CREATE IF NOT EXISTS` — لا مساس بالجداول القائمة؛ الجلسات hash فقط، لا access/refresh tokens مخزنة).
- تعديل جراحي: `genio_server/server/main.py` (تركيب الـroutes + ربط WS بالـcookie + ملكية الجلسات + منع الوصول المتقاطع + تنظيف عند القطع).
- جديد frontend: `lib/session.ts`، `hooks/useSession.ts`، `components/OAuthLoginButtons.tsx` (Google+GitHub بأزرار واضحة، loading/error/retry).
- إعادة كتابة: `googleAuth.ts` (حذف كل الـmocks والـdemo bypass — الدخول الحقيقي عبر الـbackend فقط)، `GoogleAuthOnboarding.tsx` (تدفق حقيقي + حساب موثق + خروج، والدخول يبقى اختياريًا أبدًا).
- إضافة: مفاتيح `lang.ts` (TN/FR/EN: github/login_ok/login_failed/unavailable/retry/logout/account).
- جديد: `tests/test_oauth_login.py` (22 اختبارًا).

## 5. الإعدادات الخارجية اللازمة (placeholders فقط — لا credentials)

انظر `promt/qa-evidence/voice-identity/oauth-setup.md` الكامل. الملخص:
- `GENIO_GOOGLE_CLIENT_ID` / `GENIO_GOOGLE_CLIENT_SECRET` (كونسول Google، Web app).
- `GENIO_GITHUB_CLIENT_ID` / `GENIO_GITHUB_CLIENT_SECRET` (OAuth Apps).
- `GENIO_OAUTH_REDIRECT_BASE` (مثال dev: `http://localhost:8098`).
- Callback واحد دقيق للتسجيل في الطرفين: `{BASE}/api/v1/auth/oauth/callback`.
- `GENIO_SESSION_TTL` (افتراضي 7 أيام).
- **الدخول الخارجي الحقيقي لم يُختبر** (يتطلب apps ينشئها المشغّل) — مصرّح به، لا مدّعى.

## 6. الاختبارات والنتائج (فصل mocks عن الحقيقي)

- **حقيقي:** TTS عربي (3 جمل صوت صالح)، STT حي (`faster-whisper` ينسخ صوتًا حقيقيًا: tone → "Beep")، نقاط OAuth حيّة (`/start`→503 بلا إعداد، `/me`→401 مجهول، `/logout`→200)، بناء frontend ناجح، bundle بلا أسرار (grep).
- **Mocks (وحدات فقط):** HTTP المزودين في اختبارات OAuth (الـJWT نفسه RS256 حقيقي بمفتاح اختبار). Google/GitHub الحقيقيان غير مختبرين (نقطة 5).
- **الأرقام:** backend **581 passed, 0 failed** (+2 deselects بيئية موثقة + 1 xfail)؛ frontend **107/107 vitest** + `tsc` نظيف + `vite build` ناجح.
- **انحدار حقيقي أمسكته الاختبارات:** `include_router` كسر اختبارًا قائمًا (`app.routes` فيه `_IncludedRouter` بلا `.path`) → أُعيد التصميم بتسجيل routes مباشر (نفس أسلوب الملف).

## 7. ما بقي غير منجز وأسبابه

1. **إصلاح VODER (FR/EN عبر Qwen):** venv محذوف — الإعادة = تنزيلات غيغابايتات + بناء طويل. FR/EN يخدمان اليوم عبر SpeechSynthesis (لم يُمسّا). الـrunbook: `engines/voder/setup.py` + `requirements.txt` ثم `systemctl restart voder-5050` (والزومبي 4074 سيُستبدل).
2. **الدخول الخارجي الحقيقي:** ينتظر إنشاء OAuth apps (نقطة 5) ثم اختبار end-to-end يدوي.
3. **دقة STT بالدارجة:** الأنبوب مثبت حيًا، لكن الدقة بالتونسي تحتاج ميكروفون حقيقي (لا mic headless).
4. **الذاكرة الشخصية الكاملة:** تم فقط ربط الهوية (user_id داخلي ثابت، ملكية الجلسات، منع متقاطع، حذف الهوية `delete_user`) — التفعيل/الإدارة/الحذف عبر UI قرار معماري لاحق.
5. **أصالة اللهجة صوتيًا:** MSA حاليًا؛ صوت درجي حقيقي يتطلب موديلًا غير متوفر محليًا اليوم.

## 8. حالة git

```
# git status --short (مختصر — الكامل في سجل الجلسة)
 M GENIO_INSTALLER_UX_AUDIT.md, feedback_memory.json, gestures.db,
   patterns.json (حية/مسبقة — خارج النطاق)
 M genio_client/src/App.tsx, GoogleAuthOnboarding.tsx, lib/googleAuth.ts,
   lib/lang.ts, genio_server/server/main.py (هذه المهمة)
?? (جديد هذه المهمة): OAuthLoginButtons, useSession, arabicVoice(+test),
   session(+test), oauth_login.py, user_store.py, voice/, test_arabic_tts,
   test_oauth_login, promt/qa-evidence/voice-identity/
# git diff --cached --stat: فارغ (لا staging جديد)
# الملفات الخمسة للعمل الأمني: غائبة من كل القوائم (لم تُلمس)
```

## 9. تأكيدات السلامة

- الـstaging الأمني السابق بلا أي تغيير (index فارغ، ملفاته الخمسة غير مذكورة في أي diff).
- لا `git add`/`reset`/`restore`/`stash` نُفّذت. لا commit/push/release/version bump.
- البوابات القائمة (Bearer/HMAC، rate limits، prod boot guard، WS legacy) untouched — الإضافات فقط.
- القيود المعمارية محترمة: لا تغيير عقود API/WS/IPC، لا system prompt/Ollama، لا sandbox/policy، لا dependencies ثقيلة جديدة (pyjwt صغير ومبرر؛ MMS ~150MB معلن).
- **لا "تمّ الإصلاح" لما لم يُتحقق منه:** الدخول الخارجي، دقة الدارجة STT، إصلاح VODER — كلها مسجلة فوق كغير منجزة.
