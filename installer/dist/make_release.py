"""Release archive builder — versioned artifact + checksums (§8/§31).

Produces, from a git checkout:
    genio-<version>.tar.gz        (git archive HEAD: tracked files only)
    genio-<version>.tar.gz.sha256 (integrity)
    genio-<version>.release.json  (release manifest)

No signatures implemented (stated honestly in docs/install).
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _run(argv, cwd):
    p = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(argv)}: {p.stderr[-300:]}")
    return p.stdout.strip()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_archive(archive, checksum_file=None, expected=None):
    """Fail-closed integrity check. Returns hex digest or raises."""
    digest = sha256_file(Path(archive))
    want = expected
    if checksum_file:
        want = Path(checksum_file).read_text().strip().split()[0]
    if want and digest != want:
        raise SystemExit(f"INTEGRITY FAIL: {archive} ({digest} != expected)")
    return digest


def make_release(repo, version, outdir):
    repo, outdir = Path(repo), Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    commit = _run(["git", "-C", str(repo), "rev-parse", "HEAD"], repo)[:12]
    archive = outdir / f"genio-{version}.tar.gz"
    with open(archive, "wb") as fh:
        p = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar.gz",
                            f"--prefix=genio-{version}/", "HEAD"],
                           stdout=fh, timeout=600)
        if p.returncode != 0:
            raise SystemExit("git archive failed")
    digest = sha256_file(archive)
    (outdir / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n")
    manifest = {
        "product": "genio", "version": version, "commit": commit,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifact": archive.name, "sha256": digest,
        "size_bytes": archive.stat().st_size,
        "min_ipc_protocol": "1.0",
        "support": {"status": "SUPPORTED"},
    }
    (outdir / f"genio-{version}.release.json").write_text(json.dumps(manifest, indent=2))
    print(f"release {version} commit={commit} sha256={digest[:16]}… size={archive.stat().st_size}")
    return archive


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: make_release.py <repo> <version> <outdir>")
        raise SystemExit(2)
    make_release(sys.argv[1], sys.argv[2], sys.argv[3])
