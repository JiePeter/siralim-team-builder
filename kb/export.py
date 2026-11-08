"""Write the static runtime data pack. Run: python -m kb.export [--out app/public/data]"""

import argparse
import base64
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from .facts import render
from .matching import worded
from .messages import _, use as use_messages
from .planner import planner_pack
from .importer import ROOT, DEFAULT_DB
from .knowledge import Knowledge, database
from .discovery import (
    CATEGORIES,
    RELATIONS,
    TYPE_LABELS,
    UNOFFERED_RELATIONS,
    UNOFFERED_VALUES,
    VALUE_ALIASES,
)

DEFAULT_OUT = ROOT / "app/public/data"
STATE_DIR = ROOT / "data/export-state"
PACK_FOLDERS = ("objects", "synergies", "cards")
TOTAL_BUDGET = 500 * 1024 * 1024
FILE_BUDGET = 5 * 1024 * 1024
RULE_ID_LENGTH = 6
FACT_ID_LENGTH = 5
POINT_ID_LENGTH = 4
OBJECT_ID_LENGTH = 6
SYNERGY_RELATIONS = (
    "Event chain",
    "Action modifier",
    "Event count",
    "Amplification",
    "Status condition",
    "Minion support",
    "Scope overlap",
)
SYNERGY_STRENGTHS = ("supported", "conditional", "reference", "context")
RELATION_CODES = {name: code for code, name in enumerate(SYNERGY_RELATIONS)}
STRENGTH_CODES = {name: code for code, name in enumerate(SYNERGY_STRENGTHS)}
CHANGED_FILES_SHOWN = 20
CARD_FIELDS = ("effects", "facts", "attrs", "classification")
SYNERGY_OBJECT_FIELDS = ("name", "kind", "image", "classification")
SYNERGY_ITEM_FIELDS = (
    "id",
    "relation",
    "strength",
    "shared_constraints",
    "source_perk",
)
SYNERGY_WITNESS_FIELDS = ("requirements", "requires_target_side")
SYNERGY_RULE_FIELDS = ("text", "segments", "conditions", "reference", "rank")


class BudgetError(Exception):
    pass


def file_stem(key, taken):
    """Ids contain ':' and mixed case; Windows and URLs need a safe, case-insensitively unique name."""
    stem = re.sub(r"[^A-Za-z0-9_-]", ".", key)
    if stem.casefold() in taken:
        stem += "-" + hashlib.sha1(key.encode()).hexdigest()[:8]
    taken.add(stem.casefold())
    return stem


def object_path(key):
    """Mirrors objectPath in app/src/data/index.ts; the manifest lists only pages stored elsewhere."""
    return "objects/" + re.sub(r"[^A-Za-z0-9_-]", ".", key) + ".json"


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def state_path(out):
    return STATE_DIR / (hashlib.sha1(str(out.resolve()).encode()).hexdigest()[:12] + ".json")


def input_fingerprint(knowledge):
    """Everything synergy files read besides mechanic records: code, raw data and other tables."""
    digest = hashlib.sha256()
    code = sorted((ROOT / "kb").glob("*.py"))
    raw = sorted(path for path in (ROOT / "data/raw").rglob("*") if path.is_file())
    messages = sorted((ROOT / "data/localization").glob("*/messages.json"))
    for path in code + raw + messages:
        digest.update(path.relative_to(ROOT).as_posix().encode() + path.read_bytes())
    with database(knowledge.path) as db:
        for (table,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name<>'mechanic_record' ORDER BY name"
        ).fetchall():
            for row in db.execute(f"SELECT * FROM {table}"):
                digest.update(repr(tuple(row)).encode())
    digest.update(json.dumps(knowledge.mechanics().spell_facts, sort_keys=True).encode())
    return digest.hexdigest()


def synergy_keys(knowledge, owners, perks_of):
    """The key under which each synergy file stays valid from one export to the next."""
    salt = input_fingerprint(knowledge)
    engine = knowledge.mechanics()

    def key(*parts):
        return hashlib.sha256("\n".join((salt, *parts)).encode()).hexdigest()

    keys = {o: key(engine.fingerprint(knowledge.synergy_owner(o))) for o in owners}
    for specialization, perks in perks_of.items():
        keys[specialization] = key(*(keys[p] for p in perks if p in keys))
    return keys


