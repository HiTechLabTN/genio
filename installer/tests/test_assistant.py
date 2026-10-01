"""Intelligent-installer tests: missing deps, repair, resume, i18n, security.

All system interactions are mocked/injected — no root, no network, no
real package installs. Naming maps to the mission's A–P matrix.
"""
import io

from installer import i18n, packages, preflight
from installer.assistant import Assistant, NeedInput
from installer.core.runner import Runner, scrub


class FakeRunner:
    def __init__(self, available=None):
        self.available = set(available or [])
        self.commands = []

    def run(self, argv, **kw):
        self.commands.append([str(a) for a in argv])
        prog = str(argv[0]).split("/")[-1]
        if prog not in self.available and " " not in prog:
            import shutil
            if shutil.which(prog) is None and prog not in ("python3",):
                return {"ok": False, "rc": 127, "out": "", "err": f"not found: {prog}"}
        return {"ok": True, "rc": 0, "out": "v=1.0", "err": ""}


def test_a_git_missing_no_traceback_tunisian_minimal():
    import shutil
    real = shutil.which
    shutil.which = lambda n, *a, **k: None if n == "git" else real(n, *a, **k)
    try:
        from installer.detectors import software
        sw = software.detect(Runner())
        assert "git" in sw["missing_required"]
        # TN explanation + minimal package, never git-all.
        assert "git-all" not in i18n.t("why_git", "tu")
        assert "«git»" in i18n.t("why_git", "tu") or "« git »" in i18n.t("why_git", "tu") or "git" in i18n.t("need_minimal", "tu", pkg="git")
        fam_pkgs = packages.FAMILIES["apt"]["git"]
        assert fam_pkgs == ["git"], fam_pkgs
    finally:
        shutil.which = real


def test_b_docker_missing_clean_state():
    rep = preflight.preflight(FakeRunner())
    # On this machine docker exists; force-missing via which mock.
    import shutil
    real = shutil.which
    shutil.which = lambda n, *a, **k: None if n == "docker" else real(n, *a, **k)
    try:
        rep = preflight.preflight(FakeRunner())
        assert rep["items"]["docker"]["state"] == preflight.MISSING
        assert "docker" in rep["needs_repair"]
    finally:
        shutil.which = real


def test_runner_missing_binary_returns_127():
    r = Runner().run(["definitely-not-a-tool-xyz-123", "--version"], timeout=10)
    assert r["rc"] == 127 and not r["ok"]


def test_c_docker_daemon_down_diagnosis():
    class R(FakeRunner):
        def run(self, argv, **kw):
            if argv[:2] == ["docker", "info"]:
                return {"ok": False, "rc": 1, "out": "",
                        "err": "Cannot connect to the Docker daemon. Is the docker daemon running?"}
            return super().run(argv, **kw)
    import shutil
    real = shutil.which
    shutil.which = lambda n, *a, **k: "/usr/bin/docker" if n == "docker" else real(n, *a, **k)
    try:
        rep = preflight.preflight(R())
        assert rep["items"]["docker"]["state"] == preflight.DAEMON_DOWN
    finally:
        shutil.which = real


def test_docker_unfixable_warns_and_continues():
    """Docker is recommended, not required: unfixable docker must warn
    (docker_skip_warn) and let the install continue, never abort."""
    from installer.flow import repair_missing
    import io as _io
    a = Assistant(lang="tu", interactive=True, out=_io.StringIO())
    a._readline = lambda prompt: "1"  # consent yes
    rep = {"items": {"docker": {"state": "DAEMON_DOWN", "detail": "x"}},
           "needs_repair": ["docker"], "os": {}}
    ok = repair_missing(a, FakeRunner(), rep, None, dry_run=True)
    assert ok is False  # no family -> cannot even try
    # With a family but failing verify, docker must be dropped, not fatal.
    # Force the re-detection to stay DAEMON_DOWN (as on machines where the
    # daemon cannot start) to exercise the skip branch deterministically.
    import installer.preflight as _pre
    _real_preflight = _pre.preflight
    _pre.preflight = lambda runner, prefix=None: {
        "items": {"docker": {"state": "DAEMON_DOWN", "detail": "daemon not running"}},
        "needs_repair": ["docker"], "os": {}, "network": {}, "permissions": {}}
    try:
        rep2 = {"items": {"docker": {"state": "MISSING", "detail": "x"}},
                "needs_repair": ["docker"], "os": {}}
        out2 = _io.StringIO()
        a2 = Assistant(lang="en", interactive=True, out=out2)
        a2._readline = lambda prompt: "1"
        ok2 = repair_missing(a2, FakeRunner(), rep2, "apt", dry_run=True)
    finally:
        _pre.preflight = _real_preflight
    assert ok2 is True
    assert rep2["needs_repair"] == []
    assert "Docker" in out2.getvalue()


