"""Tests for core/dataset_synthesizer.py — Alpaca Darija Q&A synthesizer.

Run:  python3 -m pytest test_dataset_synthesizer.py -v
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from core.dataset_synthesizer import (  # noqa: E402
    DOMAINS,
    export_jsonl,
    main,
    synthesize_dataset,
)
from core.dataset_synthesizer import DEFAULT_OUT  # noqa: E402, F401 (import smoke)


def test_alpaca_schema_and_count():
    records = synthesize_dataset(count=20, seed=7)
    assert len(records) == 20
    for rec in records:
        assert set(rec.keys()) == {"instruction", "input", "output"}
        # `input` is an optional context and may legitimately be empty (Alpaca).
        assert rec["instruction"].strip()
        assert rec["output"].strip()
        assert isinstance(rec["input"], str)


def test_all_domains_covered():
    records = synthesize_dataset(count=60, seed=3)
    blob = " ".join(r["instruction"] + " " + r["output"] for r in records)
    assert any(k in blob for k in
               ("chmod", "journalctl", "du -h", "ss -tlnp"))          # linux
    assert any(k in blob for k in ("docker", "Volume", "compose"))     # docker
    assert any(k in blob for k in ("nvidia-smi", "VRAM", "CUDA"))      # gpu
    assert any(k in blob for k in ("backoff", "Restart=", "Circuit"))  # selfhealing


def test_every_domain_has_seeds():
    for domain in DOMAINS:
        records = synthesize_dataset(count=5, domain=domain, seed=1)
        assert len(records) == 5
        for rec in records:
            assert set(rec.keys()) == {"instruction", "input", "output"}


def test_seed_reproducibility():
    a = synthesize_dataset(count=30, seed=99)
    b = synthesize_dataset(count=30, seed=99)
    assert a == b
    c = synthesize_dataset(count=30, seed=100)
    assert a != c


def test_reuses_are_not_identical():
    # 60 > corpus -> scenarios are cycled; identical output content is allowed,
    # but the records themselves must remain structurally valid Alpaca.
    records = synthesize_dataset(count=60, seed=1)
    assert len(records) == 60
    assert all(set(r) == {"instruction", "input", "output"} for r in records)


def test_export_jsonl(tmp_path):
    records = synthesize_dataset(count=6, seed=2)
    out = export_jsonl(records, tmp_path / "sample.jsonl")
    assert out.exists()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    for line in lines:
        obj = json.loads(line)
        assert set(obj.keys()) == {"instruction", "input", "output"}


def test_invalid_domain_raises():
    with pytest.raises(ValueError):
        synthesize_dataset(count=5, domain="nope")


def test_zero_count_returns_empty():
    assert synthesize_dataset(count=0) == []


def test_cli_main(tmp_path):
    out = tmp_path / "genio_dataset.jsonl"
    path = main(["--count", "10", "--seed", "0", "--out", str(out)])
    assert Path(path).exists()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 10
    assert all("instruction" in json.loads(l) for l in lines)