class PackWriter:
    """Leaves files untouched whose content the last export with the same state already wrote."""

    def __init__(self, out, state=None):
        self.out = out
        self.state = state
        self.previous = {}
        if state and state.exists():
            self.previous = json.loads(state.read_text(encoding="utf-8"))
            # A state left behind by an interrupted export would vouch for files it did not finish.
            state.unlink()
        self.present = {}
        for folder in ("", *PACK_FOLDERS):
            (out / folder).mkdir(parents=True, exist_ok=True)
            for entry in os.scandir(out / folder):
                if entry.is_file() and (folder or entry.name.endswith(".json")):
                    self.present[f"{folder}/{entry.name}" if folder else entry.name] = (
                        entry.stat().st_size
                    )
        self.files = {}
        self.owners = {}
        self.changed = []

    def known(self, relative):
        return self.previous.get("files", {}).get(relative)

    def keep(self, relative):
        """Whether a file another check found current is still on disk as it was written."""
        written = self.known(relative)
        if written and self.present.get(relative) == written[1]:
            self.files[relative] = written
            return True
        return False

    def write(self, relative, data):
        written = [hashlib.sha256(data).hexdigest(), len(data)]
        self.files[relative] = written
        if self.known(relative) != written or self.present.get(relative) != len(data):
            (self.out / relative).write_bytes(data)
            self.changed.append(relative)

    def finish(self, tables):
        for relative in self.present.keys() - self.files.keys():
            (self.out / relative).unlink()
        if self.state:
            self.state.parent.mkdir(parents=True, exist_ok=True)
            self.state.write_text(
                json.dumps({"files": self.files, "owners": self.owners, **tables.shared()}),
                encoding="utf-8",
            )


def joined(segments):
    return "".join(part["text"] for part in segments)


def segments_only(item, text="description"):
    """Drop text that the browser can rebuild by joining segments."""
    if "segments" in item and item.get(text) == joined(item["segments"]):
        return {k: v for k, v in item.items() if k != text}
    return item


ARTIFACT_FORMULAS = ROOT / "data/annotations/artifact-formulas.json"


def artifact_formulas():
    """Per-property value formulas, keyed by property name, plus the primary stat of each type."""
    data = json.loads(ARTIFACT_FORMULAS.read_text(encoding="utf-8"))
    return data["properties"], data["primary"]


BASE_ANOINTMENTS = 5
ANOINTMENT_BONUS = re.compile(
    r"equip (\d+) additional Anointments(?:, or (\d+) if you've ascended all other)?"
)

# A Perk whose text says this counts at full rank whenever its specialization is the base.
ALWAYS_ACTIVE = "always active while your specialization"


def anointment_capacity(perks):
    """Anointments every character holds, and those each Perk adds while it is active."""
    bonuses = {}
    for perk in perks:
        found = ANOINTMENT_BONUS.search(perk["description"])
        if found:
            count, all_ascended = found.groups()
            bonuses[perk["id"]] = {"count": int(count)} | (
                {"all_ascended": int(all_ascended)} if all_ascended else {}
            )
    if not bonuses:
        raise ValueError("No Perk adds Anointments")
    return {"base": BASE_ANOINTMENTS, "perks": bonuses}


