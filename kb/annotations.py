"""Project-owned structured mechanics: rules per trait, spell, perk and relic rank, plus the
status and minion names they use.

Seeded from Kleptichron's Structured Compendium (MIT, see data/annotations/LICENSE) and maintained
here. Corrections belong in these files.
"""

import hashlib
import json

from .importer import ROOT
from .messages import _

ANNOTATIONS = ROOT / "data/annotations"
KINDS = ("traits", "spells", "perks", "relics")

# A trigger either names an event, which side of it the subject is on and when it fires (before
# the event resolves, as it happens, or after), or is one of the non-event types.
NON_EVENT = {
    "passive": "Passive",
    "activated": "On use",
    "non_combat": "Outside battle",
    "other": "Other trigger",
}
PHASES = {
    "battle_start": {"on": "Start of battle", "after": "After start-of-battle effects"},
    "turn_start": {"on": "Start of turn"},
    "turn_end": {"on": "End of turn"},
}
TIMINGS = {"before": "Before", "on": "On", "after": "After"}
EVENTS = {
    "attack:actor": "attack",
    "attack:target": "being attacked",
    "cast:actor": "cast",
    "cast:target": "being targeted by a Spell",
    "heal:actor": "healing",
    "heal:target": "healing received",
    "deal_damage:actor": "damage dealt",
    "deal_damage:target": "damage taken",
    "kill:actor": "kill",
    "kill:target": "death",
    "resurrect:target": "resurrection",
    "defend:actor": "defend",
    "provoke:actor": "provoke",
    "dodge:actor": "dodge",
    "critical_hit:actor": "critical hit",
    "stat_change:target": "stat change",
    "apply_status:target:debuff": "status applied",
    "apply_status:target:buff": "gaining a buff",
    "remove_status:target": "status removed",
    "remove_status:target:buff": "losing a buff",
    "remove_status:target:debuff": "losing a debuff",
    "expire_status:target": "status expiring",
    "expire_status:target:buff": "a buff expiring",
    "expire_status:target:debuff": "a debuff expiring",
    "status_effect:target": "status activation",
    "effect_activation:actor": "effect activation",
    "summon_minion:target": "gaining a Minion",
    "lose_minion:target": "losing a Minion",
    "timeline_move:target": "timeline move",
}


def event_key(trigger):
    """What a rule listens for regardless of timing; a non-event trigger is its type."""
    if "event" not in trigger:
        return trigger.get("type")
    return ":".join(
        part for part in (trigger["event"], trigger.get("role"), trigger.get("statusKind")) if part
    )


def named_statuses(params):
    return [s for s in [params.get("status"), *params.get("statuses", [])] if s]


def trigger_id(trigger):
    return event_key(trigger) + ("@" + trigger["timing"] if "event" in trigger else "")


def trigger_label(value):
    """Label for a `trigger_id`."""
    key, _separator, timing = value.partition("@")
    if not timing:
        return _(NON_EVENT.get(key, key))
    if key in PHASES:
        return _(PHASES[key].get(timing, key))
    return _("{timing} {event}", timing=_(TIMINGS[timing]), event=_(EVENTS.get(key, key)))


def reacts(trigger):
    """Whether a trigger fires off an event, or after a phase's effects."""
    return "event" in trigger and (trigger["event"] not in PHASES or trigger["timing"] == "after")


def read(name):
    data = (ANNOTATIONS / name).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def load_names(db):
    db.executescript("""CREATE TABLE mechanic_status(name TEXT PRIMARY KEY,kind TEXT);
    CREATE TABLE mechanic_minion(name TEXT PRIMARY KEY);""")
    statuses, _ = read("statuses.json")
    db.executemany(
        "INSERT INTO mechanic_status VALUES(?,?)", [(s["name"], s["kind"]) for s in statuses]
    )
    minions, _ = read("minions.json")
    db.executemany("INSERT INTO mechanic_minion VALUES(?)", [(m,) for m in minions])


def game_text(db, key, rank):
    """The text an annotation was written against: the game's, where a sheet replaced it."""
    original = """COALESCE((SELECT o.game_value FROM sheet_override o
                  WHERE o.entity_id=e.id AND o.field='description'),e.description)"""
    if rank:
        for text, attrs in db.execute(
            f"SELECT {original},e.attrs FROM edge g JOIN entity e ON e.id=g.dst WHERE g.src=? AND g.rel='rank_effect'",
            (key,),
        ):
            if int(json.loads(attrs)["rank"]) == rank:
                return text
        return None
    row = db.execute(
        f"SELECT {original} FROM entity e JOIN component c ON c.id=e.id WHERE e.id=?", (key,)
    ).fetchone()
    return row and row[0]


def check_spans(record):
    """Each span quotes the record's text and names an item that exists in it."""
    for span in record.get("spans", []):
        item = record
        for part in span["path"].split(".") if "path" in span else ():
            item = item[int(part)] if isinstance(item, list) else item[part]
        if record["text"].count(span["text"]) <= span.get("nth", 0):
            raise ValueError(f"Span is not a quote of {record['id']}: {span['text']}")


def load(db):
    """Attach each annotation to its component; a game update that changes the text fails here."""
    db.executescript("""CREATE TABLE mechanic_record(id INTEGER PRIMARY KEY,entity_id TEXT,reference_id TEXT,body TEXT,row_id TEXT,rank INTEGER DEFAULT 0);
    CREATE INDEX mechanic_entity ON mechanic_record(entity_id);""")
    normalize = lambda s: " ".join(s.split()).casefold()
    for kind in KINDS:
        filename = kind + ".json"
        records, digest = read(filename)
        source = "annotations:" + filename
        for i, record in enumerate(records):
            key, rank = record.pop("entity"), record.pop("rank", 0)
            text = game_text(db, key, rank)
            if text is None or normalize(text) != normalize(record["text"]):
                raise ValueError(f"Annotation does not match the game text: {key} rank {rank}")
            check_spans(record)
            row = source + ":" + str(i)
            body = json.dumps(record, ensure_ascii=False)
            db.execute(
                "INSERT INTO mechanic_record(entity_id,reference_id,body,row_id,rank) VALUES(?,?,?,?,?)",
                (key, record["id"], body, row, rank),
            )
    db.execute("INSERT INTO meta VALUES('mechanic_schema','annotations-v1')")
