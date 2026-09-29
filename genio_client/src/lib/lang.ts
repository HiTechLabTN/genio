/**
 * Centralized language layer — single source of truth for user-facing strings.
 * PRIMARY: Tunisian Derja (default, RTL). SECONDARY: French, English (LTR).
 * Persisted in localStorage; document.dir follows the language.
 * Technical identifiers, protocol names and code constants stay untranslated.
 */
import { useEffect, useState } from "react";

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
    // auth.*
    "auth.title": "أهلا بيك في Genio",
    "auth.subtitle": "باش تبدأ تحكي معايا، ادخل بحساب Google ولا كمّل من غير حساب.",
    "auth.why": "الدخول يخوّلك تستعمل السحاب. من غير دخول تنجم تستعمل Genio على جهازك.",
    "auth.google": "ادخل بـ Google",
    "auth.continue_google": "كمّل بـ Google",
    "auth.continue": "كمّل",
    "auth.skip": "كمّل من غير حساب",
    "auth.signed_in": "داخل توا — انقر كمّل",
    "auth.agree": "بمواصلتك انت توافق على استعمال Genio. المفتاح يتخزن كان في جهازك.",
    "auth.checking": "نتحققو...",
    // shell.* (unified L1 + panels)
    "shell.ready": "Genio حاضر",
    "shell.greeting": "عسلامة! أنا Genio",
    "shell.listening": "Genio يسمع فيك",
    "shell.understanding": "Genio قاعد يفهم في طلبك",
    "shell.thinking": "Genio يخمّم",
    "shell.planning": "Genio يخطط",
    "shell.explaining": "Genio يجاوب فيك",
    "shell.executing": "Genio قاعد يخدم على مهمّتك",
    "shell.waiting": "Genio يستنى",
    "shell.asking": "Genio يستنى في ردّك",
    "shell.success": "كمّلت المهمّة",
    "shell.warning": "رد بالك، فما حاجة",
    "shell.error": "صار مشكل",
    "shell.recovering": "Genio قاعد يصلّح",
    "shell.celebrating": "برافو، كمّلت!",
    "shell.sleeping": "Genio راقد",
    "shell.disconnected": "تقطع الاتصال",
    "shell.attention": "Genio يحب انتباهك",
    "shell.current_task": "المهمّة الحالية",
    "shell.no_task": "ما فماش مهمّة. ابعث رسالة باش تبدأ.",
    "shell.resources": "الموارد",
    "shell.details": "تفاصيل تقنية",
    "shell.result": "النتيجة",
    "shell.events": "الأحداث",
    "shell.cancel": "ألغي",
    "shell.reconnect": "عاود الاتصال",
    "shell.unavailable": "غير متوفّر",
    "shell.offline": "ما فماش اتصال — الوثائق والإعدادات والتفضيلات تخدم. الذكاء الاصطناعي يحتاج اتصال.",
    "shell.connection_lost": "تقطع الاتصال",
    "shell.details_docs": "تفاصيل في الوثائق",
    "shell.advanced_on": "متقدّم مفعّل",
    "shell.opt_in": "اختياري",
    "shell.hide_advanced": "خبّي المتقدّم",
    "shell.show_advanced": "وريني المتقدّم",
    // input.*
    "input.placeholder": "ابعث لـ Genio… (Enter باش تبعث، Shift+Enter باش تدخل سطر جديد)",
    "input.attach": "رفق ملفّات",
    "input.mic": "اسمع",
    "input.stop": "وقّف التسجيل",
    "input.recording": "جاري التسجيل",
    "input.send": "ابعث",
    "input.cancel": "ألغي",
    "input.drop": "حطّ ملفّات هنا باش ترفقهم",
    "input.listening": "Genio يسمع فيك — احكي توا",
    "input.listen": "اسمع",
    "input.listen_label": "اسمع",
    "input.stop_recording": "وقّف التسجيل",
    "input.live_transcription": "كلّم… التحويل الحيّ يشتغل",
    "input.release_to_send": "حرّر باش تبعث عبر Web Audio",
    "input.send_label": "جاهز",
    // errors.*
    "errors.generic": "صار مشكل غير متوقع. عاود جرّب، ولو تكرر ابعث التفاصيل.",
    "errors.network": "ما فماش اتصال. تحقق من الإنترنت وعاود جرّب.",
    "errors.auth": "لازم الدخول باش تكمّل. ادخل ولا كمّل من غير حساب.",
    "errors.mic": "المايكرو ما لقاهش",
    "errors.server": "السيرفر ما جاوبش. عاود جرّب بعد شوية.",
    "errors.timeout": "طوّل برشا وما جاش رد. عاود جرّب.",
    "errors.tech_details": "تفاصيل تقنية",
    "errors.cloud_auth": "سجّل بـ Google باش تكمّل في السحاب",
    "errors.cloud_fail": "مشكل في الاتصال بالسحاب — عاود جرّب",
    "errors.cloud_retry": "عاود جرّب",
    "errors.google_signin": "ادخل بـ Google",
    "errors.mic_unavailable": "المايكرو موش متوفّر. تحقق من إذن المتصفح.",
    "errors.google_auth_failed": "الدخول بـ Google فشل. عاود جرّب.",
    "errors.recording": "جاري التسجيل",
    "errors.live_transcription": "التحويل الحيّ يشتغل…",
    "errors.release_to_send": "حرّر باش تبعث",
    "errors.close_chat": "سكّر الدردشة",
    "errors.open_chat": "افتح الدردشة",
    // status.*
    "status.connected": "متصل",
    "status.connecting": "قاعد يتصل...",
    "status.disconnected": "مقطوع",
    "status.ready": "حاضر",
    "status.working": "قاعد يخدم",
    "status.done": "كمّل",
    // task.*
    "task.title": "المهمّة الحالية",
    "task.step": "الخطوة الحالية",
    "task.steps": "الخطوات",
    "task.tool": "الأداة",
    "task.duration": "المدة",
    "task.status": "الحالة",
    "task.cancel": "ألغي المهمّة",
    "task.cancel_requested": "طلب الإلغاء تبعث، نستنى التأكيد...",
    "task.cancelled": "تلغات المهمّة",
    "task.queued": "في الانتظار",
    "task.running": "قاعدة تخدم",
    "task.waiting": "تستنى",
    "task.completed": "كمّلت",
    "task.failed": "فشلت",
    "task.elapsed": "المدة (محسوبة في جهازك)",
    // settings.*
    "settings.density": "الكثافة المعرفية",
    "settings.ambient": "المؤثّرات المحيطة",
    // density.*
    "density.simple": "بسيط",
    "density.detailed": "مفصّل",
    "density.advanced": "متقدّم",
    // ambient.*
    "ambient.glow": "توهّج/جسيمات",
    "ambient.reduced": "تقليل الحركة",
    "ambient.note": "تنبيهات الأمان وحالة المهمّة والأخطاء ما تتطفاش أبدا بالإعدادات هاذي.",
    // events.*
    "events.empty": "ما فماش أحداث توا.",
    // tool.*
    "tool.activity": "نشاط الأدوات",
    "tool.evidence_unavailable": "ما فماش دليل متوفّر",
    // a11y.*
    "a11y.skip": "تخطى للمحتوى",
    "a11y.close": "سكّر",
    "a11y.menu": "افتح القائمة",
    "a11y.copy": "انسخ الأمر",
    "a11y.copied": "تنسخ ✓",
    // onboarding.*
    "onboarding.welcome": "مرحبا بيك في Genio",
    "onboarding.start": "إبدا",
    "onboarding.skip": "تخطى",
    // permissions.*
    "perm.checking": "نتحقّقو من إمكانيّات الجهاز...",
    "perm.title": "الأذونات والعتاد",
    "perm.subtitle": "Genio يحتاج برشا أذونات باش يخدم ممتاز على الأندرويد",
    "perm.camera": "الكاميرا",
    "perm.camera_desc": "تتبّع الوجه بالكاميرا الأمامية (ابتسامة الشاشة)",
    "perm.microphone": "المايكرو",
    "perm.microphone_desc": "إدخال الصوت بالتونسي (تحويل الكلام لنصّ)",
    "perm.storage": "التخزين",
    "perm.storage_desc": "الملفّات المرفقة وقراءة الوسائط",
    "perm.network": "الشبكة",
    "perm.network_desc": "الاتصال بالإنترنت",
    "perm.grant_all": "أذن لكلّ",
    "perm.reverify": "عاود التحقّق",
    "perm.continue_anyway": "كمّل من غير أذونات",
    "perm.continue": "كمّل",
    "perm.tauri_note": "أندرويد Tauri يفرض أذونات المانيفست: CAMERA, RECORD_AUDIO, INTERNET, ACCESS_NETWORK_STATE, READ_MEDIA_*.",
    "perm.skip": "تخطّى التأهيل",
    // header.*
    "header.toggle_drawer": "افتح القائمة",
    "header.selfie_mode": "SELFIE MODE",
    "header.toggle_selfie": "تبديل تتبّع الوجه",
    "header.stop": "وقّف",
    "header.disconnect": "تقطع",
    "header.thinking": "خمّم...",
    "header.executing": "ينفّذ: ",
    "header.completed": "كمّل",
    "header.stale": "متوقّف",
    "header.telemetry_paused": "البيانات متوقّفة — السيرفر مشغول",
    // mascot.*
    "mascot.listening": "يسمع...",
    "mascot.speaking": "يحكي...",
    "mascot.tap_to_speak": "اضغط باش تحكي",
    "mascot.gesture_note": "حركات تعلّمها منك",
    "mascot.technical_mode": "الوضع التقني",
    // telemetry.*
    "telemetry.offline": "🔴 غير متصل",
    "telemetry.thinking": "🟡 جينيو يخمّم...",
    "telemetry.streaming": "🔵 يجاوب",
    "telemetry.ready": "🟢 متصل",
    // app.* (App shell mode buttons + background actions)
    "app.mode_technique": "الوضع التقني",
    "app.mode_mascot": "وضع الماسكوت",
    "app.mode_unified": "الوضع الموحّد",
    "app.mode_mascot_title": "ارجع للماسكوت على كامل الشاشة",
    "app.mode_unified_title": "عرض موحّد: محادثة وحضور ومهمّة",
    "app.kill_agent": "وقّف الوكيل",
    "app.disconnect": "افصل الاتصال",
    // error boundary fallback
    "boundary.crash": "المشهد طاح — وضع الأمان يخدم.",
    // permission status values (device messages mapped, never raw English)
    "perm.status_granted": "مسموح",
    "perm.status_online": "متصل",
    "perm.status_offline": "موش متصل",
    "perm.status_denied": "مرفوض — شوف إعدادات الجهاز",
    "perm.status_denied_retry": "مرفوض — تنجم تعاود تطلب",
    "perm.status_unavailable": "غير متوفّر على الجهاز هذا",
    // chat panel (FAB)
    "chat.title": "دردشة Genio",
    "chat.empty": "✨ Genio يسمع — اكتب رسالة ولا احكي ✨",
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
    "auth.title": "Bienvenue sur Genio",
    "auth.subtitle": "Pour commencer, connectez-vous avec Google ou continuez sans compte.",
    "auth.why": "La connexion donne accès au cloud. Sans compte, Genio reste utilisable sur votre appareil.",
    "auth.google": "Se connecter avec Google",
    "auth.continue_google": "Continuer avec Google",
    "auth.continue": "Continuer",
    "auth.skip": "Continuer sans compte",
    "auth.signed_in": "Déjà connecté — touchez Continuer",
    "auth.agree": "En continuant vous acceptez l'utilisation de Genio. La clé reste sur votre appareil.",
    "auth.checking": "Vérification...",
    "shell.ready": "Genio est prêt",
    "shell.greeting": "Salut ! C'est Genio",
    "shell.listening": "Genio vous écoute",
    "shell.understanding": "Genio comprend votre demande",
    "shell.thinking": "Genio réfléchit",
    "shell.planning": "Genio planifie",
    "shell.explaining": "Genio répond",
    "shell.executing": "Genio travaille sur votre tâche",
    "shell.waiting": "Genio patiente",
    "shell.asking": "Genio attend votre réponse",
    "shell.success": "Tâche terminée",
    "shell.warning": "Attention, un point à voir",
    "shell.error": "Un problème est survenu",
    "shell.recovering": "Genio répare",
    "shell.celebrating": "Bravo, terminé !",
    "shell.sleeping": "Genio est en veille",
    "shell.disconnected": "Connexion perdue",
    "shell.attention": "Genio a besoin de vous",
    "shell.current_task": "Tâche actuelle",
    "shell.no_task": "Aucune tâche. Envoyez un message pour commencer.",
    "shell.resources": "Ressources",
    "shell.details": "Détails techniques",
    "shell.result": "Résultat",
    "shell.events": "Événements",
    "shell.cancel": "Annuler",
    "shell.reconnect": "Reconnecter",
    "shell.unavailable": "Indisponible",
    "shell.offline": "Hors ligne — navigation, docs, paramètres restent utilisables. L'IA nécessite une connexion.",
    "shell.connection_lost": "Connexion perdue",
    "shell.details_docs": "Détails dans les docs",
    "shell.advanced_on": "Avancé activé",
    "shell.opt_in": "Optionnel",
    "shell.hide_advanced": "Masquer avancé",
    "shell.show_advanced": "Afficher avancé",
    "input.placeholder": "Envoyer à Genio… (Entrée pour envoyer, Maj+Entrée pour un retour à la ligne)",
    "input.attach": "Joindre des fichiers",
    "input.mic": "Parler",
    "input.stop": "Arrêter l'enregistrement",
    "input.recording": "Enregistrement en cours...",
    "input.send": "Envoyer",
    "input.cancel": "Annuler",
    "input.drop": "Déposez les fichiers ici pour les joindre",
    "input.listening": "Genio vous écoute — parlez",
    "input.listen": "Écouter",
    "input.listen_label": "ÉCOUTER",
    "input.stop_recording": "Arrêter l'enregistrement",
    "input.live_transcription": "parlez… transcription en direct",
    "input.release_to_send": "relâchez pour envoyer via Web Audio",
    "input.send_label": "PRÊT",
    "errors.generic": "Erreur inattendue. Réessayez, puis envoyez les détails si ça persiste.",
    "errors.network": "Pas de connexion. Vérifiez Internet et réessayez.",
    "errors.auth": "Connexion requise pour continuer.",
    "errors.mic": "Microphone indisponible",
    "errors.server": "Le serveur ne répond pas. Réessayez dans un moment.",
    "errors.timeout": "Trop long sans réponse. Réessayez.",
    "errors.tech_details": "Détails techniques",
    "errors.cloud_auth": "Connectez-vous avec Google pour continuer dans le cloud",
    "errors.cloud_fail": "Problème de connexion au cloud — réessayez",
    "errors.cloud_retry": "Réessayer",
    "errors.google_signin": "Se connecter avec Google",
    "errors.mic_unavailable": "Microphone indisponible. Vérifiez les autorisations du navigateur.",
    "errors.google_auth_failed": "Connexion Google échouée. Réessayez.",
    "errors.recording": "Enregistrement",
    "errors.live_transcription": "Transcription en direct…",
    "errors.release_to_send": "Relâchez pour envoyer",
    "errors.close_chat": "Fermer le chat",
    "errors.open_chat": "Ouvrir le chat",
    "status.connected": "Connecté",
    "status.connecting": "Connexion...",
    "status.disconnected": "Déconnecté",
    "status.ready": "Prêt",
    "status.working": "En cours",
    "status.done": "Terminé",
    "task.title": "Tâche actuelle",
    "task.step": "Étape actuelle",
    "task.steps": "Étapes",
    "task.tool": "Outil",
    "task.duration": "Durée",
    "task.status": "État",
    "task.cancel": "Annuler la tâche",
    "task.cancel_requested": "Annulation demandée, en attente de confirmation...",
    "task.cancelled": "Tâche annulée",
    "task.queued": "En file",
    "task.running": "En cours",
    "task.waiting": "En attente",
    "task.completed": "Terminée",
    "task.failed": "Échouée",
    "task.elapsed": "Durée (mesurée sur votre appareil)",
    "settings.density": "Densité d'information",
    "settings.ambient": "Effets ambiants",
    "density.simple": "Simple",
    "density.detailed": "Détaillée",
    "density.advanced": "Avancée",
    "ambient.glow": "Lueur/particules",
    "ambient.reduced": "Mouvement réduit",
    "ambient.note": "Alertes, état des tâches et erreurs ne sont jamais désactivés par ces réglages.",
    "events.empty": "Aucun événement pour le moment.",
    "tool.activity": "Activité des outils",
    "tool.evidence_unavailable": "Aucune preuve disponible",
    "a11y.skip": "Aller au contenu",
    "a11y.close": "Fermer",
    "a11y.menu": "Ouvrir le menu",
    "a11y.copy": "Copier la commande",
    "a11y.copied": "Copié ✓",
    "onboarding.welcome": "Bienvenue sur Genio",
    "onboarding.start": "Démarrer",
    "onboarding.skip": "Passer",
    // permissions.*
    "perm.checking": "Vérification des capacités de l'appareil...",
    "perm.title": "Autorisations et matériel",
    "perm.subtitle": "Genio a besoin de quelques autorisations pour fonctionner nativement sur Android",
    "perm.camera": "Caméra",
    "perm.camera_desc": "Suivi facial par caméra frontale (regard de l'avatar)",
    "perm.microphone": "Microphone",
    "perm.microphone_desc": "Saisie vocale native (STT Darija)",
    "perm.storage": "Stockage",
    "perm.storage_desc": "Pièces jointes et READ_MEDIA_*",
    "perm.network": "Réseau",
    "perm.network_desc": "INTERNET et ACCESS_NETWORK_STATE",
    "perm.grant_all": "Tout autoriser",
    "perm.reverify": "Revérifier",
    "perm.continue_anyway": "Continuer sans autorisations",
    "perm.continue": "Continuer",
    "perm.tauri_note": "Tauri Android impose aussi les permissions du manifest : CAMERA, RECORD_AUDIO, INTERNET, ACCESS_NETWORK_STATE, READ_MEDIA_*.",
    "perm.skip": "Passer l'onboarding",
    // header.*
    "header.toggle_drawer": "Ouvrir le tiroir",
    "header.selfie_mode": "MODE SELFIE",
    "header.toggle_selfie": "Basculer le suivi facial",
    "header.stop": "Arrêter",
    "header.disconnect": "Déconnecter",
    "header.thinking": "Réflexion...",
    "header.executing": "Exécution : ",
    "header.completed": "Terminé",
    "header.stale": "Périmé",
    "header.telemetry_paused": "Télémétrie en pause — serveur occupé",
    // mascot.*
    "mascot.listening": "écoute...",
    "mascot.speaking": "parle...",
    "mascot.tap_to_speak": "Touchez pour parler",
    "mascot.gesture_note": "gestes appris pour cet utilisateur",
    "mascot.technical_mode": "Mode technique",
    // telemetry.*
    "telemetry.offline": "🔴 Hors ligne",
    "telemetry.thinking": "🟡 Genio réfléchit...",
    "telemetry.streaming": "🔵 Répond",
    "telemetry.ready": "🟢 Connecté",
    // app.* (App shell mode buttons + background actions)
    "app.mode_technique": "Mode technique",
    "app.mode_mascot": "Mode mascotte",
    "app.mode_unified": "Mode unifié",
    "app.mode_mascot_title": "Retour à la mascotte plein écran",
    "app.mode_unified_title": "Vue unifiée : conversation, présence et tâche",
    "app.kill_agent": "Arrêter l'agent",
    "app.disconnect": "Déconnecter",
    // error boundary fallback
    "boundary.crash": "La scène a planté — mode de secours actif.",
    // permission status values (device messages mapped, never raw English)
    "perm.status_granted": "Autorisé",
    "perm.status_online": "En ligne",
    "perm.status_offline": "Hors ligne",
    "perm.status_denied": "Refusé — voir réglages système",
    "perm.status_denied_retry": "Refusé — redemandable",
    "perm.status_unavailable": "Indisponible sur cet appareil",
    // chat panel (FAB)
    "chat.title": "Discussion Genio",
    "chat.empty": "✨ Genio écoute — écrivez ou parlez ✨",
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
    "auth.title": "Welcome to Genio",
    "auth.subtitle": "To get started, sign in with Google or continue without an account.",
    "auth.why": "Signing in unlocks the cloud. Without an account Genio still works on your device.",
    "auth.google": "Sign in with Google",
    "auth.continue_google": "Continue with Google",
    "auth.continue": "Continue",
    "auth.skip": "Continue without an account",
    "auth.signed_in": "Already signed in — tap Continue",
    "auth.agree": "By continuing you accept using Genio. The key stays on your device.",
    "auth.checking": "Checking...",
    "shell.ready": "Genio is ready",
    "shell.greeting": "Hi! I am Genio",
    "shell.listening": "Genio is listening",
    "shell.understanding": "Genio is understanding your request",
    "shell.thinking": "Genio is thinking",
    "shell.planning": "Genio is planning",
    "shell.explaining": "Genio is answering",
    "shell.executing": "Genio is working on your task",
    "shell.waiting": "Genio is waiting",
    "shell.asking": "Genio is waiting for your reply",
    "shell.success": "Task completed",
    "shell.warning": "Attention needed",
    "shell.error": "Something went wrong",
    "shell.recovering": "Genio is recovering",
    "shell.celebrating": "Well done, completed!",
    "shell.sleeping": "Genio is asleep",
    "shell.disconnected": "Connection lost",
    "shell.attention": "Genio needs your attention",
    "shell.current_task": "Current task",
    "shell.no_task": "No task yet. Send a message to start.",
    "shell.resources": "Resources",
    "shell.details": "Technical details",
    "shell.result": "Result",
    "shell.events": "Events",
    "shell.cancel": "Cancel",
    "shell.reconnect": "Reconnect",
    "shell.unavailable": "Unavailable",
    "shell.offline": "Offline — navigation, docs, settings and preferences stay usable. AI features need a connection.",
    "shell.connection_lost": "Connection lost",
    "shell.details_docs": "Details in docs",
    "shell.advanced_on": "advanced on",
    "shell.opt_in": "opt-in",
    "shell.hide_advanced": "Hide advanced",
    "shell.show_advanced": "Show advanced",
    "input.placeholder": "Message Genio… (Enter to send, Shift+Enter for newline)",
    "input.attach": "Attach files",
    "input.mic": "Speak",
    "input.stop": "Stop recording",
    "input.recording": "Recording",
    "input.send": "Send",
    "input.cancel": "Cancel",
    "input.drop": "Drop files here to attach",
    "input.listening": "Genio is listening — speak now",
    "input.listen": "Listen",
    "input.listen_label": "LISTEN",
    "input.stop_recording": "Stop recording",
    "input.live_transcription": "live transcription: speak…",
    "input.release_to_send": "release to send via Web Audio",
    "input.send_label": "READY",
    "errors.generic": "Unexpected error. Try again, and send details if it persists.",
    "errors.network": "No connection. Check the Internet and retry.",
    "errors.auth": "Sign-in required to continue.",
    "errors.mic": "Microphone unavailable",
    "errors.server": "The server did not answer. Retry in a moment.",
    "errors.timeout": "Took too long. Retry.",
    "errors.tech_details": "Technical details",
    "errors.cloud_auth": "Sign in with Google to continue in the cloud",
    "errors.cloud_fail": "Cloud connection problem — retry",
    "errors.cloud_retry": "Retry",
    "errors.google_signin": "Sign in with Google",
    "errors.mic_unavailable": "Microphone unavailable. Check browser permission.",
    "errors.google_auth_failed": "Google sign-in failed. Try again.",
    "errors.recording": "Recording",
    "errors.live_transcription": "Live transcription…",
    "errors.release_to_send": "Release to send",
    "errors.close_chat": "Close chat",
    "errors.open_chat": "Open chat",
    "status.connected": "Connected",
    "status.connecting": "Connecting...",
    "status.disconnected": "Disconnected",
    "status.ready": "Ready",
    "status.working": "Working",
    "status.done": "Done",
    "task.title": "Current task",
    "task.step": "Current step",
    "task.steps": "Steps",
    "task.tool": "Tool",
    "task.duration": "Duration",
    "task.status": "Status",
    "task.cancel": "Cancel task",
    "task.cancel_requested": "Cancellation requested, waiting for confirmation...",
    "task.cancelled": "Task cancelled",
    "task.queued": "Queued",
    "task.running": "Running",
    "task.waiting": "Waiting",
    "task.completed": "Completed",
    "task.failed": "Failed",
    "task.elapsed": "Elapsed (measured on your device)",
    "settings.density": "Information density",
    "settings.ambient": "Ambient effects",
    "density.simple": "Simple",
    "density.detailed": "Detailed",
    "density.advanced": "Advanced",
    "ambient.glow": "Glow/particles",
    "ambient.reduced": "Reduced motion",
    "ambient.note": "Security alerts, task state and errors are never disabled by these settings.",
    "events.empty": "No events yet.",
    "tool.activity": "Tool activity",
    "tool.evidence_unavailable": "No evidence available",
    "a11y.skip": "Skip to content",
    "a11y.close": "Close",
    "a11y.menu": "Open menu",
    "a11y.copy": "Copy command",
    "a11y.copied": "Copied ✓",
    "onboarding.welcome": "Welcome to Genio",
    "onboarding.start": "Start",
    "onboarding.skip": "Skip",
    // permissions.*
    "perm.checking": "Checking device capabilities...",
    "perm.title": "Permissions & Hardware",
    "perm.subtitle": "Genio needs a few capabilities to run natively on Android",
    "perm.camera": "Camera",
    "perm.camera_desc": "Front-camera face tracking (Chachia avatar gaze)",
    "perm.microphone": "Microphone",
    "perm.microphone_desc": "Native voice input (Darija STT)",
    "perm.storage": "Storage",
    "perm.storage_desc": "Attachments & READ_MEDIA_*",
    "perm.network": "Network",
    "perm.network_desc": "INTERNET & ACCESS_NETWORK_STATE",
    "perm.grant_all": "Grant all",
    "perm.reverify": "Re-verify",
    "perm.continue_anyway": "Continue anyway",
    "perm.continue": "Continue",
    "perm.tauri_note": "Tauri Android will also enforce manifest permissions: CAMERA, RECORD_AUDIO, INTERNET, ACCESS_NETWORK_STATE, READ_MEDIA_*.",
    "perm.skip": "skip onboarding",
    // header.*
    "header.toggle_drawer": "Toggle drawer",
    "header.selfie_mode": "SELFIE MODE",
    "header.toggle_selfie": "Toggle selfie face tracking",
    "header.stop": "Stop",
    "header.disconnect": "Disconnect",
    "header.thinking": "Thinking...",
    "header.executing": "Exec: ",
    "header.completed": "Completed",
    "header.stale": "Stale",
    "header.telemetry_paused": "Telemetry paused — backend event loop busy",
    // mascot.*
    "mascot.listening": "listening...",
    "mascot.speaking": "speaking...",
    "mascot.tap_to_speak": "Tap to speak",
    "mascot.gesture_note": "gestures learned for this user",
    "mascot.technical_mode": "Technical mode",
    // telemetry.*
    "telemetry.offline": "🔴 Offline",
    "telemetry.thinking": "🟡 Genio thinking...",
    "telemetry.streaming": "🔵 Streaming",
    "telemetry.ready": "🟢 Ready",
    // app.* (App shell mode buttons + background actions)
    "app.mode_technique": "Technical mode",
    "app.mode_mascot": "Mascot mode",
    "app.mode_unified": "Unified mode",
    "app.mode_mascot_title": "Back to fullscreen mascot",
    "app.mode_unified_title": "Unified view: conversation, presence and task",
    "app.kill_agent": "Kill agent",
    "app.disconnect": "Disconnect",
    // error boundary fallback
    "boundary.crash": "Scene crashed — fallback active.",
    // permission status values (device messages mapped, never raw English)
    "perm.status_granted": "Granted",
    "perm.status_online": "Online",
    "perm.status_offline": "Offline",
    "perm.status_denied": "Denied — check OS settings",
    "perm.status_denied_retry": "Denied — can request again",
    "perm.status_unavailable": "Unavailable on this device",
    // chat panel (FAB)
    "chat.title": "Genio Chat",
    "chat.empty": "✨ Genio is listening — type or speak ✨",
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