def compact_catalog(catalog, formulas=None, original=None):
    """`original` is the catalog in the game's English; a localized catalog reads rules from it."""
    properties, primary = formulas or artifact_formulas()
    original = original or catalog
    result = dict(catalog)
    result["anointments"] = anointment_capacity(original["perks"])
    for group in ("perks", "artifact_properties", "spells"):
        result[group] = [segments_only(item) for item in catalog[group]]
    always_active = {
        p["id"] for p in original["perks"] if ALWAYS_ACTIVE in p["description"].lower()
    }
    result["perks"] = [
        {**perk, "always_active": True} if perk["id"] in always_active else perk
        for perk in result["perks"]
    ]
    english = {p["id"]: p["name"] for p in original["artifact_properties"]}
    missing = [name for name in english.values() if name not in properties]
    if missing:
        raise ValueError("No Artifact formula for " + ", ".join(missing))
    result["artifact_properties"] = [
        {**item, "formula": properties[english[item["id"]]]}
        for item in result["artifact_properties"]
    ]
    keys = {s["id"]: s["name"] for s in original["specializations"]}
    result["specializations"] = [
        {**s, "key": keys.get(s["id"], s["name"])} for s in result["specializations"]
    ]
    result["artifact_primary"] = primary
    result["relics"] = [
        {**relic, "effects": [segments_only(e) for e in relic["effects"]]}
        for relic in catalog["relics"]
    ]
    return result


def point_event(relation, event):
    """An event's display text; the engine names trigger events in the pack's language already."""
    if relation in ("Status condition", "Minion support"):
        return worded(event)
    if relation == "Amplification":
        return _(event)
    return event


class SynergyTables:
    """Target rules, facts and object fields repeat across owners; the pack stores each once.

    Only the fields the Synergies card reads are kept: the owner's own rule, rule scopes,
    path direction and status are not shown and are dropped. A fact is stored as its layer,
    name and display text. Rules and facts are keyed by their content, so that one changed rule
    leaves every file that does not use it byte-identical.

    A point is what a link meets on: its relation and event. Its degree is the number of owners
    with a link through it, counted over every file of the pack, reused or written.
    """

    def __init__(self):
        self.rules, self.objects, self.facts, self.perks, self.points = {}, {}, {}, {}, {}
        self.fact_keys, self.rule_keys = {}, {}
        self.degrees = defaultdict(int)

    @staticmethod
    def content_key(value, length):
        canonical = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
        return base64.urlsafe_b64encode(hashlib.sha256(canonical).digest())[:length].decode()

    def store(self, table, value, length):
        key = self.content_key(value, length)
        if table.setdefault(key, value) != value:
            raise ValueError("Pack id collision: " + key)
        return key

    def fact_ids(self, tokens):
        ids = []
        for token in tokens:
            token = tuple(token)
            key = self.fact_keys.get(token)
            if key is None:
                stored = [token[0], token[1], render(token)]
                key = self.fact_keys[token] = self.store(self.facts, stored, FACT_ID_LENGTH)
            ids.append(key)
        return ids

    def rule(self, rule):
        key = self.rule_keys.get(id(rule))
        if key is None:
            stored = segments_only(
                {k: v for k, v in rule.items() if k in SYNERGY_RULE_FIELDS}, "text"
            )
            stored["conditions"] = self.fact_ids(stored.get("conditions", []))
            key = self.rule_keys[id(rule)] = self.store(self.rules, stored, RULE_ID_LENGTH)
        return key

    def compact(self, result):
        """Each item as a row: object, point, strength, rule, then shared constraints,
        requirements, required target side, source rank and source Perk, without trailing blanks."""
        rows = []
        used = {"rules": set(), "facts": set(), "objects": set(), "perks": set(), "points": set()}
        for item in result["items"]:
            lifted = {"id": item["id"], **{k: item[k] for k in SYNERGY_OBJECT_FIELDS if k in item}}
            key = self.content_key(item["id"], OBJECT_ID_LENGTH)
            if self.objects.setdefault(key, lifted) != lifted:
                raise ValueError("Synergy object fields differ for " + item["id"])
            witness = item.get("witness", {})
            constraints = self.fact_ids(item.get("shared_constraints", []))
            requirements = self.fact_ids(witness.get("requirements") or [])
            rule = self.rule(item["target_rule"])
            point = self.store(
                self.points,
                [
                    RELATION_CODES[item["relation"]],
                    point_event(item["relation"], item["event_label"]),
                ],
                POINT_ID_LENGTH,
            )
            perk = None
            if item.get("source_perk"):
                perk = self.store(self.perks, item["source_perk"], OBJECT_ID_LENGTH)
                used["perks"].add(perk)
            row = [
                key,
                point,
                STRENGTH_CODES[item["strength"]],
                rule,
                constraints,
                requirements,
                witness.get("requires_target_side") or None,
                item.get("source_rule", {}).get("rank") or None,
                perk,
            ]
            while not row[-1]:
                row.pop()
            rows.append(row)
            used["rules"].add(rule)
            used["objects"].add(key)
            used["points"].add(point)
            used["facts"].update(constraints, requirements)
        for point in used["points"]:
            self.degrees[point] += 1
        return {"items": rows}, {name: sorted(keys) for name, keys in used.items()}

    def adopt(self, entry, previous):
        """Bring in what a synergy file written by an earlier export refers to."""
        for key in entry["rules"]:
            self.rules[key] = previous["rules"][key]
            for fact in self.rules[key]["conditions"]:
                self.facts[fact] = previous["facts"][fact]
        for key in entry["facts"]:
            self.facts[key] = previous["facts"][key]
        for key in entry["objects"]:
            self.objects[key] = previous["objects"][key]
        for key in entry["perks"]:
            self.perks[key] = previous["perks"][key]
        for key in entry["points"]:
            self.points[key] = previous["points"][key][:2]
            self.degrees[key] += 1

    def shared(self):
        return {
            "relations": SYNERGY_RELATIONS,
            "strengths": SYNERGY_STRENGTHS,
            "objects": dict(sorted(self.objects.items())),
            "perks": dict(sorted(self.perks.items())),
            "points": {k: [*v, self.degrees[k]] for k, v in sorted(self.points.items())},
            "rules": dict(sorted(self.rules.items())),
            "facts": dict(sorted(self.facts.items())),
        }


