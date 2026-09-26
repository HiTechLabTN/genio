"""Bash structured validation — Phase 7 (couche primaire, avant regex).

Parse shlex (stdlib) : segmentation top-level (;, &&, ||, |, &, newline),
argv par segment, redirections, substitutions $( )/`` ` ``, assigns d'env.
`classify()` rend un verdict structuré ; `is_dangerous` (bash_tool) le
consulte EN PREMIER, les regex historiques restant en défense en profondeur.

Politique :
- BLOCK (refus) : privesc su/pkexec/…, setuid, docker à risque / socket,
  fichiers credentials, écritures /proc /sys /dev (hors null/std*),
  LD_PRELOAD & cie, redirections `..` ou absolues sensibles, -c embarquant
  un vecteur connu.
- FLAG (autorisé + annoté) : outils réseau, installs paquets, background,
  exports bénins, interpréteurs simples.
"""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_SEP_RE = re.compile(r"(?P<op>&&|\|\||;;|;|\||&|\n)")


def _split_top_level(command: str) -> List[Dict[str, str]]:
    """Découpe en segments sur les séparateurs NON quotés.

    Scanner manuel (quotes simples/doubles + backslash) — shlex seul
    fragmente la ponctuation (-la, /tmp, out.txt) en tokens unitaires.
    Retourne [{text, sep}] où sep suit le segment (;, &&, ||, |, &).
    """
    segments: List[Dict[str, str]] = []
    buf: List[str] = []
    quote: Optional[str] = None
    esc = False
    i, n = 0, len(command or "")
    while i < n:
        c = command[i]
        if esc:
            buf.append(c)
            esc = False
            i += 1
            continue
        if c == "\\" and quote != "'":
            esc = True
            buf.append(c)
            i += 1
            continue
        if quote:
            buf.append(c)
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            buf.append(c)
            i += 1
            continue
        two = command[i:i + 2]
        if two in ("&&", "||"):
            segments.append({"text": "".join(buf), "sep": two})
            buf = []
            i += 2
            continue
        if c in (";", "|", "&", "\n"):
            segments.append({"text": "".join(buf), "sep": c})
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf)
    if tail.strip() or not segments:
        segments.append({"text": tail, "sep": ""})
    return segments


@dataclass
class Segment:
    argv: List[str]
    raw: str
    sep: str
    redirects: List[tuple] = field(default_factory=list)
    has_subst: bool = False
    env_assign: Dict[str, str] = field(default_factory=dict)


def parse(command: str) -> List[Segment]:
    """Parse structuré (ne lève jamais : dégrade en segment brut)."""
    out: List[Segment] = []
    for part in _split_top_level(command or ""):
        text = part["text"]
        try:
            argv = shlex.split(text, posix=True)
        except ValueError:
            argv = [text.strip()] if text.strip() else []
        redirects: List[tuple] = []
        clean: List[str] = []
        i = 0
        while i < len(argv):
            if argv[i] in (">", ">>", "<", "2>", "&>", "2>>") and i + 1 < len(argv):
                redirects.append((argv[i], argv[i + 1]))
                i += 2
                continue
            clean.append(argv[i])
            i += 1
        env_assign: Dict[str, str] = {}
        while clean and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", clean[0]):
            k, _, v = clean.pop(0).partition("=")
            env_assign[k] = v
        has_subst = bool(re.search(r"\$\(|\`|\$\{", text))
        out.append(Segment(argv=clean, raw=text.strip(), sep=part["sep"],
                           redirects=redirects, has_subst=has_subst,
                           env_assign=env_assign))
    return out


# --- vocabulaire d'attaque (structurel, pas du regex plein-texte) --- #
_PRIV = {"sudo", "su", "pkexec", "runuser", "doas"}
_CRED_PATTERNS = (".ssh/", "id_rsa", "id_ed25519", ".pem", ".env",
                  ".vault", "credentials", "shadow")
_SENSITIVE_ABS = ("/etc/", "/root/", "/proc/", "/sys/")
_DEV_OK = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/stdin"}
_NET_TOOLS = {"curl", "wget", "nc", "ncat", "nmap", "ssh", "scp", "sftp",
              "ftp", "telnet", "socat"}
