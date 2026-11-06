"""Check each annotation against the game's own markup and list where they disagree.

The game types statuses, stats, races and classes in its markup; numbers, timing words and
"does not stack" are read from the text. Run with `python -m kb.audit`.
"""

import json
import re
import sqlite3
from collections import Counter, defaultdict

from .annotations import ANNOTATIONS, KINDS, reacts, trigger_id
from .current import SNAPSHOT, records
from .importer import ROOT

REPORT = ROOT / "data/annotation-audit.json"
STATUS_KEYS = {"status", "statuses", "minion", "minions"}
STAT_KEYS = {"stat", "stats", "scaleStat"}
GROUP_KEYS = {
    "race": "race",
    "races": "race",
    "sourceRace": "race",
    "class": "class",
    "classes": "class",
    "spellClass": "class",
    "sourceClass": "class",
    "vsClass": "class",
}
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


def fold(value):
    return " ".join(str(value).split()).casefold()


def walk(value, key=None):
    """Every (key, scalar) pair inside an annotation's rules."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from walk(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v, key)
    else:
        yield key, value


def markup(db):
    """Game markup per (entity, rank); rank 0 for everything but relic bonuses."""
    texts = {}
    for key, body in db.execute(
        "SELECT entity_id,body FROM game_entity WHERE kind IN ('trait','spell','perk')"
    ):
        texts[key, 0] = json.loads(body).get("description", "")
    relics = {
        fold(name.split(",")[0]): key
        for key, name in db.execute("SELECT id,name FROM entity WHERE kind='relic'")
    }
    for god in records("gods.json"):
        key = relics.get(fold(god.get("relicName", "")))
        for i, text in enumerate(god.get("relicBonuses", []) if key else [], 1):
            texts[key, i * 10] = text
    return texts


def typed(text, tokens):
    """What the markup asserts: statuses, stats, races and classes, by display name."""
    found = defaultdict(set)
    for token in re.findall(r"\{([A-Z]+_[^}]*)\}", text):
        name = tokens.get(token)
        group = token.split("_")[0]
        if name and group in ("CONDNAME", "STAT", "RACE", "CLASS"):
            found[group].add(fold(name))
    return found


def claims(record):
    """Names and numbers the rules state in typed fields, and the free text in the rest."""
    found = defaultdict(set)
    numbers = set()
    loose = []
    for key, value in walk(record.get("rules", [])):
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            numbers.add(float(value))
        elif not isinstance(value, str):
            continue
        elif key in STATUS_KEYS:
            found["CONDNAME"].add(fold(value))
        elif key in STAT_KEYS:
            found["STAT"].add(fold(value))
        elif key in GROUP_KEYS:
            found["RACE" if GROUP_KEYS[key] == "race" else "CLASS"].add(fold(value))
        else:
            loose.append(fold(value))
    return found, numbers, " | ".join(loose)


def lead_words(text):
    return {m.group(1) for m in re.finditer(r"(?:^|[.!]\s+)(When|Whenever|After)\b", text)}


def audit(db):
    tokens = json.loads((SNAPSHOT / "tokens.json").read_text(encoding="utf-8-sig"))
    game = markup(db)
    issues = defaultdict(list)
    free = Counter()
    for kind in KINDS:
        for record in json.loads((ANNOTATIONS / (kind + ".json")).read_text(encoding="utf-8")):
            ref = record["id"]
            # Perk text appends a glossary paragraph for each spell it names; that belongs to the spell.
            text = record["text"].split("\n\n")[0]
            raw = game.get((record["entity"], record.get("rank", 0)), "").replace("\\n", "\n")
            raw = raw.split("\n\n")[0]
            if not raw:
                issues["no_markup"].append(ref)
            asserted = typed(raw, tokens)
            claimed, numbers, loose = claims(record)
            for group, label in [
                ("CONDNAME", "status"),
                ("STAT", "stat"),
                ("RACE", "race"),
                ("CLASS", "class"),
            ]:
                # A stat named inside a typed stat such as "Maximum Health" counts as stated.
                missing = {n for n in asserted[group] if not any(n in c for c in claimed[group])}
                untyped = {n for n in missing if n in loose}
                if untyped:
                    issues[label + "_untyped"].append({"id": ref, "names": sorted(untyped)})
                if missing - untyped:
                    issues[label + "_missing"].append(
                        {"id": ref, "names": sorted(missing - untyped)}
                    )
                extra = claimed[group] - asserted[group] if group == "CONDNAME" and raw else set()
                if extra:
                    issues[label + "_unmarked"].append({"id": ref, "names": sorted(extra)})
            absent = {float(n) for n in NUMBER.findall(text)} - numbers
            untyped = {n for n in absent if n in {float(x) for x in NUMBER.findall(loose)}}
            if untyped:
                issues["number_untyped"].append({"id": ref, "numbers": sorted(untyped)})
            if absent - untyped:
                issues["number_missing"].append({"id": ref, "numbers": sorted(absent - untyped)})
            triggers = [r.get("trigger", {}) for r in record.get("rules", [])]
            reacting = {trigger_id(t) for t in triggers if reacts(t)}
            words = lead_words(text)
            if words & {"When", "Whenever"} and "After" not in words:
                after = sorted(t for t in reacting if t.endswith("@after"))
                if after:
                    issues["when_as_after"].append({"id": ref, "triggers": after})
            if "After" in words and not words & {"When", "Whenever"}:
                early = sorted(t for t in reacting if not t.endswith("@after"))
                if early:
                    issues["after_as_when"].append({"id": ref, "triggers": early})
            if (
                "After" in words
                and not reacting
                and any(t.get("type") == "passive" for t in triggers)
            ):
                issues["after_as_passive"].append(ref)
            stacks = record.get("flags", {}).get("stacks")
            if ("does not stack" in text.lower()) != (stacks is False):
                issues["stacking"].append(ref)
            if record.get("flags", {}).get("unmodeled"):
                issues["unmodeled"].append(ref)
            for rule in record.get("rules", []):
                for part in [
                    rule.get("trigger", {}),
                    *rule.get("conditions", []),
                    *rule.get("actions", []),
                ]:
                    for key, value in (part.get("params") or {}).items():
                        if isinstance(value, str) and key not in {
                            *GROUP_KEYS,
                            *STAT_KEYS,
                            *STATUS_KEYS,
                        }:
                            free[key] += 1
    return issues, free


def main():
    db = sqlite3.connect(ROOT / "data/knowledge.sqlite3")
    issues, free = audit(db)
    report = {
        "counts": {k: len(v) for k, v in sorted(issues.items())},
        "free_text_params": dict(free.most_common()),
        "issues": dict(sorted(issues.items())),
    }
    with open(REPORT, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {"counts": report["counts"], "free_text_params": dict(free.most_common(15))}, indent=1
        )
    )


if __name__ == "__main__":
    main()