def wire_key(item):
    """Identifies a Synergy by the fields that reach the pack."""
    witness = item.get("witness", {})
    rule = item.get("target_rule", {})
    return json.dumps(
        [
            {k: item.get(k) for k in SYNERGY_ITEM_FIELDS},
            {k: witness.get(k) for k in SYNERGY_WITNESS_FIELDS},
            item.get("source_rule", {}).get("rank"),
            {k: rule.get(k) for k in SYNERGY_RULE_FIELDS},
        ],
        sort_keys=True,
        ensure_ascii=False,
    )


def base_synergies(perks):
    """A Character base has no rule of its own; its Synergies are those of its Perks.

    The base's own Perks are active with it, so they are not suggested.
    """
    items, seen = [], set()
    for perk, result in perks.items():
        for item in result["items"]:
            item = item | {"source_perk": perk}
            key = wire_key(item)
            if item["id"] not in perks and key not in seen:
                seen.add(key)
                items.append(item)
    return {"items": items}


def discovery_pack(found):
    """Everything Discovery.query and the text search read, with features interned into one table.

    Group names and words are not stored: the browser rebuilds them from the members and locations.
    """
    features, index = [], {}

    def unit(value):
        ids = []
        for feature in sorted(value):
            if feature not in index:
                index[feature] = len(features)
                features.append(list(feature))
            ids.append(index[feature])
        return ids

    groups = []
    for root, group in found.groups.items():
        if group["entity"] not in group["members"]:
            raise ValueError("Group root is not a member: " + root)
        # The group's entity is its member with the group id; canonical ids follow membership.
        groups.append(
            {
                "id": root,
                "members": group["members"],
                "locations": sorted(group["locations"]),
                "kinds": sorted(group["kinds"]),
                "action": [unit(u) for u in group["action"]],
                "rule": [unit(u) for u in group["rule"]],
                "component": [unit(u) for u in group["component"]],
                # descriptors[i].unit is action[i]; the browser restores the unit by position.
                "descriptors": [
                    {k: d[k] for k in ("entity_id", "rank", "reference", "rule", "action")}
                    for d in group["descriptors"]
                ],
            }
        )
        if [d["unit"] for d in group["descriptors"]] != group["action"]:
            raise ValueError("Descriptor order differs from action units for " + root)
    labels = defaultdict(dict)
    for category, _relation, value in features:
        labels[category][value] = found.label(category, value)
    return {
        "features": features,
        "groups": groups,
        "references": found.references,
        "attributes": found.attributes,
        "status_kinds": found.status_kinds,
        "labels": {
            "categories": {k: _(v) for k, v in CATEGORIES.items()},
            "relations": {
                category: {k: _(v) for k, v in relations.items()}
                for category, relations in RELATIONS.items()
            },
            "types": {k: _(v) for k, v in TYPE_LABELS.items()},
            "values": labels,
            "unoffered_relations": sorted(UNOFFERED_RELATIONS),
            "unoffered_values": sorted(UNOFFERED_VALUES),
            "value_aliases": [[c, v, alias] for (c, v), alias in VALUE_ALIASES.items()],
        },
    }


