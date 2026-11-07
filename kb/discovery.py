"""Search over complete canonical components and linked, typed mechanism facets."""

import json
import sqlite3
from .annotations import event_key, named_statuses, trigger_id, trigger_label
from .facts import STAT_AMOUNT, STAT_SET, event, listened
from .messages import _, name as local_name, phrase

CATEGORIES = {
    "status": "Status",
    "stat": "Stat",
    "action": "Action",
    "trigger": "Trigger",
    "class": "Affects class",
    "race": "Affects race",
    "scope": "Scope",
    "minion": "Minion",
}
RELATIONS = {
    "status": {
        "inflicts": "Inflicts",
        "grants": "Grants",
        "always_has": "Always has",
        "triggers_off": "Triggers on",
        "conditions_on": "Requires",
        "modifies": "Modifies",
        "prevents": "Prevents",
        "removes": "Removes",
        "detonates": "Activates",
        "steals": "Steals",
        "interacts": "Other interaction",
    },
    "stat": {
        "increases": "Gains",
        "has_more": "Has more",
        "decreases": "Loses",
        "has_less": "Has less",
        "gain_modifier": "Modifies gains",
        "scales_with": "Scales with",
        "triggers_off": "Triggers on",
        "modifies": "Changes rule",
        "steals": "Steals",
    },
    "action": {
        "performs": "Performs",
        "triggers_off": "Triggers on",
        "additional": "Additional",
        "prevents": "Prevents",
        "modifies": "Modifies",
    },
    "trigger": {"when": "Trigger"},
    "class": {"conditions_on": "Involves", "vs": "Against", "spells": "Spell Class"},
    "race": {"conditions_on": "Involves"},
    "scope": {"target": "Effect target", "actor": "Actor", "trigger_subject": "Trigger subject"},
    "minion": {
        "summons": "Gains／Summon",
        "removes": "Removes",
        "modifies": "Modifies effect",
        "triggers_off": "Triggers on",
    },
}
ACTION_LABELS = {
    "attack": "Attack",
    "attacked": "Attacked",
    "cast": "Cast",
    "targeted_by_cast": "Targeted by a Spell",
    "defend": "Defend",
    "provoke": "Provoke",
    "heal": "Heal",
    "healed": "Healed",
    "deal_damage": "Deal damage",
    "damaged": "Damage taken",
    "kill": "Kill",
    "death": "Death",
    "resurrect": "Resurrect",
    "dodge": "Dodge",
    "timeline_move": "Move timeline",
    "gain_charges": "Gain charges",
    "extra_turn": "Extra turn",
}
ACTION_TRIGGERS = {
    "attack:actor": "attack",
    "attack:target": "attacked",
    "cast:actor": "cast",
    "cast:target": "targeted_by_cast",
    "defend:actor": "defend",
    "provoke:actor": "provoke",
    "heal:actor": "heal",
    "heal:target": "healed",
    "deal_damage:actor": "deal_damage",
    "deal_damage:target": "damaged",
    "kill:actor": "kill",
    "kill:target": "death",
    "resurrect:target": "resurrect",
    "dodge:actor": "dodge",
    "timeline_move:target": "timeline_move",
}
VALUE_LABELS = {
    "*": "Any Minion",
    "*buff": "Random buff",
    "*debuff": "Random debuff",
    "*status": "Any status",
    "@horsemen": "One of the Four Horsemen",
    "@lesser_demon": "Lesser Demon（unspecified）",
    "@buff": "Any buff",
    "@debuff": "Any debuff",
    "all": "All stats",
    "highest_stat": "Highest stat",
    "lowest_stat": "Lowest stat",
    "total_stats": "Total stats",
    "missing_health": "Missing Health",
    "other": "Other",
    "holder": "Holder",
    "caster": "Caster",
    "allies": "All allies",
    "ally": "One ally",
    "enemies": "All enemies",
    "enemy": "One enemy",
    "target": "Current target",
    "trigger_subject": "Trigger subject",
    "attacker": "Attacker",
    "owner": "Owner",
    "relic": "Relic itself",
    "minions": "Minion",
    "random_enemy": "Random enemy",
    "random_ally": "Random ally",
    "adjacent_allies": "Adjacent allies",
    "adjacent_enemies": "Adjacent enemies",
    "adjacent_any": "Adjacent creatures",
    "random_any": "Random creature",
    "any": "Any creature",
}
TYPE_LABELS = {
    "trait": "Trait",
    "creature": "Creature",
    "material": "Material",
    "spell": "Spell Gem",
    "relic": "Relic",
    "specialization": "Specialization",
    "perk": "Character Perk",
}
EXCLUDED = {"artifact", "enchantment"}
VALUE_ALIASES = {("stat", "Health"): "Maximum Health"}
# The kind whose game names label a filter category's values; minions are conditions in the game.
NAMED_VALUES = {"status": "condition", "minion": "condition", "race": "race", "class": "class"}
STATUS_VERBS = {
    "status_modifier": "modifies",
    "prevent_status": "prevents",
    "remove_status": "removes",
    "detonate": "detonates",
}
CREATURE_PARAMS = {
    "race": ("race", "conditions_on"),
    "races": ("race", "conditions_on"),
    "sourceRace": ("race", "conditions_on"),
    "class": ("class", "conditions_on"),
    "spellClass": ("class", "spells"),
    "vsClass": ("class", "vs"),
    "sourceClass": ("class", "vs"),
}
# Residual buckets stay indexed so broader filters still match, but are never offered as options.
UNOFFERED_RELATIONS = {("status", "interacts")}
UNOFFERED_VALUES = {("stat", "other"), ("scope", "other"), ("trigger", "other")}


