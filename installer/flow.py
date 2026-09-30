"""Assistant-driven install orchestration (deterministic, no LLM).

Flow: welcome → full preflight → TN report → explain missing → consent →
repair (minimal packages) → verify → retry (bounded) → install →
smoke → first-run. Non-interactive mode performs the same steps without
prompts and exits with the documented codes.
"""
from installer import i18n
from installer.assistant import Assistant, NeedInput
from installer.core.errors import (
    EXIT_OK, EXIT_USER_ABORT, EXIT_ALREADY_INSTALLED,
    EXIT_AMBIGUOUS_INSTALLS, EXIT_DEPS_MISSING, InstallerError,
)
from installer.core.paths import DEFAULT_PORTS, default_prefix, layout


def _assistant(args):
    lang = i18n.resolve_lang(getattr(args, "lang", None))
    interactive = bool(getattr(args, "assistant", False)) or (
        not getattr(args, "yes", False) and _tty_available())
    return Assistant(lang=lang, interactive=interactive)


def _tty_available():
    import sys
    if sys.stdin.isatty():
        return True
    try:
        open("/dev/tty", "r").close()
        return True
    except OSError:
        return False


def _why_for(name):
    return {"git": "why_git", "docker": "why_docker", "python3": "why_python",
            "pip": "why_pip", "venv": "why_venv"}.get(name, "why_python")


def report_preflight(a, rep):
    plat = rep["os"]
    a.say(a.t("inspecting"))
    a.progress("ok", a.t("os_line", v=f"{plat.get('distribution')} {plat.get('distro_version')}"))
    a.say(a.t("report_title"))
    for name in ("python3", "git", "pip", "venv", "docker"):
        it = rep["items"].get(name, {"state": "UNKNOWN", "detail": ""})
        st = it["state"]
        if st == "AVAILABLE":
            a.progress("ok", a.t("found_ok", name=name))
        elif st == "MISSING":
            a.progress("warn", a.t("missing_line", name=name))
        elif st == "DAEMON_DOWN":
            a.progress("warn", a.t("daemon_down", name=name))
        elif st == "PERMISSION_DENIED":
            a.progress("warn", a.t("perm_denied", name=name))
        else:
            a.progress("warn", a.t("broken_line", name=name))
    net = rep.get("network", {})
    if net.get("offline"):
        a.progress("fail", a.t("net_fail"))


def explain_missing(a, rep, family):
    from installer import packages as pkg
    for name in rep.get("needs_repair", []):
        a.say("")
        a.say(a.t(_why_for(name)))
        if family and name in ("git", "python3", "pip", "venv", "docker"):
            need = {"git": ["git"], "docker": ["docker"]}.get(
                name, ["python"] if name in ("python3", "pip", "venv") else [])
            pkgs = []
            for n in need:
                pkgs.extend(pkg.FAMILIES[family].get(n, []))
            if pkgs:
                a.say(a.t("need_minimal", pkg=", ".join(pkgs)))


def consent_for(a, executor_cmds, what):
    a.say("")
    a.say(a.t("consent_sudo", what=what))
    a.say(a.t("consent_changes"))
    if not a.interactive:
        return False
    choice = a.ask_choice(a.t("consent_ask"), [
        ("yes", a.t("consent_yes")),
        ("no", a.t("consent_no")),
        ("what", a.t("consent_what")),
    ])
    if choice == "what":
        a.say(a.t("consent_what_answer", cmd=" && ".join(" ".join(c) for c in executor_cmds)))
        return a.ask_yes_no(a.t("consent_ask"))
    return choice == "yes"


def repair_missing(a, runner, rep, family, emitter=None, dry_run=False):
    """Install minimal missing system packages with consent. Returns True if
    a re-check shows everything repaired. Bounded: one attempt per item."""
    from installer import packages as pkg
    from installer import preflight as pre
    need_names = [n for n in rep.get("needs_repair", [])
                  if n in ("git", "python3", "pip", "venv", "docker")]
    if not need_names:
        return True
    if not family:
        a.say(a.t("abort_repair_impossible",
                  hint="install git + python3 + docker manually for your OS"))
        return False
    need = []
    for n in need_names:
        need.extend([{"git": "git", "docker": "docker"}.get(n, "python")])
    need = list(dict.fromkeys(need))
    cmds = pkg.plan_install(family, need)
    if not consent_for(a, cmds, what=", ".join(need)):
        a.say(a.t("cancelled"))
        raise _Abort()
    ex = pkg.Executor(runner=runner, dry_run=dry_run)
    a.say(a.t("installing_what", name=", ".join(need)))
    ok, log = pkg.install_needs(ex, family, need, sudo=True)
    if a.interactive:
        a.technical(log)
    if not ok:
        a.progress("fail", a.t("verify_fail", name=", ".join(need), detail="package install rc!=0"))
        return False
    # Verify by re-detection (never trust the installer blindly).
    rep2 = pre.preflight(runner)
    still = [n for n in need_names
             if rep2["items"].get(n, {}).get("state") != "AVAILABLE"]
    # Docker needs daemon/permission handling beyond packages.
    if "docker" in need_names:
        from installer.preflight import DAEMON_DOWN, PERMISSION_DENIED, AVAILABLE
        dst = rep2["items"].get("docker", {}).get("state")
        if dst == DAEMON_DOWN:
            a.say(a.t("verifying_what", name="Docker daemon"))
            st, dlog = pkg.ensure_docker_daemon(ex, family)
            if a.interactive:
                a.technical(dlog)
            rep2 = pre.preflight(runner)
            dst = rep2["items"].get("docker", {}).get("state")
        if dst == PERMISSION_DENIED:
            import os
            user = os.environ.get("USER") or os.environ.get("LOGNAME") or "you"
            a.say(a.t("abort_repair_impossible", hint=f"sudo usermod -aG docker {user} # then log out/in"))
            return False
        if dst != AVAILABLE:
            a.progress("fail", a.t("verify_fail", name="Docker",
                                   detail=rep2["items"].get("docker", {}).get("detail", "?")))
            return False
        still = [n for n in still if n != "docker"]
    for n in need_names:
        if n not in still:
            a.progress("ok", a.t("installed_ok", name=n))
            a.progress("ok", a.t("verify_ok", name=n))
    for n in still:
        a.progress("fail", a.t("verify_fail", name=n, detail="still missing after install"))
    rep["items"] = rep2["items"]
    rep["needs_repair"] = [n for n in rep.get("needs_repair", []) if n in still]
    return not still


