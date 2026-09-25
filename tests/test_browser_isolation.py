"""Phase 10 tests — browser isolation + anti-SSRF.

Validateur pur (sans réseau sauf DNS public), isolation cookies réelle
(navigateur headless local, aucun site externe), labels UNTRUSTED.
"""
import sys
import subprocess

sys.path.insert(0, "/data/ai_tools/genio")

from genio_server.tools import browser_tool as bt


def test_ssrf_direct_private_blocked():
    for u in ("http://127.0.0.1:8000/", "http://10.0.0.5/",
              "http://192.168.1.1/", "http://169.254.169.254/",
              "http://[::1]/", "http://0.0.0.0/",
              "http://localhost:8000/api", "http://localhost/"):
        assert bt.is_private_url(u) is not None, u


def test_ssrf_schemes_blocked():
    for u in ("file:///etc/passwd", "data:text/html,hi", "ftp://x/y",
              "gopher://x", "javascript:alert(1)"):
        assert bt.is_private_url(u) is not None, u


def test_ssrf_unresolvable_fail_closed():
    assert bt.is_private_url("https://no-such-host-xyz.invalid/") is not None


def test_public_url_allowed():
    assert bt.is_private_url("https://example.com/") is None


def test_open_blocked_without_browser():
    r = bt.handle({"action": "open", "url": "http://127.0.0.1:9/"})
    assert r["ok"] is False and "SSRF" in r["error"]
    r = bt.handle({"action": "open", "url": "file:///etc/passwd"})
    assert r["ok"] is False


def test_session_cookie_isolation():
    # Navigateur RÉEL mais en sous-processus : Playwright gare une event loop
    # runnante dans le thread appelant, ce qui empoisonnerait asyncio.run()
    # des autres tests du même worker pytest.
    import json
    import subprocess
    code = (
        "import json, sys; sys.path.insert(0, '/data/ai_tools/genio');"
        "from genio_server.tools import browser_tool as bt;"
        "pa, pb = bt.page_for('ph10_A'), bt.page_for('ph10_B');"
        "assert pa is not pb;"
        "pa.context.add_cookies([{'name':'s','value':'A',"
        "'domain':'example.com','path':'/'}]);"
        "ca = {c['name'] for c in pa.context.cookies()};"
        "cb = {c['name'] for c in pb.context.cookies()};"
        "bt.close_session('ph10_A'); bt.close_session('ph10_B');"
        "print(json.dumps({'same_page': pa is pb, 'a_has': 's' in ca,"
        " 'b_has': 's' in cb,"
        " 'cleaned': 'ph10_A' not in bt._SESSION._pages}))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-500:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["a_has"] and not out["b_has"] and out["cleaned"]


def test_close_unknown_session_safe():
    bt.close_session("ph10_never_existed")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