_INSTALLERS = {"pip", "pip3", "apt", "apt-get", "npm", "yarn", "yum", "dnf",
               "apk", "pacman"}
_INTERPRETERS = {"python", "python3", "node", "perl", "ruby", "php"}
_DOCKER_RO = {"ps", "images", "inspect", "logs", "stats", "version", "info"}


def _is_cred_path(p: str) -> bool:
    low = p.lower()
    return any(pat in low for pat in _CRED_PATTERNS)


def classify(command: str) -> Dict[str, Any]:
    """Verdict structuré : {"verdict": allow|deny, "reasons": [...],
    "flags": [...]}. Jamais d'exception (dégrade en allow + flag)."""
    reasons: List[str] = []
    flags: List[str] = []
    try:
        segments = parse(command)
    except Exception:
        return {"verdict": "allow", "reasons": [], "flags": ["parse-fallback"]}
    if not segments or not any(s.argv for s in segments):
        return {"verdict": "allow", "reasons": [], "flags": []}

    for seg in segments:
        if not seg.argv:
            continue
        # 0. fork bomb (structure fonction + pipe récursif en brut).
        if re.search(r":\(\)\s*\{", seg.raw) or ":|:&" in seg.raw:
            reasons.append("fork bomb")
        prog = seg.argv[0].split("/")[-1].lower()
        args = seg.argv[1:]

        # 1. élévation de privilèges (sudo honore GENIO_ALLOW_SUDO comme avant).
        if prog in _PRIV and not (
                prog == "sudo" and os.getenv("GENIO_ALLOW_SUDO", "").strip().lower()
                in ("1", "true", "yes")):
            reasons.append(f"privilege escalation tool: {prog}")
        # 1b. création de filesystem.
        if prog == "mkfs" or prog.startswith("mkfs."):
            reasons.append("mkfs (filesystem creation)")
        # 1c. dd vers/depuis périphériques bloc (of=/dev/sd*…). Les usages
        # légitimes (if=/dev/zero|urandom, of=/dev/null|fichier) restent permis.
        if prog == "dd":
            for a in args:
                low = a.lower()
                if low.startswith("of=/dev/") and not low.startswith(
                        ("of=/dev/null", "of=/dev/stdout", "of=/dev/stderr")):
                    reasons.append(f"dd write to device: {a}")
                if re.match(r"^(if|of)=/dev/(sd|hd|nvme|mmcblk|vd|xvd)", low):
                    reasons.append(f"dd block-device access: {a}")
        # 2. setuid
        if prog == "chmod" and any(
                re.fullmatch(r"[0-7]*[4567][0-7]{3}", a) or a in ("u+s", "g+s", "+s")
                for a in args):
            reasons.append("setuid bit manipulation")
        # 2b. chmod récursif permissif sur racine (chmod -R 777 /).
        if prog == "chmod":
            rec = any(a in ("-r", "-R", "--recursive") for a in args)
            wide = any(a == "777" or "a+w" in a or "o+w" in a for a in args)
            rooted = any(a == "/" or a == "/*" for a in args)
            if rec and wide and rooted:
                reasons.append("chmod recursive world-writable on /")
        # 2c. rm destructif hors périmètre (/work seul est sûr).
        if prog == "rm":
            rec_force = any(a in ("-r", "-R", "-f", "--recursive", "--force",
                                  "-rf", "-fr") for a in args)
            for t in args:
                if t.startswith("-"):
                    continue
                if t in ("/", "/*", "*", ".", "..", "~") \
                        or t.startswith("~/") \
                        or (t.startswith("/") and t != "/work"
                            and not t.startswith("/work/")):
                    if rec_force or t in ("/", "/*", "*"):
                        reasons.append(f"destructive rm target: {t}")
                        break
        # 3. socket Docker n'importe où dans les args (curl --unix-socket…).
        if any("/var/run/docker.sock" in a or "//./pipe" in a
               for a in seg.argv):
            reasons.append("docker socket exposure")
        # 3b. docker : flags d'évasion, sous-commandes non-RO
        if prog == "docker":
            blob = " ".join(seg.argv).lower()
            if ("/var/run/docker.sock" in blob or "//./pipe" in blob
                    or "--privileged" in args or "--pid=host" in args
                    or "--network=host" in args
                    or any(a == "/" or a.startswith("/:/")
                           for a in args if a.startswith("/"))):
                reasons.append("docker escape vector (socket/privileged/host)")
            elif args and args[0].lstrip("-") not in _DOCKER_RO:
                reasons.append(f"docker non-readonly subcommand: {args[0]}")
        if prog in ("nsenter", "runc", "ctr", "crictl", "podman"):
            reasons.append(f"container escape tool: {prog}")
        # 4. fichiers credentials (lecture/écriture/argument)
        for a in args:
            if _is_cred_path(a):
                reasons.append(f"credential file access: {a}")
                break
        for _, target in seg.redirects:
            if _is_cred_path(target):
                reasons.append(f"credential file redirect: {target}")
        # 5. écritures /proc /sys
        for _, target in seg.redirects:
            if target.startswith(("/proc/", "/sys/")):
                reasons.append(f"write to kernel FS: {target}")
        # 6. /dev (hors null/std*)
        for _, target in seg.redirects:
            if target.startswith("/dev/") and target not in _DEV_OK:
                reasons.append(f"device write: {target}")
        # 7. env dangereux (assigns préfixés ET tokens exportés VAR=val).
        loader_hit = [k for k in list(seg.env_assign) + [
            t.split("=", 1)[0] for t in seg.argv
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t)]
            if k in ("LD_PRELOAD", "LD_LIBRARY_PATH",
                     "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH")]
        if loader_hit:
            reasons.append(f"loader hijack env: {loader_hit[0]}")
        for k in seg.env_assign:
            if k in ("PYTHONPATH", "NODE_PATH"):
                flags.append(f"env-override:{k}")
        # 8. redirections .. ou absolues sensibles
        for _, target in seg.redirects:
            if ".." in target.split("/"):
                reasons.append(f"path traversal redirect: {target}")
            elif target.startswith("/") and (
                    target.startswith(_SENSITIVE_ABS)
                    or target in ("/", "/root", "/etc")):
                reasons.append(f"sensitive absolute redirect: {target}")
        # 9. interpréteur -c/-e embarquant un vecteur connu
        if prog in _INTERPRETERS and any(
                a in ("-c", "-e", "-E") for a in args):
            payload = " ".join(args).lower()
            # urllib seul (fetch simple) reste permis ; on bloque l'évasion
            # réelle (exécution process, sockets bruts, imports dynamiques).
            if ("os.system" in payload or "os.popen" in payload
                    or "os.exec" in payload or "os.spawn" in payload
                    or "os.fork" in payload or "os.kill" in payload
                    or "subprocess" in payload or "socket" in payload
                    or "__import__" in payload or "child_process" in payload
                    or "pty" in payload or "ctypes" in payload):
                reasons.append(f"interpreter escape payload ({prog} -c)")
            else:
                flags.append(f"interpreter-exec:{prog}")
        elif prog in _INTERPRETERS:
            flags.append(f"interpreter:{prog}")
        # 10. flags : réseau, installs, background
        if prog in _NET_TOOLS:
            flags.append(f"net-tool:{prog}")
        if prog in _INSTALLERS and any(
                a in ("install", "i", "add", "update", "upgrade") for a in args):
            flags.append(f"pkg-install:{prog}")
        if seg.sep == "&":
            flags.append("backgrounded")

    if reasons:
        return {"verdict": "deny", "reasons": reasons, "flags": flags}
    return {"verdict": "allow", "reasons": [], "flags": flags}


def denial_reason(command: str) -> Optional[str]:
    """Raison de refus structurée, ou None si autorisé."""
    verdict = classify(command)
    if verdict["verdict"] == "deny":
        return "structured block: " + "; ".join(verdict["reasons"])
    return None