def merge(units):
    return frozenset(feature for unit in units for feature in unit)


class Discovery:
    def __init__(self, db, cards=None):
        from .cards import Cards

        self.cards = cards or Cards(db)
        components = {
            row[0]: {
                "id": row[0],
                "kind": row[1],
                "name": row[2],
                "description": row[3],
                "image": json.loads(row[4]).get("image"),
            }
            for row in db.execute(
                "SELECT e.id,e.kind,e.name,e.description,e.attrs FROM entity e JOIN component c ON c.id=e.id"
            )
            if row[1] not in EXCLUDED and json.loads(row[4]).get("obtainable", True)
        }
        self.attributes = {}
        for key, attrs in db.execute(
            "SELECT e.id,e.attrs FROM entity e JOIN component c ON c.id=e.id"
        ):
            if key not in components:
                continue
            attrs = json.loads(attrs)
            classified = self.cards.classification.get(key, {})
            found = {
                "class": classified.get("class") or attrs.get("class"),
                "race": classified.get("race"),
                "base": attrs.get("specialization"),
            }
            found = {k: v for k, v in found.items() if v}
            if found:
                self.attributes[key] = found
        carriers = {}
        for source, rel, target in db.execute(
            "SELECT DISTINCT src,rel,dst FROM edge WHERE rel IN ('innate_trait','grants_trait','unlocks_spell') ORDER BY rel,dst"
        ):
            if source in components and target in components:
                carriers.setdefault(source, target)
        self.groups = {}
        self.canonical = {}
        self.references = [
            {"id": k, "kind": t, "name": n, "description": d, "image": json.loads(a).get("image")}
            for k, t, n, d, a in db.execute(
                "SELECT id,kind,name,description,attrs FROM entity WHERE kind IN ('realm','god','shop','acquisition_source')"
            )
        ]
        for key, item in components.items():
            root = carriers.get(key, key)
            self.canonical[key] = root
            canonical = components[root]
            group = self.groups.setdefault(
                root,
                {
                    "entity": canonical,
                    "members": [],
                    "locations": set(),
                    "action": [],
                    "rule": [],
                    "descriptors": [],
                },
            )
            group["members"].append(item)
        for key, location in db.execute(
            """SELECT DISTINCT r.entity_id,e.name FROM route r JOIN entity e ON e.id=r.location
            UNION SELECT g.dst,e.name FROM edge g JOIN route r ON r.entity_id=g.src
            JOIN entity e ON e.id=r.location WHERE g.rel='unlocks_creature'"""
        ):
            root = self.canonical.get(key)
            if root in self.groups:
                self.groups[root]["locations"].add(location)
        self.status_kinds = dict(db.execute("SELECT name,kind FROM mechanic_status"))
        try:
            for key, alias in db.execute("SELECT entity_id,alias FROM entity_alias"):
                if key in components:
                    components[key].setdefault("aliases", []).append(alias)
        except sqlite3.OperationalError:
            pass
        try:
            self.minions = {name for (name,) in db.execute("SELECT name FROM mechanic_minion")}
        except sqlite3.OperationalError:
            self.minions = set()
        for key, body in db.execute("SELECT entity_id,body FROM mechanic_record ORDER BY id"):
            root = self.canonical.get(key)
            if root not in self.groups:
                continue
            record = json.loads(body)
            group = self.groups[root]
            for rule_index, rule in enumerate(record.get("rules", [])):
                units = []
                for action_index, action in enumerate(rule.get("actions", [])):
                    unit = self.features(rule, action)
                    if unit:
                        units.append(unit)
                        group["action"].append(unit)
                        group["descriptors"].append(
                            {
                                "entity_id": key,
                                "rank": record.get("meta", {}).get("rank"),
                                "reference": record["id"],
                                "rule": rule_index,
                                "action": action_index,
                                "unit": unit,
                            }
                        )
                if units:
                    group["rule"].append(merge(units))
        for group in self.groups.values():
            group["component"] = [merge(group["action"])] if group["action"] else []
            item = group["entity"]
            group["kinds"] = {item["kind"]}
            for member in group["members"]:
                if member["kind"] == "creature":
                    group["kinds"].add("creature")
                if member["kind"] == "material":
                    group["kinds"].add("material")

    def features(self, rule, action):
        features = set()

        def add(category, relation, value):
            if relation in RELATIONS.get(category, {}) and value:
                features.add((category, relation, VALUE_ALIASES.get((category, value), value)))

        trigger = rule.get("trigger", {})
        state = event_key(trigger) in ("passive", "non_combat")
        verb = action["verb"]
        params = action.get("params", {})
        magnitude = action.get("magnitude", {})

        def status_features(relation, named, kind=None, random=False, unnamed=False):
            """Each named status with its category; an unnamed one is its category, and random if applied.

            Without a name or category, an unnamed status is any status.
            """
            for status in named:
                status_kind = self.status_kinds.get(status)
                if status_kind in ("buff", "debuff"):
                    add("status", relation(status_kind), "@" + status_kind)
                add("status", relation(status_kind), status)
            if kind and not named:
                add("status", relation(kind), "@" + kind)
                if random:
                    add("status", relation(kind), "*" + kind)
            if unnamed and not kind and not named:
                add("status", relation(None), "*status")

        named = [s for s in action.get("statuses", []) if s]
        kind = action.get("statusKind")
        if verb == "copy" and (named or kind):
            status_features(lambda k: "grants" if k == "buff" else "inflicts", named, kind)
        elif verb == "apply_status":
            if state and not params.get("timing"):
                status_features(lambda k: "always_has", named, kind, True, True)
            else:
                stolen = "stolen" in action.get("qualifiers", [])
                status_features(
                    lambda k: "grants" if k == "buff" else "inflicts", named, kind, not stolen, True
                )
                if stolen:
                    status_features(lambda k: "steals", named, kind, unnamed=True)
        elif verb in STATUS_VERBS:
            status_features(lambda k: STATUS_VERBS[verb], named, kind, unnamed=True)
        elif named:
            status_features(lambda k: "interacts", named)
        tp = trigger.get("params", {})
        status_features(
            lambda k: "triggers_off",
            named_statuses(tp),
            trigger.get("statusKind"),
        )
        for c in rule.get("conditions") or []:
            cp = c.get("params") or {}
            status_features(lambda k: "conditions_on", named_statuses(cp))
            if c.get("type") == "stat_comparison":
                add("stat", "conditions_on", cp.get("stat"))
        if verb == "stat_change":
            stats = action.get("stats", [])
            direction = magnitude.get("direction")
            if STAT_AMOUNT & set(params):
                relation = "gain_modifier"
            elif STAT_SET & set(params) or not direction:
                relation = "modifies"
            else:
                tokens = [event(rule, action, "stat_change:target", "target")]
                gained = not state and listened(tokens[0])
                relation = {
                    ("up", True): "increases",
                    ("down", True): "decreases",
                    ("up", False): "has_more",
                    ("down", False): "has_less",
                }[(direction, gained)]
            for value in stats:
                add("stat", relation, value)
                if "stolen" in action.get("qualifiers", []):
                    add("stat", "steals", value)
        if verb == "stat_rule":
            for value in action.get("stats", []):
                add("stat", "modifies", value)
        add("stat", "scales_with", magnitude.get("scaleStat"))
        add("stat", "triggers_off", tp.get("stat"))
        for value in tp.get("stats", []):
            add("stat", "triggers_off", value)
        for source in [
            action.get("params", {}),
            tp,
            *((c.get("params") or {}) for c in rule.get("conditions") or []),
        ]:
            for key, (category, relation) in CREATURE_PARAMS.items():
                values = source.get(key)
                for value in values if isinstance(values, list) else [values]:
                    add(category, relation, value)
        target = action.get("target")
        if target == "trigger_subject":
            target = trigger.get("subject")
        add("scope", "target", target)
        actor = action.get("actor")
        if actor == "trigger_subject":
            actor = trigger.get("subject")
        add("scope", "actor", actor)

        add("trigger", "when", trigger_id(trigger))
        add("scope", "trigger_subject", trigger.get("subject"))
        if event_key(trigger) in ACTION_TRIGGERS:
            add("action", "triggers_off", ACTION_TRIGGERS[event_key(trigger)])
        if verb in ACTION_LABELS:
            add("action", "additional" if params.get("additional") else "performs", verb)
        if verb == "prevent_action":
            text = params.get("action", "").lower()
            for stem, value in [
                ("attack", "attack"),
                ("cast", "cast"),
                ("defend", "defend"),
                ("provok", "provoke"),
                ("dodg", "dodge"),
            ]:
                if stem in text:
                    add("action", "prevents", value)
        if verb == "activation_modifier":
            text = params.get("what", "").lower()
            for stem, value in [
                ("attack", "attack"),
                ("cast", "cast"),
                ("death", "death"),
                ("resurrect", "resurrect"),
                ("defend", "defend"),
                ("provok", "provoke"),
                ("dodg", "dodge"),
            ]:
                if stem in text:
                    add("action", "modifies", value)
        if verb in ("damage_modifier", "spell_modifier"):
            source = params.get("source", "").lower()
            if "attack" in source:
                add("action", "modifies", "attack")
            if "spell" in source or verb == "spell_modifier":
                add("action", "modifies", "cast")
        if verb in ("summon_minion", "minion_modifier"):
            minion = params.get("minion", "*")
            minion = {
                "Zombie": "Zombies",
                "random minion": "*",
                "random": "*",
                "the same minion": "*",
                "a copy of one of the holder's minions": "*",
                "one of the four horsemen": "@horsemen",
                "the sacrificed Lesser Demon stack": "@lesser_demon",
            }.get(minion, minion)
            if (
                self.minions
                and minion not in self.minions
                and minion not in ("*", "@horsemen", "@lesser_demon")
            ):
                minion = "*"
            add("minion", "summons" if verb == "summon_minion" else "modifies", minion)
        if verb == "remove_minion":
            add("minion", "removes", "*")
        if trigger.get("event") in ("summon_minion", "lose_minion"):
            add("minion", "triggers_off", trigger.get("params", {}).get("minion", "*"))
        return frozenset(features)

    def label(self, category, value):
        if category == "trigger":
            return trigger_label(value)
        if category == "action":
            return _(ACTION_LABELS.get(value, value))
        if value in VALUE_LABELS:
            return _(VALUE_LABELS[value])
        if category in NAMED_VALUES:
            return phrase(local_name(NAMED_VALUES[category], value))
        return _(value)
