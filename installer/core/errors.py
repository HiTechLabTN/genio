"""Installer errors + deterministic exit codes."""

EXIT_OK = 0
EXIT_PREFLIGHT_FAIL = 10
EXIT_ALREADY_INSTALLED = 11
EXIT_AMBIGUOUS_INSTALLS = 12
EXIT_DEPS_MISSING = 13
EXIT_DOWNLOAD_FAIL = 14
EXIT_INTEGRITY_FAIL = 15
EXIT_INSTALL_FAIL = 16
EXIT_VERIFY_FAIL = 17
EXIT_BACKUP_FAIL = 18
EXIT_ROLLBACK_FAIL = 19
EXIT_PERMISSION = 20
EXIT_UNSUPPORTED = 21
EXIT_USER_ABORT = 22


class InstallerError(Exception):
    def __init__(self, message, code=EXIT_INSTALL_FAIL, hint=""):
        super().__init__(message)
        self.code = code
        self.hint = hint