def card_shards(found):
    """Card fields Discovery.query attaches to each result, grouped by kind."""
    shards = defaultdict(dict)
    keys = [m["id"] for g in found.groups.values() for m in g["members"]]
    keys += [item["id"] for item in found.references]
    for key in dict.fromkeys(keys):
        card = found.cards.card(key)
        fields = {k: card[k] for k in CARD_FIELDS if k in card}
        if "effects" in fields:
            fields["effects"] = [segments_only(e) for e in fields["effects"]]
        shards[card["kind"]][key] = fields
    return shards


TRAIT_RELATIONS = ("innate_trait", "grants_trait")
SLOT_KINDS = {
    "base": ["creature"],
    "fusion": ["creature"],
    "artifact": ["material", "artifact"],
    "relic": ["relic"],
    "spells": ["spell"],
}
ARTIFACT_SLOTS = {"stats": 3, "tricks": 2}


def named(db, kind, name):
    row = db.execute("SELECT id FROM entity WHERE kind=? AND name=?", (kind, name)).fetchone()
    if not row:
        raise ValueError(f"No {kind} named {name}")
    return row[0]


def team_rules(db, replacements=()):
    """Database facts that team validation and build effects read beyond catalog.json.

    Ids repeat too far apart for gzip to share them, so the other tables refer to a component by
    its position in the component lists, taken in key order.
    """
    components = defaultdict(list)
    for key, kind in db.execute("SELECT id,kind FROM component ORDER BY kind,id"):
        components[kind].append(key)
    compatibility, choices, potency = {}, {}, []
    for key, kind, name, attrs in db.execute(
        "SELECT id,kind,name,attrs FROM entity WHERE kind IN ('spell','enchantment') ORDER BY id"
    ):
        attrs = json.loads(attrs)
        if kind == "spell" and attrs.get("property_compatibility") is not None:
            compatibility[key] = attrs["property_compatibility"]
        if kind == "enchantment" and attrs.get("game_property_ids"):
            choices[key] = attrs["game_property_ids"]
            if name.startswith("Potency Based On"):
                potency += attrs["game_property_ids"]
    if len(potency) < 2:
        raise ValueError("No Potency Based On properties")
    traits = defaultdict(dict)
    carriers = db.execute(
        "SELECT DISTINCT src,rel FROM edge JOIN component c ON c.id=src WHERE rel IN (?,?) ORDER BY src,rel",
        TRAIT_RELATIONS,
    ).fetchall()
    for key, rel in carriers:
        # Same statement as build_effects, so multi-trait carriers keep its order.
        traits[key][rel] = [
            r[0]
            for r in db.execute("SELECT DISTINCT dst FROM edge WHERE src=? AND rel=?", (key, rel))
        ]
    position = {key: i for i, key in enumerate(k for ids in components.values() for k in ids)}
    # A trait whose text says it does not stack counts once in the whole party.
    unstackable = [
        r[0]
        for r in db.execute(
            "SELECT e.id FROM entity e JOIN component c ON c.id=e.id "
            "WHERE e.kind='trait' AND lower(e.description) LIKE '%does not stack%' ORDER BY e.id"
        )
    ]

    def at(key):
        if key not in position:
            raise ValueError("Team rules refer to a non-component: " + key)
        return position[key]

    return {
        "components": components,
        "property_compatibility": [[at(k), v] for k, v in compatibility.items()],
        "property_choices": choices,
        "traits": [
            [at(k), {rel: [at(t) for t in found] for rel, found in carried.items()}]
            for k, carried in traits.items()
        ],
        "unstackable": [at(k) for k in unstackable],
        "slot_kinds": SLOT_KINDS,
        # Traits and perks raise a creature's Spell Gem count up to `most` and lift the class match.
        "spell_gems": {
            "most": 8,
            "properties": 3,
            "any_class": named(db, "enchantment", "Class Swap"),
        },
        "artifact_slots": ARTIFACT_SLOTS,
        "potency_sources": sorted(potency),
        # [owner, Relic Rank or 0, whether it can stop only its holder's events, whether it always
        # stops them, [[listener, whether the listener's subject is its own holder], ...]]
        "replacements": [
            [
                at(r["owner"]),
                r["rank"] or 0,
                int(r["set"] == "holder"),
                int(r["certain"]),
                [[at(target), int(holder)] for target, holder in r["listeners"]],
            ]
            for r in replacements
        ],
    }


