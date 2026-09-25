"""Phase 7 tests — bash structured validation.

Chaque classe d'attaque du prompt : verdict + exécution réelle du refus
(run_command ne doit JAMAIS exécuter — canaris). Bénins : autorisés ET
exécutés pour de vrai (pas de sur-blocage).
"""
import os
import sys

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.tools.bash_ast import classify, parse
from genio_server.tools.bash_tool import is_dangerous, run_command

DENY_CASES = {
    "sudo": "sudo id",
    "su": "su -",
    "pkexec": "pkexec id",
    "setuid": "chmod u+s /bin/x",
    "fork_bomb": ":(){ :|:& };:",
    "mkfs": "mkfs.ext4 /dev/sda1",
    "dd_device": "dd if=/dev/zero of=/dev/sda bs=1M",
    "redirect_device": "echo x > /dev/sda",
    "chmod_777_root": "chmod -R 777 /",
    "proc_write": "echo 1 > /proc/sys/x",
    "sys_write": "echo 1 > /sys/x",
    "dev_tty": "echo x > /dev/tty0",
    "docker_priv": "docker run --privileged img",
    "docker_sock": "curl --unix-socket /var/run/docker.sock http://x",
    "nsenter": "nsenter -t 1 bash",
    "ssh_key": "cat ~/.ssh/id_rsa",
    "env_file": "cat .env",
    "pem": "cat key.pem",
    "shadow": "cat /etc/shadow",
    "ld_preload": "export LD_PRELOAD=/tmp/x.so",
    "traversal_write": "echo x > ../../escape",
    "py_escape": "python3 -c \"import os; os.system('id')\"",
    "node_escape": "node -e \"require('child_process').exec('id')\"",
    "rm_root": "rm -rf /",
}

ALLOW_CASES = [
    "echo hi",
    "ls -la",
    "pwd",
    "git status --short",
    "python3 --version",
    "curl https://example.com",
    "pip install requests",
    "sleep 1 &",
    "export PATH=/x",
    "echo x > /dev/null",
    "cat file.txt",
    "docker ps",
]


def test_parser_segments():
    segs = parse("ls -la /tmp; echo hi && pwd")
    assert len(segs) == 3
    assert segs[0].argv[0] == "ls"
    assert segs[1].sep in (";", "&&")


def test_parser_redirects_and_subst():
    segs = parse("echo $(whoami) > out.txt")
    assert segs[0].redirects == [(">", "out.txt")]
    assert segs[0].has_subst is True


def test_deny_classes():
    for name, cmd in DENY_CASES.items():
        v = classify(cmd)
        assert v["verdict"] == "deny", f"{name} not denied: {cmd}"
        assert is_dangerous(cmd), f"{name} passes is_dangerous: {cmd}"


def test_allow_benign():
    for cmd in ALLOW_CASES:
        v = classify(cmd)
        assert v["verdict"] == "allow", f"false positive: {cmd} {v}"
        assert not is_dangerous(cmd), f"false positive gate: {cmd}"


def test_flags_annotate_without_blocking():
    assert "net-tool:curl" in classify("curl https://example.com")["flags"]
    assert "pkg-install:pip" in classify("pip install requests")["flags"]
    assert "backgrounded" in classify("sleep 1 &")["flags"]


def test_denied_never_executes():
    canary = "/tmp/ph7_canary_never"
    if os.path.exists(canary):
        os.remove(canary)
    r = run_command(f"echo PWNED > {canary}; echo PWNED > /dev/sda")
    assert r["returncode"] in (125, 126)
    assert not os.path.exists(canary)


def test_allowed_really_executes():
    r = run_command("echo ph7-alive")
    assert r["returncode"] == 0 and "ph7-alive" in r["stdout"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