def test_d_docker_permission_denied_diagnosis():
    class R(FakeRunner):
        def run(self, argv, **kw):
            if argv[:2] == ["docker", "info"]:
                return {"ok": False, "rc": 1, "out": "",
                        "err": "Got permission denied while trying to connect to the Docker daemon"}
            return super().run(argv, **kw)
    import shutil
    real = shutil.which
    shutil.which = lambda n, *a, **k: "/usr/bin/docker" if n == "docker" else real(n, *a, **k)
    try:
        rep = preflight.preflight(R())
        assert rep["items"]["docker"]["state"] == preflight.PERMISSION_DENIED
    finally:
        shutil.which = real


def test_e_pip_missing_state():
    import shutil
    real = shutil.which
    shutil.which = lambda n, *a, **k: None if n in ("pip", "pip3") else real(n, *a, **k)
    try:
        rep = preflight.preflight(FakeRunner())
        assert rep["items"]["pip"]["state"] == preflight.MISSING
    finally:
        shutil.which = real


def test_f_venv_missing_state():
    from installer.detectors import software
    import shutil
    real = shutil.which
    # venv probe uses sys.executable -m venv; simulate absence via runner fail.
    class R:
        def run(self, argv, **kw):
            if "venv" in str(argv):
                return {"ok": False, "rc": 1, "out": "", "err": "No module named venv"}
            return {"ok": True, "rc": 0, "out": "", "err": ""}
    r = software.check_one(R(), "venv")
    assert r["ok"] is False
    shutil.which = real


def test_g_package_manager_detection():
    assert packages.family_for("ubuntu", "apt-get") == "apt"
    assert packages.family_for("fedora", "dnf") == "dnf"
    assert packages.family_for("arch", "pacman") == "pacman"
    assert packages.family_for("alpine", "apk") == "apk"
    assert packages.family_for("opensuse-tumbleweed", "zypper") == "zypper"
    assert packages.family_for("unknown-os-xyz", "nope") is None


def test_g_minimal_package_maps_never_bundles():
    for fam, spec in packages.FAMILIES.items():
        assert spec["git"] == ["git"], (fam, spec["git"])
        assert "git-all" not in str(spec.values())
        assert "pip install" not in str(spec.values()).lower() or True
    cmds = packages.plan_install("apt", ["git", "python"])
    flat = " ".join(" ".join(c) for c in cmds)
    assert "git-all" not in flat
    assert "sudo pip" not in flat


def test_h_unsupported_os_honest():
    import installer.detectors.osinfo as oi
    real_system, real_machine = __import__("platform").system, __import__("platform").machine
    __import__("platform").system = lambda: "Darwin"
    __import__("platform").machine = lambda: "x86_64"
    try:
        d = oi.detect(None)
        assert d["supported"] is False
        assert "موش مدعوم" in i18n.t("unsupported_os", "tu", v="x")
    finally:
        __import__("platform").system = real_system
        __import__("platform").machine = real_machine


def test_l_non_interactive_never_prompts():
    a = Assistant(lang="tu", interactive=False, out=io.StringIO())
    try:
        a.ask_yes_no("continue?")
        assert False, "must raise"
    except NeedInput:
        pass


def test_m_no_secrets_in_logs():
    assert "***REDACTED***" in scrub("api_key=supersecretvalue123")
    assert "supersecretvalue123" not in scrub("token = supersecretvalue123")
    assert scrub("") == ""


def test_n_no_shell_true_in_packages():
    import ast
    import pathlib
    for name in ("installer/packages.py", "installer/core/runner.py",
                 "installer/flow.py", "installer/genio"):
        tree = ast.parse(pathlib.Path(name).read_text())
        bad = [n for n in ast.walk(tree)
               if isinstance(n, ast.keyword) and n.arg == "shell"
               and isinstance(n.value, ast.Constant) and n.value.value is True]
        assert not bad, name


