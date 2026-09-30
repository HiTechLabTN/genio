import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import genioHero from "../assets/mascot/genio-hero.webp";
import IslamicPatterns from "../components/background/IslamicPatterns";
import { t, useLang, type Lang } from "../lib/lang";

function LandingLangSwitcher({ lang, onChange }: { lang: Lang; onChange: (l: Lang) => void }) {
  return (
    <div role="group" aria-label="Language / اللغة" className="flex items-center gap-1">
      {(["tu", "fr", "en"] as Lang[]).map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={lang === l}
          aria-label={l === "tu" ? "تونسي" : l === "fr" ? "Français" : "English"}
          onClick={() => onChange(l)}
          className={`rounded-full px-2 py-1 font-mono text-[11px] ${lang === l ? "bg-cyan-400 font-bold text-slate-900" : "text-white/60 hover:text-white"}`}
        >
          {l === "tu" ? "TN" : l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

export default function Landing() {
  const [lang, change] = useLang();
  const dir = lang === "tu" ? "rtl" : "ltr";
  const htmlLang = lang === "tu" ? "ar" : lang;
  return (
    <div dir={dir} lang={htmlLang} className="min-h-screen w-full bg-[#020B1E] text-slate-100" style={{ fontFamily: "Tajawal, system-ui, -apple-system, sans-serif" }}>
      {/* zellij .07 background */}
      <div className="pointer-events-none fixed inset-0 z-0 opacity-[0.07]">
        <IslamicPatterns />
      </div>

      {/* NAV */}
      <nav className="sticky top-0 z-20 flex h-[56px] items-center justify-between border-b border-white/10 bg-slate-950/60 px-4 backdrop-blur-md md:px-8">
        <div className="flex items-center gap-2">
          <img src={genioHero} alt="Genio" className="h-8 w-8 rounded-full object-cover border border-cyan-400/30" />
          <span style={{ fontFamily: "Reem Kufi, Tajawal, sans-serif" }} className="text-[18px] font-bold tracking-tight text-white">
            {t(lang, "landing.brand_tag")}
          </span>
          <span className="hidden md:inline rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 font-mono text-[10px] text-emerald-300">{t(lang, "landing.live")}</span>
        </div>
        <div className="flex items-center gap-2">
          <LandingLangSwitcher lang={lang} onChange={change} />
          <Link to="/about" className="hidden md:inline rounded-full px-3 py-1.5 text-[13px] text-white/70 hover:text-white">{t(lang, "landing.founder")}</Link>
          <Link to="/app" className="rounded-full bg-cyan-400 px-4 py-1.5 text-[13px] font-bold text-slate-900 shadow-[0_0_16px_rgba(34,211,238,0.4)] hover:bg-cyan-300">{t(lang, "landing.enter_app")}</Link>
        </div>
      </nav>

      {/* HERO */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-16">
        <div className="grid gap-8 md:grid-cols-2 md:items-center">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="order-2 md:order-1">
            <p className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 font-mono text-[11px] text-cyan-300">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              {t(lang, "landing.hero_badge")}
            </p>
            <h1
              style={{ fontFamily: "Reem Kufi, Tajawal, sans-serif" }}
              className="mt-4 text-[30px] font-bold leading-[1.15] text-white md:text-[44px]"
            >
              {t(lang, "landing.hero_title_a")} <span className="text-cyan-400">{t(lang, "landing.hero_title_b")}</span> {t(lang, "landing.hero_title_c")}
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-7 text-slate-300 md:text-[16px]">
              {t(lang, "landing.hero_sub")}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                to="/app"
                className="inline-flex items-center justify-center rounded-full bg-cyan-400 px-7 py-3 text-[15px] font-extrabold text-slate-900 shadow-[0_0_24px_rgba(34,211,238,0.5)] transition hover:bg-cyan-300 active:scale-95"
              >
                {t(lang, "landing.cta_try")}
              </Link>
              <Link
                to="/install"
                className="inline-flex items-center justify-center rounded-full border border-cyan-400/40 bg-cyan-400/10 px-7 py-3 text-[15px] font-extrabold text-cyan-200 transition hover:bg-cyan-400/20 active:scale-95"
              >
                {t(lang, "landing.cta_install")}
              </Link>
              <a href="#how" className="inline-flex items-center justify-center rounded-full border border-white/15 bg-white/5 px-6 py-3 text-[14px] font-bold text-white/90 backdrop-blur hover:bg-white/10">
                {t(lang, "landing.cta_how")}
              </a>
            </div>
            <nav aria-label="Product" className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-[12px]">
              <Link to="/explore" className="text-cyan-300/90 hover:text-cyan-200">{t(lang, "landing.product_explore")}</Link>
              <Link to="/download" className="text-cyan-300/90 hover:text-cyan-200">{t(lang, "landing.product_download")}</Link>
              <Link to="/install" className="text-cyan-300/90 hover:text-cyan-200">{t(lang, "landing.product_install")}</Link>
              <Link to="/docs" className="text-cyan-300/90 hover:text-cyan-200">{t(lang, "landing.product_docs")}</Link>
              <Link to="/security" className="text-cyan-300/90 hover:text-cyan-200">{t(lang, "landing.product_security")}</Link>
            </nav>
            <p className="mt-3 font-mono text-[11px] text-white/40">{t(lang, "landing.no_key_note")}</p>
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
                alt={t(lang, "landing.alt_hero")}
                className="genio-hero-float h-[320px] w-[320px] md:h-[420px] md:w-[420px] object-contain drop-shadow-[0_0_36px_rgba(34,211,238,0.35)]"
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
          {t(lang, "landing.how_title")}
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {[
            { n: "1", t: t(lang, "landing.how_1t"), d: t(lang, "landing.how_1d") },
            { n: "2", t: t(lang, "landing.how_2t"), d: t(lang, "landing.how_2d") },
            { n: "3", t: t(lang, "landing.how_3t"), d: t(lang, "landing.how_3d") },
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
            {t(lang, "landing.tech_title")}
          </h2>
          <div className="mt-4 grid gap-6 md:grid-cols-2 text-[13px] leading-6 text-slate-300">
            <div>
              <p className="font-bold text-white">{t(lang, "landing.tech_1t")}</p>
              <p className="mt-1">{t(lang, "landing.tech_1d")}</p>
              <p className="mt-3 font-bold text-white">{t(lang, "landing.tech_2t")}</p>
              <p className="mt-1">{t(lang, "landing.tech_2d")}</p>
            </div>
            <div>
              <p className="font-bold text-white">{t(lang, "landing.tech_3t")}</p>
              <p className="mt-1">{t(lang, "landing.tech_3d")}</p>
              <p className="mt-3 font-bold text-white">{t(lang, "landing.tech_4t")}</p>
              <p className="mt-1">{t(lang, "landing.tech_4d")}</p>
            </div>
          </div>
        </div>
      </section>

      {/* ROADMAP 4 phases */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-10 md:px-8">
        <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[22px] font-bold text-white md:text-[28px]">
          {t(lang, "landing.road_title")}
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {[
            { phase: t(lang, "landing.road_1p"), title: t(lang, "landing.road_1t"), desc: t(lang, "landing.road_1d"), color: "border-cyan-400/30 bg-cyan-400/10" },
            { phase: t(lang, "landing.road_2p"), title: t(lang, "landing.road_2t"), desc: t(lang, "landing.road_2d"), color: "border-violet-400/30 bg-violet-400/10" },
            { phase: t(lang, "landing.road_3p"), title: t(lang, "landing.road_3t"), desc: t(lang, "landing.road_3d"), color: "border-emerald-400/30 bg-emerald-400/10" },
            { phase: t(lang, "landing.road_4p"), title: t(lang, "landing.road_4t"), desc: t(lang, "landing.road_4d"), color: "border-amber-400/30 bg-amber-400/10" },
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
          <img src={genioHero} alt={t(lang, "landing.alt_founder")} className="h-24 w-24 shrink-0 rounded-2xl object-cover border border-amber-400/30 md:h-28 md:w-28" />
          <div>
            <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[18px] font-bold text-white md:text-[22px]">
              {t(lang, "landing.founder_title")}
            </h2>
            <p className="mt-2 max-w-2xl text-[13px] leading-7 text-slate-200">
              {t(lang, "landing.founder_body")}
            </p>
            <Link to="/about" className="mt-3 inline-flex rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-[12px] font-bold text-white hover:bg-white/10">
              {t(lang, "landing.founder_more")}
            </Link>
          </div>
        </div>
      </section>

      {/* PLATFORM MATRIX — factual, from product-data (G6-A) */}
      <section aria-label="Platform support" className="relative z-10 mx-auto max-w-6xl px-5 py-10 md:px-8">
        <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-center text-[20px] font-bold text-white md:text-[24px]">
          {t(lang, "landing.platform_title")}
        </h2>
        <div className="mx-auto mt-6 grid max-w-4xl gap-3 sm:grid-cols-2">
          {[
            [t(lang, "landing.platform_linux"), t(lang, "landing.platform_linux_ok"), true],
            [t(lang, "landing.platform_docker"), t(lang, "landing.platform_docker_ok"), true],
            [t(lang, "landing.platform_other"), t(lang, "landing.platform_other_no"), false],
            [t(lang, "landing.platform_os"), t(lang, "landing.platform_os_soon"), false],
          ].map(([label, state, ok]) => (
            <div key={label as string} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3">
              <span className="text-[13px] font-bold text-white">{label}</span>
              <span className={`font-mono text-[11px] ${ok ? "text-emerald-300" : "text-white/50"}`}>{state}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 text-center">
          <Link to="/download" className="text-[13px] font-bold text-cyan-300 hover:text-cyan-200">{t(lang, "landing.platform_all")}</Link>
        </div>
      </section>

      {/* INSTALL 3 STEPS — real commands, checksums first */}
      <section aria-label="Install" className="relative z-10 mx-auto max-w-6xl px-5 py-10 md:px-8">
        <h2 style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-center text-[20px] font-bold text-white md:text-[24px]">
          {t(lang, "landing.install_title")}
        </h2>
        <ol className="mx-auto mt-6 grid max-w-4xl gap-3 md:grid-cols-3">
          {[
            ["1", t(lang, "landing.install_1t"), t(lang, "landing.install_1d")],
            ["2", t(lang, "landing.install_2t"), t(lang, "landing.install_2d")],
            ["3", t(lang, "landing.install_3t"), t(lang, "landing.install_3d")],
          ].map(([n, title, d]) => (
            <li key={n} className="rounded-xl border border-white/10 bg-white/5 p-4">
              <span className="font-mono text-[11px] text-cyan-300">STEP {n}</span>
              <p className="mt-1 text-[14px] font-bold text-white">{title}</p>
              <p className="mt-1 text-[12px] text-white/60">{d}</p>
            </li>
          ))}
        </ol>
        <div className="mt-4 text-center">
          <Link to="/install" className="text-[13px] font-bold text-cyan-300 hover:text-cyan-200">{t(lang, "landing.install_more")}</Link>
        </div>
      </section>

      {/* FOOTER */}      <footer className="relative z-10 border-t border-white/10 bg-slate-950/40 px-5 py-8 text-center backdrop-blur md:px-8">
        <p style={{ fontFamily: "Reem Kufi, sans-serif" }} className="text-[13px] font-bold tracking-wide text-white/80">
          {t(lang, "landing.footer_made")}
        </p>
        <p className="mt-1 font-mono text-[11px] text-white/40">© {new Date().getFullYear()} HiTechLab TN • genio.hitech.tn • {t(lang, "landing.footer_rights")}</p>
        <div className="mt-3 flex justify-center gap-3 text-[11px]">
          <Link to="/app" className="text-cyan-300 hover:text-cyan-200">{t(lang, "landing.footer_enter")}</Link>
          <span className="text-white/20">•</span>
          <Link to="/about" className="text-white/60 hover:text-white">{t(lang, "landing.footer_about")}</Link>
          <span className="text-white/20">•</span>
          <a href="https://github.com/HiTechLabTN/genio" className="text-white/60 hover:text-white">GitHub</a>
        </div>
      </footer>
      <style>{`@keyframes genio-hero-float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        .genio-hero-float { animation: genio-hero-float 5s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) { .genio-hero-float { animation: none; } }`}</style>
    </div>
  );
}
