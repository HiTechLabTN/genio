"""Assistant UX layer — deterministic Tunisian conversation, no LLM.

Interactive mode reads answers (from /dev/tty when stdin is a pipe, as in
curl|bash). Non-interactive mode NEVER prompts: it raises NeedInput instead
so callers emit machine-readable output with correct exit codes.
"""
import sys

from installer import i18n


class NeedInput(Exception):
    """Raised when a prompt is required but interaction is disabled."""


class Assistant:
    def __init__(self, lang="tu", interactive=True, out=None):
        self.lang = lang if lang in i18n.LANGS else "tu"
        self.interactive = interactive
        self.out = out or sys.stdout
        self._tty = None

    def t(self, key, **vars):
        return i18n.t(key, self.lang, **vars)

    def say(self, text=""):
        print(text, file=self.out, flush=True)

    def _readline(self, prompt):
        if not self.interactive:
            raise NeedInput(prompt)
        if sys.stdin.isatty():
            try:
                return input(prompt)
            except EOFError:
                return ""
        # curl|bash: stdin is the script pipe — talk to the terminal.
        try:
            if self._tty is None:
                self._tty = open("/dev/tty", "r")
            self.out.write(prompt)
            self.out.flush()
            return self._tty.readline()
        except OSError:
            raise NeedInput(prompt)

    def _norm(self, s):
        return (s or "").strip().lower()

    def ask_yes_no(self, question, details=None):
        """Ask [yes / no] (plus [details] when provided). Returns True/False/None(details-shown-then-ask-again loop, max 3)."""
        for _ in range(4):
            ans = self._norm(self._readline(question + " "))
            yes = i18n.wordlist(self.lang, "yes_words")
            no = i18n.wordlist(self.lang, "no_words")
            det = i18n.wordlist(self.lang, "details_word")
            if any(ans == w or ans.startswith(w + " ") for w in yes) or ans in ("y", "o", "ن"):
                return True
            if any(ans == w for w in no) or ans in ("n", "l"):
                return False
            if details and any(d in ans for d in det):
                self.say(details)
                continue
            self.say(question + " ")
        return False

    def ask_choice(self, question, choices):
        """choices: [(key, label)]. Returns key or None on abort/empty."""
        self.say(question)
        for i, (_, label) in enumerate(choices, 1):
            self.say(f"  [{i}] {label}")
        try:
            ans = self._norm(self._readline("> "))
        except NeedInput:
            raise
        if ans.isdigit() and 1 <= int(ans) <= len(choices):
            return choices[int(ans) - 1][0]
        return None

    def progress(self, kind, text):
        mark = {"ok": "✓", "do": "→", "warn": "⚠", "fail": "✗"}.get(kind, "•")
        self.say(f"{mark} {text}")

    def technical(self, lines):
        """Details gate: hidden unless the user explicitly wants them."""
        try:
            if self.interactive:
                ans = self._norm(self._readline(self.t("tech_details") + " [y/N] "))
                if ans not in ("y", "yes", "o", "oui", "نعم", "اي"):
                    return
            else:
                return
        except NeedInput:
            return
        for line in lines:
            self.say(f"    {line}")