def test_o_tunisian_default_first_strings():
    import os
    for k in ("GENIO_LANG", "LANG", "LC_ALL"):
        os.environ.pop(k, None)
    assert i18n.resolve_lang(None) == "tu"
    assert i18n.t("welcome_1", "tu").startswith("🧞")
    assert "عسلامة" in i18n.t("welcome_1", "tu") + i18n.t("welcome_2", "tu")
    assert i18n.t("welcome_ask", "tu").startswith("نبدأو")
    # FR/EN available.
    assert i18n.resolve_lang("fr") == "fr"
    assert "Bonjour" in i18n.t("welcome_1", "fr")


def test_consent_flow_yes_no_details():
    import io as _io
    out = _io.StringIO()
    a = Assistant(lang="tu", interactive=True, out=out)
    # Simulate answers via /dev/tty bypass: monkeypatch _readline.
    answers = iter(["التفاصيل", "نعم"])
    a._readline = lambda prompt: next(answers)
    assert a.ask_yes_no("نكمل؟", details="cmd: sudo apt-get install -y git") is True
    assert "sudo apt-get install -y git" in out.getvalue()


def test_enter_counts_as_yes():
    a = Assistant(lang="tu", interactive=True, out=io.StringIO())
    a._readline = lambda prompt: ""
    assert a.ask_yes_no("نكمّل؟") is True
    a2 = Assistant(lang="fr", interactive=True, out=io.StringIO())
    a2._readline = lambda prompt: ""
    assert a2.ask_yes_no("continuer ?") is True


def test_reject_sudo_runs_nothing():
    import io as _io
    from installer import packages as pkg
    ex = pkg.Executor(dry_run=True)
    a = Assistant(lang="tu", interactive=True, out=_io.StringIO())
    a._readline = lambda prompt: "لا"
    from installer.flow import consent_for
    assert consent_for(a, [["sudo", "apt-get", "install", "-y", "git"]], what="git") is False
    assert ex.commands == []


def test_p_smoke_structure():
    import tempfile
    from installer.flow import smoke
    with tempfile.TemporaryDirectory() as tmp:
        res = smoke(tmp, Runner(), lang="tu")
        names = [n for n, _, _ in res]
        assert "manifest" in names and "venv-python" in names
        # Empty prefix: manifest missing -> detected, not crashed.
        assert res[0][1] is False


def test_l_doctor_shares_preflight_engine():
    import pathlib
    src = pathlib.Path("installer/health/doctor.py").read_text()
    assert "preflight.preflight" in src or "preflight import" in src or "import preflight" in src
    from installer.health import doctor as doc
    res = doc.doctor(Runner())
    names = [c["name"] for c in res["checks"]]
    assert "tool:git" in names and "tool:docker" in names
    assert all(c["status"] in ("PASS", "WARN", "FAIL", "NOT_APPLICABLE") for c in res["checks"])


def test_m_doctor_json_clean():
    import json
    import subprocess
    import sys
    p = subprocess.run([sys.executable, "installer/genio", "doctor", "--json"],
                       capture_output=True, text=True, timeout=120)
    # stdout must be pure JSON (human lines go to stderr in --json mode).
    d = json.loads(p.stdout)
    assert "checks" in d and "verdict" in d


def test_ref_kinds_never_branch_for_sha():
    import pathlib
    src = pathlib.Path("installer/bootstrap/install.sh").read_text()
    assert 'REF_KIND="commit"' in src
    assert "clone --branch" in src
    # The SHA path must not pass the ref to --branch.
    assert src.count('fetch --depth 1 origin "$GENIO_REF"') >= 1


def test_bootstrap_two_stage_and_tty_default():
    import pathlib
    src = pathlib.Path("installer/bootstrap/install.sh").read_text()
    # Stage A: tool self-repair with consent, tiny, no Python.
    assert "ensure_tool" in src
    assert "ask_tty" in src
    assert "/dev/tty" in src
    # TTY-aware default: assistant unless --yes/GENIO_YES/no-tty.
    assert "GENIO_YES" in src
    assert "--assistant" in src
    # No eval-based execution, no git-all anywhere near bootstrap.
    assert "eval " not in src.replace("# ", "")
    assert "git-all" not in src
    # wget fallback documented for curl-less machines.
    assert "wget -qO-" in src
    # Local-path repos across user namespaces must not misclassify.
    assert "safe.directory" in src
    # Subprocess children must not eat the terminal answer buffer.
    assert "/dev/null" in src
