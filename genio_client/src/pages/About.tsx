import { Link } from "react-router-dom";
import genioHero from "../assets/mascot/genio-hero.webp";
import IslamicPatterns from "../components/background/IslamicPatterns";

export default function About() {
  return (
    <div dir="rtl" lang="ar" className="min-h-screen w-full bg-[#020B1E] text-slate-100" style={{ fontFamily: "Tajawal, system-ui, sans-serif" }}>
      <div className="pointer-events-none fixed inset-0 z-0 opacity-[0.07]">
        <IslamicPatterns />
      </div>
      <nav className="sticky top-0 z-20 flex h-[56px] items-center justify-between border-b border-white/10 bg-slate-950/60 px-4 backdrop-blur-md md:px-8">
        <Link to="/" className="flex items-center gap-2">
          <img src={genioHero} alt="Genio" className="h-8 w-8 rounded-full object-cover border border-cyan-400/30" />
          <span style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[18px] font-bold text-white">جينيو</span>
        </Link>
        <div className="flex items-center gap-2">
          <Link to="/" className="rounded-full px-3 py-1.5 text-[13px] text-white/70 hover:text-white">الرئيسية</Link>
          <Link to="/app" className="rounded-full bg-cyan-400 px-4 py-1.5 text-[13px] font-bold text-slate-900">جرّب Genio</Link>
        </div>
      </nav>

      <section className="relative z-10 mx-auto max-w-3xl px-5 py-10 md:px-8 md:py-12">
        <p className="font-mono text-[11px] tracking-[0.18em] text-cyan-300">المؤسس • FOUNDER</p>
        <h1 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="mt-2 text-[28px] font-bold leading-tight text-white md:text-[36px]">
          محمد عزمي كعنيش
        </h1>
        <p className="mt-1 text-[14px] font-bold text-amber-300">خبير بنية تحتية وأتمتة — HiTechLab TN</p>

        <div className="mt-6 flex flex-col gap-6 md:flex-row md:items-start">
          <img src={genioHero} alt="محمد عزمي كعنيش" className="h-32 w-32 shrink-0 rounded-2xl object-cover border border-amber-400/20 md:h-40 md:w-40" />
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur">
            <p className="text-[14px] leading-7 text-slate-200">
              هدفي كسر الحاجز بين التونسي والتكنولوجيا. سنين نخدم في البنية التحتية، الـ Docker، الشبكات والـ VPN، وشفت قدّاش برشا توانسة — طلبة، حرفيين، إداريين — يحبّو يستعملو الذكاء الاصطناعي لكن اللغة، التعقيد، والخصوصية يوقفوهم.
            </p>
            <p className="mt-3 text-[14px] leading-7 text-slate-200">
              جينيو معمول باش يحكي بلغتك (دارجة، عربي، فرنسي)، يفهم ثقافتك، ويخدم معاك كصاحب — موش كأداة باردة. من تنظيم السيرفرات إلى مراجعة الدروس إلى تشغيل الدار الذكية.
            </p>
          </div>
        </div>

        <div className="mt-8 space-y-6">
          <section>
            <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[18px] font-bold text-white">
              الرؤية
            </h2>
            <p className="mt-2 text-[14px] leading-7 text-slate-300">
              تونس فيها طاقات كبيرة، لكن الأدوات العالمية ما تحكيش دارجتنا وما تفهمش واقعنا. جينيو يبدا بصاحب ذكي يفهمك، وبعد يتحوّل لمنصة تعليم (Academy + Education Edition)، ثم لمساعد SysAdmin، وأخيراً لأتمتة يومية مع n8n والأجهزة الذكية — كلّه بصوتك وانت في الطريق.
            </p>
          </section>

          <section className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-5">
            <h3 className="font-bold text-cyan-300">ماذا يميّز جينيو؟</h3>
            <ul className="mt-2 list-disc space-y-1 pr-5 text-[13px] leading-6 text-slate-200">
              <li>يتكلم دارجة تونسية بطلاقة ويحوّلها لعربية/فرنسية عند الحاجة</li>
              <li>يعمل محلي (Tier A) أو سحابي (Gemini 2.0 Flash) حسب اختيارك — مفتاحك لا يخرج من السيرفر</li>
              <li>يتعامل مع ملفات، سكربتات، متصفح، وصوت/صورة — موش مجرد دردشة</li>
              <li>مفتوح للتوسيع: أضف أدواتك، سكربتاتك، وأجهزتك</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[18px] font-bold text-white">
              خارطة الطريق المختصرة
            </h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="font-mono text-[11px] text-cyan-300">1 • Academy</p>
                <p className="text-[13px] font-bold text-white">كورسات الأشباح + معلّم Genio</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="font-mono text-[11px] text-violet-300">2 • Education</p>
                <p className="text-[13px] font-bold text-white">شرح ومراجعة بالدارجة</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="font-mono text-[11px] text-emerald-300">3 • SysAdmin</p>
                <p className="text-[13px] font-bold text-white">Docker + VPN + سكربتات</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="font-mono text-[11px] text-amber-300">4 • Daily</p>
                <p className="text-[13px] font-bold text-white">n8n + منزل ذكي + صوت</p>
              </div>
            </div>
          </section>

          <div className="flex flex-wrap gap-3 pt-2">
            <Link to="/app" className="rounded-full bg-cyan-400 px-6 py-2.5 text-[14px] font-black text-slate-900">جرّب Genio توة</Link>
            <Link to="/" className="rounded-full border border-white/15 bg-white/5 px-6 py-2.5 text-[14px] font-bold text-white">العودة للرئيسية</Link>
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/10 bg-slate-950/40 px-5 py-6 text-center md:px-8">
        <p className="font-mono text-[11px] text-white/40">© {new Date().getFullYear()} HiTechLab TN — صُنع في تونس 🇹🇳</p>
      </footer>
    </div>
  );
}
