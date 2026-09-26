"""Transactional self-healing — Phase 18.

Flow : checkpoint → diagnose → propose → policy → sandboxed apply →
tests → health → COMMIT ou ROLLBACK. Aucune mutation d'état critique sans
autorisation policy ; tout échec de vérification restaure le checkpoint
(octets comparés, preuve de restauration).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class HealingResult:
    status: str  # committed | rolled_back | denied | failed
    diagnosis: str = ""
    applied: List[str] = field(default_factory=list)
    rolled_back: List[str] = field(default_factory=list)
    verified: bool = False
    detail: str = ""


def _read(p: str) -> Optional[bytes]:
    try:
        with open(p, "rb") as f:
            return f.read()
    except Exception:
        return None


class HealingTransaction:
    """Transaction de réparation sur fichiers workspace-scopés."""

    def __init__(self, workspace: str):
        from genio_server.tools.fs_guard import canonicalize
        self.workspace = canonicalize(workspace)
        self._checkpoint: Dict[str, Optional[bytes]] = {}

    def _guarded(self, path: str) -> Optional[str]:
        from genio_server.tools.fs_guard import authorize
        return authorize(path, workspace=self.workspace, for_write=True)

    def checkpoint(self, paths: List[str]) -> Dict[str, bool]:
        """Snapshot octets des cibles (None = fichier inexistant)."""
        saved = {}
        for p in paths:
            if self._guarded(p) is not None:
                saved[p] = False
                continue
            self._checkpoint[p] = _read(p)
            saved[p] = True
        return saved

    def diagnose(self, error_text: str) -> str:
        try:
            from sandbox.self_healer import GenericHealer
            hint = GenericHealer().inspect_and_heal(error_text or "")
            if hint:
                return str(hint)[:1000]
        except Exception:
            pass
        return "no pattern matched; manual diagnosis required"

    def run(self, operations: List[Dict[str, Any]],
            verify: Callable[[], bool],
            policy: str = "DENY",
            diagnosis: str = "") -> HealingResult:
        """Exécute la transaction complète. `operations`: [{path, content}].
        `policy` doit valoir explicitement "ALLOW" sinon refus immédiat."""
        if policy != "ALLOW":
            return HealingResult(status="denied",
                                 detail="policy gate: explicit ALLOW required")
        paths = [str(op.get("path", "")) for op in operations]
        saved = self.checkpoint(paths)
        refused = [p for p, ok in saved.items() if not ok]
        if refused:
            return HealingResult(status="denied", diagnosis=diagnosis,
                                 detail=f"paths refused: {refused}")
        applied: List[str] = []
        try:
            for op in operations:
                path = str(op.get("path"))
                content = op.get("content")
                data = content.encode("utf-8") if isinstance(content, str) \
                    else bytes(content or b"")
                if len(data) > 1_000_000:
                    raise ValueError(f"patch too large: {path}")
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
                applied.append(path)
        except Exception as exc:
            rolled, _proven = self._rollback()
            return HealingResult(status="rolled_back", diagnosis=diagnosis,
                                 applied=applied, rolled_back=rolled,
                                 detail=f"apply failed: {exc}")
        try:
            healthy = bool(verify())
        except Exception as exc:
            healthy = False
            verify_err = str(exc)[:200]
        else:
            verify_err = ""
        if not healthy:
            rolled, proven = self._rollback()
            return HealingResult(
                status="rolled_back", diagnosis=diagnosis, applied=applied,
                rolled_back=rolled if proven else [],
                detail=f"health check failed {verify_err} — "
                       f"rollback proven={proven}")
        self._checkpoint.clear()
        return HealingResult(status="committed", diagnosis=diagnosis,
                             applied=applied, verified=True)

    def _rollback(self) -> tuple:
        """Restaure + retourne (chemins, preuve octets-identiques)."""
        snapshot = dict(self._checkpoint)
        done = []
        for path, data in snapshot.items():
            try:
                if data is None:
                    if os.path.exists(path):
                        os.remove(path)
                else:
                    with open(path, "wb") as f:
                        f.write(data)
                done.append(path)
            except Exception:
                continue
        proven = all(_read(p) == snapshot.get(p) for p in done)
        self._checkpoint.clear()
        return done, proven
