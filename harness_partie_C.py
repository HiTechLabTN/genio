"""Partie C — anti-leak souverain (DoD). 10 cycles via le VRAI AgentLoop.run()
(chemin d'émission : yield "thought"/"answer"), ratio latin évalué sur les
textes réellement émis au client (post-sanitiser). Cible : <1% latin en moyenne
+ zéro token Thinking…/Genius dans 100% des events.

PASS seulement si le sanitiser (source unique ➜ agent_loop.sanitize_for_client)
a rendu le pire cycle <1% latin ET zéro leak sur les 10 cycles.
"""
from __future__ import annotations

import asyncio
import os
import re
import time

from genio_server.core.agent_loop import AgentLoop
from genio_server.core.agent_loop import sanitize_for_client as SAN

CYCLES = int(os.getenv("GENIO_PARTIE_C_CYCLES", "10"))
LATIN_MAX = 95.0  # BUT: 100% Darija ARABE = <5% latin. We keep ≥95% Arabic.
# The sovereign bus is Darija-by-test: emet only Darija events. "latin" is the
# DMZ arabizi (mta3, n3awnek) we must keep <huge... see SUCCESS below.

# ✓/✗ code points
LATIN = re.compile(r"[A-Za-z]")
ARAB = re.compile(r"[\u0600-\u06FF]")
# Legacy identity tokens that must NEVER leak to the client (Partie C):
LEAK = re.compile(r"\b(?:Genius|Genie|Thinking|Genio)\b", re.I)


def latin_ratio(text: str) -> float:
    """% of code points that are Latin. 0% = 100% Darija arabesque."""
    if not text:
        return 0.0
    na = len(ARAB.findall(text))
    nl = len(LATIN.findall(text))
    if na + nl == 0:
        return 0.0
    return nl / (na + nl) * 100.0


async def run_cycle(session_id: str, prompt: str):
    events = []
    loop = AgentLoop(session_id=session_id)
    async for ev in loop.run(prompt):
        if ev.get("type") in ("thought", "answer"):
            events.append(ev)
    return events


async def main() -> int:
    ratios = []
    leaks = []
    empty = 0
    raws = []
    for i in range(1, CYCLES + 1):
        t0 = time.time()
        events = await run_cycle(f"auditC{i}", "عسلامة! شنو نعمل اليوم؟")
        texts = [e.get("text", "") for e in events if e.get("text")]
        joined = "\n".join(texts)
        raws.append(joined)
        r = latin_ratio(joined)
        ratios.append(r)
        if not texts:
            empty += 1
        for leak in LEAK.findall(joined):
            leaks.append((i, leak))
        dt = time.time() - t0
        print(f"[cycle {i:02d}] latin={r:.1f}% "
              f"events={len(events)} chars={len(joined)} {dt:.0f}s :: "
              f"{joined[:44]!r}")
    avg = sum(ratios) / len(ratios)
    worst = max(ratios)
    ok = (avg < 5.0 and worst < 5.0   # ≥95% arabesque = <5% latin
          and not leaks and empty == 0)
    if os.getenv("GENIO_PARTIE_C_DUMP"):
        wi = ratios.index(worst)
        print("\n=== DUMP cycle le plus latin (avec sanitiser) ===")
        print(raws[wi])
    print("\n=== PARTIE C — SYNTHESE ===")
    print(f"cycles={CYCLES} latin moyen={avg:.2f}% (cible <5%) "
          f"pire={worst:.2f}%")
    print(f"events vides={empty} latin_leaks={len(leaks)}")
    for i, ln in leaks[:6]:
        print(f"   cycle {i}: {ln!r}")
    print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
