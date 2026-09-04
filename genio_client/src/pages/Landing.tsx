import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import genioHero from "../assets/mascot/genio-hero.webp";
import IslamicPatterns from "../components/background/IslamicPatterns";

export default function Landing() {
  return (
    <div dir="rtl" lang="ar" className="min-h-screen w-full bg-[#020B1E] text-slate-100" style={{ fontFamily: "Tajawal, system-ui, -apple-system, sans-serif" }}>
      {/* zellij .07 background */}
      <div className="pointer-events-none fixed inset-0 z-0 opacity-[0.07]">
        <IslamicPatterns />
      </div>

      {/* NAV */}
      <nav className="sticky top-0 z-20 flex h-[56px] items-center justify-between border-b border-white/10 bg-slate-950/60 px-4 backdrop-blur-md md:px-8">
        <div className="flex items-center gap-2">
          <img src={genioHero} alt="Genio" className="h-8 w-8 rounded-full object-cover border border-cyan-400/30" />
          <span style={{ fontFamily: "Reem Kufi, Tajawal, sans-serif" }} className="text-[18px] font-bold tracking-tight text-white">
            جينيو
          </span>
          <span className="hidden md:inline rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 font-mono text-[10px] text-emerald-300">SYSTEM LIVE</span>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/about" className="hidden md:inline rounded-full px-3 py-1.5 text-[13px] text-white/70 hover:text-white">المؤسس</Link>
          <Link to="/app" className="rounded-full bg-cyan-400 px-4 py-1.5 text-[13px] font-bold text-slate-900 shadow-[0_0_16px_rgba(34,211,238,0.4)] hover:bg-cyan-300">ادخل للتطبيق</Link>
        </div>
      </nav>

      {/* HERO */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-16">
        <div className="grid gap-8 md:grid-cols-2 md:items-center">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="order-2 md:order-1">
            <p className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 font-mono text-[11px] text-cyan-300">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              أول صاحب ذكاء اصطناعي تونسي — بالدارجة
            </p>
            <h1
              style={{ fontFamily: "Reem Kufi, Tajawal, sans-serif" }}
              className="mt-4 text-[30px] font-bold leading-[1.15] text-white md:text-[44px]"
            >
              أول صاحب <span className="text-cyan-400">ذكاء اصطناعي</span> تونسي
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-7 text-slate-300 md:text-[16px]">
              جينيو يفهمك بالدارجة، ينظّم خدمتك، يبرمج، يراقب السيرفرات، ويخلّيك تتحكم في دارك الذكية — من تليفونك ولا حاسوبك. خصوصية مضمونة، يعمل محلي ولا سحابي حسب اختيارك.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                to="/app"
                className="inline-flex items-center justify-center rounded-full bg-cyan-400 px-7 py-3 text-[15px] font-extrabold text-slate-900 shadow-[0_0_24px_rgba(34,211,238,0.5)] transition hover:bg-cyan-300 active:scale-95"
              >
                جرّب Genio توة ←
              </Link>
              <a href="#how" className="inline-flex items-center justify-center rounded-full border border-white/15 bg-white/5 px-6 py-3 text-[14px] font-bold text-white/90 backdrop-blur hover:bg-white/10">
                كيفاش يخدم؟
              </a>
            </div>
            <p className="mt-3 font-mono text-[11px] text-white/40">لا API key في المتصفح • يعمل أوفلاين Tier A • صوت و صورة</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="order-1 md:order-2 flex items-center justify-center"
          >
            <div className="relative">
              <div className="absolute -inset-6 -z-10 rounded-[2rem] bg-cyan-400/10 blur-[32px]" />
              <div className="absolute -inset-3 -z-10 rounded-[1.5rem] border border-cyan-400/20" />
              <img
                src={genioHero}
                alt="Genio Hero — Jebba rouge"
                className="h-[320px] w-[320px] md:h-[420px] md:w-[420px] object-contain drop-shadow-[0_0_36px_rgba(34,211,238,0.35)]"
                style={{
                  WebkitMaskImage: "radial-gradient(ellipse at 50% 55%, black 68%, transparent 82%)",
                  maskImage: "radial-gradient(ellipse at 50% 55%, black 68%, transparent 82%)",
                  mixBlendMode: "screen" as React.CSSProperties["mixBlendMode"],
                }}
              />
            </div>
          </motion.div>
        </div>
      </section>

      {/* HOW IT WORKS 3 steps */}
      <section id="how" className="relative z-10 mx-auto max-w-6xl px-5 py-10 md:px-8 scroll-mt-16">
        <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[22px] font-bold text-white md:text-[28px]">
          كيفاش يخدم — 3 خطوات
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {[
            { n: "1", t: "احكي بالدارجة", d: "اكتب ولا احكي: «نظّملي السيرفر» ولا «شغّل الضو» — جينيو يفهم عربي، دارجة، فرنسي وانجليزي." },
            { n: "2", t: "جينيو يخطط وينفّذ", d: "يحلّل طلبك، يستعمل الأدوات (bash, browser, ملفات) ويوريك كل خطوة في Matrix." },
            { n: "3", t: "شوف النتيجة", d: "يجيبك بالصوت والصورة، مع ملفات وجداول. كان تحب، يكمّل وحده في الخلفية." },
          ].map((s) => (
            <div key={s.n} className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-400 text-[14px] font-black text-slate-900">{s.n}</div>
              <h3 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="mt-3 text-[16px] font-bold text-white">
                {s.t}
              </h3>
              <p className="mt-2 text-[13px] leading-6 text-slate-300">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* TECH & PRIVACY */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-10 md:px-8">
        <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.05] to-white/[0.02] p-6 backdrop-blur md:p-8">
          <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[20px] font-bold text-white md:text-[24px]">
            تكنولوجيا وخصوصية
          </h2>
          <div className="mt-4 grid gap-6 md:grid-cols-2 text-[13px] leading-6 text-slate-300">
            <div>
              <p className="font-bold text-white">سحابي آمن</p>
              <p className="mt-1">Gemini 2.0 Flash عبر بوابة مشفّرة على السيرفر — المفتاح ما يخرجش من السيرفر، ما فماش API key في المتصفح ولا في الـ APK.</p>
              <p className="mt-3 font-bold text-white">يعمل محلي زادة</p>
              <p className="mt-1">كان السيرفر طايح، جينيو يكمّل على الجهاز (Tier A) — ما يوقفش.</p>
            </div>
            <div>
              <p className="font-bold text-white">صوت وصورة</p>
              <p className="mt-1">تعرّف على الصوت بالدارجة (ar-TN) وجهاً لوجه مع تتبّع الوجه. خصوصيتك محفوظة: الميكروفون والكاميرا بإذنك فقط.</p>
              <p className="mt-3 font-bold text-white">كود مفتوح وقابل للتوسيع</p>
              <p className="mt-1">أدوات جديدة، سكربتات، وحتى أصوات — كل شيء قابل للتخصيص.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ROADMAP 4 phases */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-10 md:px-8">
        <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[22px] font-bold text-white md:text-[28px]">
          خارطة الطريق — 4 مراحل
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {[
            { phase: "المرحلة 1", title: "Academy — كورسات الأشباح + معلّم Genio", desc: "كورسات مسجّلة خفية + جينيو يشرح، يسأل، ويصحّح — كأنّك مع أستاذ خاص 24/24.", color: "border-cyan-400/30 bg-cyan-400/10" },
            { phase: "المرحلة 2", title: "Education Edition — شرح ومراجعة بالدارجة", desc: "دروس ابتدائي وثانوي وجامعة بالدارجة التونسية — تلخيص، تمارين، ومراجعة ذكية.", color: "border-violet-400/30 bg-violet-400/10" },
            { phase: "المرحلة 3", title: "SysAdmin — Docker + VPN + سكربتات أتمتة", desc: "إدارة سيرفرات، حاويات، شبكات وVPN بضغطة — جينيو يكتب وينفّذ السكربتات.", color: "border-emerald-400/30 bg-emerald-400/10" },
            { phase: "المرحلة 4", title: "Daily Automation — n8n + أجهزة ذكية + صوت متنقّل", desc: "أتمتة يومية: n8n، منزل ذكي، أوامر صوتية وانت في الطريق.", color: "border-amber-400/30 bg-amber-400/10" },
          ].map((r) => (
            <div key={r.title} className={`rounded-2xl border p-5 backdrop-blur ${r.color}`}>
              <p className="font-mono text-[11px] font-bold tracking-widest text-white/60">{r.phase}</p>
              <h3 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="mt-1 text-[15px] font-bold text-white">
                {r.title}
              </h3>
              <p className="mt-2 text-[13px] leading-6 text-slate-200">{r.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FOUNDER */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-10 md:px-8">
        <div className="flex flex-col gap-6 rounded-2xl border border-amber-400/20 bg-amber-500/5 p-6 backdrop-blur md:flex-row md:items-center md:p-8">
          <img src={genioHero} alt="محمد عزمي كعنيش" className="h-24 w-24 shrink-0 rounded-2xl object-cover border border-amber-400/30 md:h-28 md:w-28" />
          <div>
            <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[18px] font-bold text-white md:text-[22px]">
              المؤسس — محمد عزمي كعنيش
            </h2>
            <p className="mt-2 max-w-2xl text-[13px] leading-7 text-slate-200">
              خبير بنية تحتية وأتمتة — سنين خبرة في Docker، الشبكات، وVPN. هدفه كسر الحاجز بين التونسي والتكنولوجيا: جينيو معمول باش أي تونسي — تلميذ، حرفي، مهندس — ينجم يستعمل الذكاء الاصطناعي بلغته، بثقته، وبطريقته.
            </p>
            <Link to="/about" className="mt-3 inline-flex rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-[12px] font-bold text-white hover:bg-white/10">
              اقرا أكثر →
            </Link>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="relative z-10 border-t border-white/10 bg-slate-950/40 px-5 py-8 text-center backdrop-blur md:px-8">
        <p style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[13px] font-bold tracking-wide text-white/80">
          جينيو — صُنع في تونس 🇹🇳 بكل حب
        </p>
        <p className="mt-1 font-mono text-[11px] text-white/40">© {new Date().getFullYear()} HiTechLab TN • genio.hitech.tn • خصوصيتك أولويتنا</p>
        <div className="mt-3 flex justify-center gap-3 text-[11px]">
          <Link to="/app" className="text-cyan-300 hover:text-cyan-200">ادخل</Link>
          <span className="text-white/20">•</span>
          <Link to="/about" className="text-white/60 hover:text-white">من نحن</Link>
          <span className="text-white/20">•</span>
          <a href="https://github.com/HiTechLabTN/genio" className="text-white/60 hover:text-white">GitHub</a>
        </div>
      </footer>
    </div>
  );
}