def check_budget(sizes):
    total = sum(sizes.values())
    large = sorted((size, path) for path, size in sizes.items() if size > FILE_BUDGET)
    problems = []
    if total > TOTAL_BUDGET:
        problems.append(f"total {total / 2**20:.1f} MB exceeds {TOTAL_BUDGET / 2**20:.0f} MB")
    problems += [f"{path} is {size / 2**20:.1f} MB" for size, path in large]
    if problems:
        raise BudgetError("Data pack over budget: " + "; ".join(problems))


def report(sizes, out=print):
    mb = lambda n: f"{n / 2**20:8.2f} MB"
    total = sum(sizes.values())
    out(f"Files: {len(sizes)}  Total: {mb(total)}")
    for prefix in ("objects/", "synergies/", "cards/"):
        part = [s for p, s in sizes.items() if p.startswith(prefix)]
        out(f"  {prefix:<12}{len(part):6} files {mb(sum(part))}")
    rest = {p: s for p, s in sizes.items() if "/" not in p}
    for path, size in sorted(rest.items()):
        out(f"  {path:<24}{mb(size)}")
    out("Largest files:")
    for path, size in sorted(sizes.items(), key=lambda x: -x[1])[:10]:
        out(f"  {mb(size)}  {path}")


# Provenance kept in the knowledge base for audits; the browser never reads it.
OBJECT_ID = re.compile(r'"([a-z_]+:[^"\\]+)"')


