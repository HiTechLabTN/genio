"""Tests for media/motion_storyboard.py — 4-act Darija motion storyboard.

Run:  python3 -m pytest test_motion_storyboard.py -v
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from media.motion_storyboard import (  # noqa: E402
    SFX_LIBRARY,
    MotionStoryboardGenerator,
    main,
)
from media.motion_storyboard import SCHEMA, TRANSITIONS  # noqa: E402

ACTS = ("hook", "metaphor", "spec_breakdown", "cta")
KNOWN_SFX = set(SFX_LIBRARY)


def make(topic="Choosing CPU / RAM for Home Server"):
    return MotionStoryboardGenerator(topic).build()


def test_schema_version():
    assert make()["schema"] == SCHEMA


def test_top_level_acts_present():
    sb = make()
    for act in ACTS:
        assert act in sb["acts"]
        assert sb["acts"][act]["act"] == act


def test_hook_is_first_5_seconds_with_glitch():
    hook = make()["acts"]["hook"]
    timing = hook["timing_s"]
    assert timing == {"start": 0, "end": 5}
    assert hook["time_code"] == "00:00 - 00:05"
    assert "glitch" in hook["animation"]
    assert "glitch" in {s["trigger"] for s in hook["sfx"]}
    assert hook["warning"] is True


def test_ram_workbench_metaphor_for_cpu_ram_topic():
    metaphor = make("Choosing CPU / RAM for Home Server")["acts"]["metaphor"]
    assert "طاولة" in metaphor["voiceover"]


def test_storage_coffee_metaphor():
    metaphor = make("SSD vs HDD for a media NAS")["acts"]["metaphor"]
    assert "قهوة" in metaphor["voiceover"]


def test_spec_breakdown_card_schema():
    specs = make("GPU management for AI server")["acts"]["spec_breakdown"]["specs"]
    assert len(specs) >= 6
    for card in specs:
        assert set(card.keys()) == {"label", "value", "unit", "color", "highlight"}
        assert card["label"].strip() and card["value"].strip()
    highlights = [c for c in specs if c["highlight"]]
    assert highlights, "at least one highlight card expected"


def test_cta_targets_site_and_slug():
    cta = make()["acts"]["cta"]
    url = cta["target"]["url"]
    assert url.startswith("https://")
    assert "lab.hitech.tn" in url
    assert cta["target"]["platform"] == "website"
    assert url == make()["article_url"]


def test_sfx_triggers_are_known():
    sb = make()
    for act in ACTS:
        triggers = {s["trigger"] for s in sb["acts"][act]["sfx"]}
        assert triggers, f"{act} must carry sfx triggers"
        assert triggers <= KNOWN_SFX


def test_visual_cues_present_for_every_act():
    sb = make()
    for act in ACTS:
        a = sb["acts"][act]
        assert a["animation"] and a["visual_cue"] and a["scene"]


def test_json_serializable_arabic_preserved():
    sb = make("حاويات Docker والشبكات")
    raw = json.dumps(sb, ensure_ascii=False)
    assert "حاويات" in raw
    assert json.loads(raw)["topic"] == "حاويات Docker والشبكات"


def test_unknown_topic_falls_back_to_generic():
    sb = make("عجائب الزمن الغريبة")
    assert len(sb["acts"]["spec_breakdown"]["specs"]) >= 6


def test_transitions_present():
    sb = make()
    assert len(sb["motion"]["transitions"]) == len(TRANSITIONS) == 3


def test_cli_main_saves_json(tmp_path):
    out = tmp_path / "storyboard.json"
    path = main(["--topic", "Docker Volumes persistence", "--out", str(out)])
    assert Path(path).exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["acts"]) == 4