/** Reactive language hook: re-renders on language switch (same-tab + other tabs). */
export function useLang(): [Lang, (l: Lang) => void] {
  const [lang, setLangState] = useState<Lang>(() => getLang());
  useEffect(() => {
    const sync = () => {
      const next = getLang();
      setLangState((prev) => (prev === next ? prev : next));
    };
    window.addEventListener("storage", sync);
    window.addEventListener("genio:lang", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("genio:lang", sync);
    };
  }, []);
  const change = (l: Lang) => {
    setLang(l);
    setLangState(l);
    window.dispatchEvent(new Event("genio:lang"));
  };
  return [lang, change];
}

/**
 * Map internal error strings to friendly localized user-facing messages.
 * Internal/technical details are hidden behind `errors.tech_details`.
 * Never expose secrets, tokens, paths, or stack traces.
 */
export function mapError(lang: Lang, raw: string): { friendly: string; technical?: string } {
  const s = (raw || "").toLowerCase();
  if (s.includes("no_google_token") || s.includes("need_google_auth")) {
    return { friendly: t(lang, "errors.cloud_auth") };
  }
  if (s.includes("gemini_proxy_fail") || s.includes("السيرفر طايح") || s.includes("server")) {
    return { friendly: t(lang, "errors.cloud_fail"), technical: raw };
  }
  if (s.includes("microphone") || s.includes("mic") || s.includes("permission")) {
    return { friendly: t(lang, "errors.mic_unavailable") };
  }
  if (s.includes("network") || s.includes("fetch") || s.includes("offline")) {
    return { friendly: t(lang, "errors.network") };
  }
  if (s.includes("timeout")) {
    return { friendly: t(lang, "errors.timeout") };
  }
  if (s.includes("google") && (s.includes("sign") || s.includes("auth") || s.includes("login"))) {
    return { friendly: t(lang, "errors.google_auth_failed") };
  }
  // Generic fallback — never leak raw internals
  return { friendly: t(lang, "errors.generic"), technical: raw };
}

/**
 * Map raw device permission status messages (English, from browser/OS APIs)
 * to friendly localized labels. Raw strings are never shown to the user.
 */
export function mapPermStatus(lang: Lang, granted: boolean, message: string): string {
  const s = (message || "").toLowerCase();
  if (s.includes("online")) return t(lang, "perm.status_online");
  if (s.includes("offline")) return t(lang, "perm.status_offline");
  if (granted) return t(lang, "perm.status_granted");
  if (s.includes("denied") && (s.includes("os settings") || s.includes("système") || s.includes("system"))) {
    return t(lang, "perm.status_denied");
  }
  if (s.includes("denied") || s.includes("notallowed") || s.includes("permission")) {
    return t(lang, "perm.status_denied_retry");
  }
  return t(lang, "perm.status_unavailable");
}
