"""RC 29.2 : strict-sans-clé refuse le boot ; dev-sans-clé démarre."""
import os
import subprocess
import sys

def boot(env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    p = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'/data/ai_tools/genio');"
         "import genio_server.server.main as m; print('BOOTED')"],
        capture_output=True, text=True, env=env, cwd="/data/ai_tools/genio")
    return p.returncode, (p.stdout + p.stderr)

def test_strict_without_key_refuses_boot():
    rc, out = boot({"GENIO_SECURITY_MODE": "strict", "GENIO_API_KEY": ""})
    assert rc != 0 and "GENIO_API_KEY" in out, out[-400:]

def test_strict_with_key_boots():
    rc, out = boot({"GENIO_SECURITY_MODE": "strict", "GENIO_API_KEY": "rc-test-key"})
    assert rc == 0 and "BOOTED" in out, out[-400:]

def test_dev_without_key_boots():
    rc, out = boot({"GENIO_SECURITY_MODE": "", "GENIO_ENV": "dev", "GENIO_API_KEY": ""})
    assert rc == 0 and "BOOTED" in out, out[-400:]

def test_prod_without_key_refuses_boot():
    rc, out = boot({"GENIO_ENV": "prod", "GENIO_API_KEY": ""})
    assert rc != 0, out[-400:]