class _Abort(Exception):
    pass


def smoke(prefix, runner, lang="tu"):
    """Real post-install smoke test. Returns [(name, ok, detail)]."""
    from installer.health import doctor as doc
    checks = []
    lay = layout(prefix)
    man = None
    try:
        from installer.core.manifest import read_manifest
        man = read_manifest(lay["manifest"])
    except Exception:
        man = None
    checks.append(("manifest", man is not None,
                   "manifest present" if man else "manifest missing"))
    py = lay["venv"] / "bin" / "python"
    r = runner.run([str(py), "--version"], timeout=30) if py.exists() else {"ok": False}
    checks.append(("venv-python", bool(r.get("ok")),
                   (r.get("out") or "").strip()[:40] or "venv python missing"))
    if man is not None:
        res = doc.doctor(runner, prefix=prefix, deep=False)
        checks.append(("doctor", res["fail"] == 0,
                       f"verdict={res['verdict']} ({res['fail']} FAIL)"))
    return checks


def run_install(args, runner, prefix, emitter):
    """Assistant install. Returns (exit_code_or_None, preflight_report).
    exit_code None means: preflight green, caller continues install."""
    from installer import packages as pkg
    from installer import preflight as pre
    from installer.core.paths import layout as _layout  # noqa
    a = _assistant(args)
    lang = a.lang
    # Welcome (interactive only; non-interactive stays machine-clean).
    _rep_empty = {"items": {}, "needs_repair": [], "os": {"supported": True},
                  "network": {}, "permissions": {}}
    if a.interactive:
        a.say(a.t("welcome_1"))
        a.say(a.t("welcome_2"))
        a.say(a.t("welcome_3"))
        a.say(a.t("welcome_4"))
        try:
            if not a.ask_yes_no(a.t("welcome_ask")):
                a.say(a.t("cancelled"))
                return EXIT_USER_ABORT, _rep_empty
        except NeedInput:
            return EXIT_USER_ABORT, _rep_empty
    emitter.emit("PREFLIGHT_STARTED", {})
    rep = pre.preflight(runner, prefix=prefix)
    report_preflight(a, rep)
    plat = rep["os"]
    if not plat.get("supported"):
        a.say(a.t("unsupported_os", v=plat.get("distribution", "?")))
        a.say("  - Debian/Ubuntu: sudo apt-get install -y git python3 python3-venv python3-pip")
        a.say("  - Fedora: sudo dnf install -y git python3 python3-pip")
        a.say("  - Arch: sudo pacman -S --noconfirm git python python-pip")
        emitter.emit("PREFLIGHT_RESULT", {"ok": False, "reason": "unsupported-os"})
        from installer.core.errors import EXIT_UNSUPPORTED
        return EXIT_UNSUPPORTED, rep
    net = rep.get("network", {})
    if net.get("offline") and not rep.get("needs_repair"):
        # Offline with nothing to repair: can only continue from local source.
        a.say(a.t("net_fail"))
    family = pkg.family_for(plat.get("distro_id"), plat.get("package_manager"))
    if rep.get("needs_repair"):
        explain_missing(a, rep, family)
        if a.interactive:
            try:
                ok = repair_missing(a, runner, rep, family, emitter,
                                   dry_run=bool(getattr(args, "dry_run", False)))
            except _Abort:
                return EXIT_USER_ABORT, rep
            if not ok:
                # Bounded retry: one more full detect→repair round.
                a.say(a.t("retrying"))
                rep2 = pre.preflight(runner, prefix=prefix)
                rep["items"] = rep2["items"]
                rep["needs_repair"] = rep2["needs_repair"]
                if rep["needs_repair"]:
                    try:
                        ok = repair_missing(a, runner, rep, family, emitter,
                                   dry_run=bool(getattr(args, "dry_run", False)))
                    except _Abort:
                        return EXIT_USER_ABORT, rep
                else:
                    ok = True
                if not ok:
                    emitter.emit("PREFLIGHT_RESULT", {"ok": False,
                                                     "missing": rep["needs_repair"]})
                    return EXIT_DEPS_MISSING, rep
        else:
            # Non-interactive: report everything + exact minimal fix, no sudo.
            from installer.core.errors import EXIT_DEPS_MISSING as _ED
            emitter.emit("PREFLIGHT_RESULT", {"ok": False,
                                             "missing": rep["needs_repair"]})
            return _ED, rep
        if rep.get("needs_repair"):
            emitter.emit("PREFLIGHT_RESULT", {"ok": False,
                                             "missing": rep["needs_repair"]})
            return EXIT_DEPS_MISSING, rep
    emitter.emit("PREFLIGHT_RESULT", {"ok": True})
    if a.interactive:
        a.say(a.t("device_ready"))
        a.say(a.t("installing_genio"))
    return None, rep  # caller continues with the standard install stages
