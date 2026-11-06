"""Versioned reference snapshots: specialization, perk and Artifact property definitions.

Kleptichron's definitions are MIT-licensed; the original license is retained beside the
snapshots. Game text remains its authors' content.
"""

import json
import re
from .importer import ROOT

REFERENCE = ROOT / "data/raw/references/2026-10-27"
STAT_KEYS = {
    "HEALTH",
    "ATTACK",
    "INTELLIGENCE",
    "DEFENSE",
    "SPEED",
    "HEALTHATTACK",
    "HEALTHINTELLIGENCE",
    "HEALTHDEFENSE",
    "HEALTHSPEED",
    "ATTACKINTELLIGENCE",
    "ATTACKDEFENSE",
    "ATTACKSPEED",
    "INTELLIGENCEDEFENSE",
    "INTELLIGENCESPEED",
    "DEFENSESPEED",
}


def load(db):
    def definition(key, kind, name, text, meta):
        db.execute(
            "INSERT OR IGNORE INTO entity VALUES(?,?,?,?,?)",
            (key, kind, name, text, json.dumps(meta)),
        )
        db.execute(
            "INSERT OR IGNORE INTO configuration VALUES(?,?,?,?)",
            (key, kind, name, json.dumps(meta)),
        )

    tokens = {
        "IMMUNITY": "Immunity",
        "WARD": "Warded",
        "SHELL": "Shelled",
        "MEND": "Mending",
        "LEECH": "Leeching",
        "IMMUNE": "Immunity",
        "TAUNT": "Taunting",
        "PROTECT": "Protected",
        "SPLASH": "Splashing",
        "BURNED": "Burning",
        "POISON": "Poisoned",
        "SCORN": "Scorned",
        "SILENCE": "Silenced",
        "SLEEP": "Sleeping",
        "STONE": "Stone",
        "BLEED": "Bleeding",
        "BLIGHT": "Blighted",
        "FEAR": "Feared",
    }
    data = json.loads((REFERENCE / "artifact-mods.json").read_text(encoding="utf-8-sig"))
    # An Artifact property's id is its position here, so a new snapshot must keep the order.
    for number, mod in enumerate(data["records"] if isinstance(data, dict) else data):
        if mod["key"] in ("TRAIT", "CASTSPELL"):
            continue
        text = re.sub(
            r"\{CONDNAME_(?:BUFF|DEBUFF)_([^}]+)\}",
            lambda m: tokens.get(m[1], m[1].title()),
            mod["markup"],
        )
        text = re.sub(r"\{STAT_([^}]+)\}", lambda m: m[1].title(), text)
        definition(
            f"artifact_property:{number}",
            "artifact_property",
            mod["name"],
            text,
            {"slot": "stat" if mod["key"] in STAT_KEYS else "trick"},
        )
    db.execute("INSERT INTO entity VALUES('artifact:0','artifact','Artifact','','{}')")
    db.execute(
        "INSERT INTO component VALUES('artifact:0','artifact',NULL,NULL,'artifact_configuration')"
    )