def export(out, knowledge, objects=None, owners=None, state=None, log=lambda line: None):
    """Write the pack and return {relative path: bytes}. objects/owners limit the export for tests.

    A state file lets the next export reuse synergy files whose inputs did not change and leave
    unchanged files untouched; the result is the same as without it.
    """
    out = Path(out)
    writer = PackWriter(out, state)
    linked = set()

    def write(relative, value):
        data = encode(value)
        linked.update(OBJECT_ID.findall(data.decode("utf-8")))
        writer.write(relative, data)
        return relative

    with database(knowledge.path) as db:
        meta = dict(db.execute("SELECT key,value FROM meta"))
        use_messages(meta.get("locale", "en"), json.loads(meta.get("names", "{}")))
        if objects is None:
            objects = [r[0] for r in db.execute("SELECT id FROM entity ORDER BY id")]
        carriers = [
            r[0]
            for r in db.execute(
                "SELECT DISTINCT src FROM edge WHERE rel IN ('innate_trait','grants_trait') ORDER BY src"
            )
        ]
        if meta.get("localized"):
            # The rules are derived from the game's English text.
            with database(DEFAULT_DB) as english:
                rules = team_rules(english, Knowledge(DEFAULT_DB).mechanics().replacements())
        else:
            rules = team_rules(db, knowledge.mechanics().replacements())
    manifest = {
        "game_version": meta["game_version"],
        "objects": {},
        "cards": {},
    }

    catalog = knowledge.build_catalog()
    original = Knowledge(DEFAULT_DB).build_catalog() if meta.get("localized") else None
    write("catalog.json", compact_catalog(catalog, original=original))
    write("team-rules.json", rules)
    with database(DEFAULT_DB) as english:
        write("planner.json", planner_pack(english))
    write("gem-properties.json", knowledge.gem_properties())

    engine = knowledge.mechanics()
    if owners is None:
        owners = sorted(engine.nodes)
    taken, files, tables = set(), {}, SynergyTables()
    perks_of = {
        spec["id"]: [p["id"] for p in catalog["perks"] if p["specialization"] == spec["name"]]
        for spec in catalog["specializations"]
    }
    selected = set(owners)
    keys = synergy_keys(knowledge, owners, perks_of) if state else {}

    def connections(owner):
        if owner in selected:
            return knowledge.connections(owner, compact=True)
        return {"items": []}

    def result_of(owner):
        if owner in perks_of:
            return base_synergies({p: connections(p) for p in perks_of[owner]})
        return connections(owner)

    for owner in dict.fromkeys([*owners, *perks_of]):
        key = keys.get(owner)
        entry = writer.previous.get("owners", {}).get(owner)
        reusable = key is not None and entry is not None and entry["key"] == key
        if reusable and entry["file"] is None:
            writer.owners[owner] = entry
            continue
        result = None if reusable else result_of(owner)
        if result is not None and not result["items"]:
            writer.owners[owner] = {"key": key, "file": None}
            continue
        relative = f"synergies/{file_stem(owner, taken)}.json"
        if reusable and entry["file"] == relative and writer.keep(relative):
            tables.adopt(entry, writer.previous)
            writer.owners[owner] = entry
        else:
            compact, used = tables.compact(result or result_of(owner))
            writer.write(relative, encode(compact))
            writer.owners[owner] = {"key": key, "file": relative, **used}
        files[owner] = relative
    write("synergy-rules.json", tables.shared())
    synergies = {}
    for key in carriers:
        owner = knowledge.synergy_owner(key)
        if owner in files:
            synergies[key] = files[owner]
    synergies.update(files)

    pages = {}
    for key in objects:
        page = knowledge.ability(key)
        if page is None:
            continue
        # Every member of a race would repeat the same list; the browser reads it from one file.
        page = {**page, "family": []}
        if key in synergies:
            page["synergies"] = synergies[key]
        pages[key] = page

    write("families.json", dict(sorted(knowledge.page_tables().family.items())))
    found = knowledge.discovery()
    write("discovery.json", discovery_pack(found))
    for kind, cards in sorted(card_shards(found).items()):
        manifest["cards"][kind] = write(f"cards/{kind}.json", cards)

    # Pages are written only when search, cards, the catalog or another reachable page links to them.
    encoded = {key: encode(page) for key, page in pages.items()}
    reachable, pending = set(), [key for key in linked if key in pages]
    while pending:
        key = pending.pop()
        if key in reachable:
            continue
        reachable.add(key)
        found_ids = OBJECT_ID.findall(encoded[key].decode("utf-8"))
        pending.extend(k for k in found_ids if k in pages and k not in reachable)
    taken = set()
    for key, data in encoded.items():
        if key not in reachable:
            continue
        relative = f"objects/{file_stem(key, taken)}.json"
        writer.write(relative, data)
        if relative != object_path(key):
            manifest["objects"][key] = relative

    manifest["pack"] = hashlib.sha256(encode(sorted(writer.files.items()))).hexdigest()[:12]
    writer.write("manifest.json", encode(manifest))
    writer.finish(tables)
    log(f"Changed files: {len(writer.changed)}")
    for relative in writer.changed[:CHANGED_FILES_SHOWN]:
        log(f"  {relative}")
    return {relative: size for relative, (_, size) in writer.files.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    sizes = export(args.out, Knowledge(args.db), state=state_path(args.out), log=print)
    report(sizes)
    try:
        check_budget(sizes)
    except BudgetError as error:
        raise SystemExit(str(error))


if __name__ == "__main__":
    main()
