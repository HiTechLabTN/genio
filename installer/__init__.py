"""Genio smart installer — layered product installer (stdlib only).

Layout:
    installer/
      bootstrap/    official curl|bash entry (install.sh)
      core/         errors, paths, runner, manifest, state
      detectors/    platform, hardware, software, network, permissions, ports
      discovery/    existing-installation states (no-duplicate rule)
      installers/   standalone prefix installation
      repair/       diagnose + repair per state (backup first)
      update/       safe update with verify + rollback
      rollback/     restore last-known-good
      health/       doctor checks (PASS/WARN/FAIL/N-A)
      security/     install-time security verification
      platform/     systemd unit rendering/installation
      manifests/    unit templates
      tests/        deterministic installer tests (tmp_path)

Entry: ``installer/genio`` (executable) or ``python3 installer/genio <cmd>``.
"""

INSTALLER_VERSION = "1.0.0"
PRODUCT = "genio"
