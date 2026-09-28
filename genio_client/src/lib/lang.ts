/**
 * Minimal language alternatives (G6-B consolidation).
 * PRIMARY: Tunisian (default, RTL). SECONDARY: French, English (LTR).
 * Covers portal chrome + install CTA only; full content i18n is roadmap.
 * Persisted in localStorage; document.dir follows the language.
 */
export type Lang = "tu" | "fr" | "en";

const STRINGS: Record<Lang, Record<string, string>> = {
  tu: {
    nav_home: "جينيو",
    nav_explore: "استكشف", nav_security: "الأمان", nav_docs: "الوثائق",
    nav_download: "تحميل", nav_install: "ركّب Genio توّا", nav_app: "التطبيق",
    install_title: "ركّب Genio توّا", try: "جرّب Genio", docs: "الوثائق",
    offline: "ما فماش اتصال بالإنترنت", error: "صار مشكل",
    retry: "عاود المحاولة", task: "المهمّة", evidence: "الدليل",
    settings: "الإعدادات", assistant: "المساعد", start: "إبدا",
    tools_activity: "نشاط الأدوات",
  },
  fr: {
    nav_home: "Genio",
    nav_explore: "Explorer", nav_security: "Sécurité", nav_docs: "Docs",
    nav_download: "Télécharger", nav_install: "Installer Genio", nav_app: "App",
    install_title: "Installer Genio", try: "Essayer Genio", docs: "Docs",
    offline: "Pas de connexion Internet", error: "Un problème est survenu",
    retry: "Réessayer", task: "Tâche", evidence: "Preuves",
    settings: "Paramètres", assistant: "Assistant", start: "Démarrer",
    tools_activity: "Activité des outils",
  },
  en: {
    nav_home: "Genio",
    nav_explore: "Explore", nav_security: "Security", nav_docs: "Docs",
    nav_download: "Download", nav_install: "Install Genio now", nav_app: "App",
    install_title: "Install Genio now", try: "Try Genio", docs: "Docs",
    offline: "No Internet connection", error: "Something went wrong",
    retry: "Retry", task: "Task", evidence: "Evidence",
    settings: "Settings", assistant: "Assistant", start: "Start",
    tools_activity: "Tool activity",
  },
};

const KEY = "genio-lang";

export function getLang(): Lang {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "fr" || v === "en" || v === "tu") return v;
  } catch { /* ignore */ }
  return "tu";
}

export function setLang(lang: Lang): void {
  try {
    localStorage.setItem(KEY, lang);
  } catch { /* ignore */ }
  if (typeof document !== "undefined") {
    document.documentElement.lang = lang === "tu" ? "ar" : lang;
    document.documentElement.dir = lang === "tu" ? "rtl" : "ltr";
  }
}

export function t(lang: Lang, key: string): string {
  return STRINGS[lang][key] ?? STRINGS.tu[key] ?? key;
}

export function applyStoredLang(): void {
  const lang = getLang();
  if (typeof document !== "undefined") {
    document.documentElement.lang = lang === "tu" ? "ar" : lang;
    document.documentElement.dir = lang === "tu" ? "rtl" : "ltr";
  }
}
