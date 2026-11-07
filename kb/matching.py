"""Requirements checked against an actual action."""

import re

from .messages import _, name as local_name, phrase


def normal(value):
    return " ".join(str(value or "").casefold().split())


def stat(value):
    name = normal(value)
    return "health" if name in ("health", "maximum health", "max health") else name


def qualitative(text):
    """Drop magnitudes (percentages, counts, caps) but keep what they qualify."""
    text = re.sub(r"\s*\([^)]*\d[^)]*\)", "", text)
    text = re.sub(
        r"\b(below|above|exceeds?|over|under|within|than)\s+\d+(?:\.\d+)?%(?:\s+of\s+[^,;]+)?",
        r"\1 threshold",
        text,
    )
    text = re.sub(r",?\s*\b\d+ per \w+", "", text)
    return re.sub(r"\b\d+(?:\.\d+)?%?\s+(?:of\s+)?", "", text)


def frozen(value):
    return tuple(frozen(v) for v in value) if isinstance(value, list) else value


def named(kind, text):
    """One or more "/"-joined game names of a kind, in the pack's language."""
    return "/".join(local_name(kind, part) for part in text.split("/"))


def worded(text):
    """An annotation's value: status and minion names, or what the pack's language lists."""
    return "/".join(phrase(local_name("condition", part)) for part in text.split("/"))


def spell_class_text(text):
    return _("Requires a {spell_class} spell", spell_class=named("class", text))


def spell_type_text(text):
    return _("Requires spell type: {spell_type}", spell_type=phrase(text.capitalize()))


NAMED_QUALIFIERS = {"race": "race", "sourceRace": "race", "class": "class"}


def qualifier_text(key, value):
    booleans = {
        "manual": ("Automatic casts", "Manual casts"),
        "forced": ("Voluntary action", "Forced action"),
        "onTurn": ("Outside its own turn", "On its own turn"),
        "singleTarget": ("Multi-target spell", "Single-target spell"),
        "survived": ("Creature does not survive", "Requires survival"),
        "otherCreaturesOnly": ("Includes the holder", "Other creatures only"),
        "byRelicOrBearer": ("Other source", "Caused by the Relic or its bearer"),
        "self": ("Excludes self", "Self only"),
        "others": ("Includes self", "Other creatures only"),
        "first": ("Later occurrence", "First occurrence only"),
    }
    if type(value) is bool:
        if key in booleans:
            return _(booleans[key][int(value)])
        what = phrase(re.sub(r"(?<!^)(?=[A-Z])", " ", key).lower())
        return _("Requires {what}" if value else "Excludes {what}", what=what)
    if key == "direction" and value in ("up", "down"):
        return _("Stat gain") if value == "up" else _("Stat loss")
    text = "/".join(str(v) for v in value) if isinstance(value, list) else str(value)
    # Read like the typed requirement for the same field, so the two are one fact.
    typed = {
        "spellClass": lambda: spell_class_text(text),
        "spellType": lambda: spell_type_text(text),
        "status": lambda: _("Requires {what}", what=worded(text)),
        "source": lambda: _("Requires source: {source}", source=worded(qualitative(text))),
    }
    if key in typed:
        return typed[key]()
    labels = {
        "who": "Creature",
        "what": "Event",
        "race": "Race",
        "class": "Class",
        "spellClass": "Spell class",
        "spellType": "Spell type",
        "source": "Source",
        "status": "Status",
        "by": "Caused by",
        "stat": "Stat",
        "stats": "Stats",
        "direction": "Stat change",
        "condition": "Condition",
    }
    label = labels.get(key, re.sub(r"(?<!^)(?=[A-Z])", " ", key).capitalize())
    # Turn number, cadence and zero amounts identify the event.
    shown = text if key in ("onTurn", "cadence", "amount") else qualitative(text)
    local = named(NAMED_QUALIFIERS[key], shown) if key in NAMED_QUALIFIERS else worded(shown)
    return _("{label}: {value}", label=phrase(label), value=local)


ATTACK_SOURCES = {"attack", "attacks", "attack or spell", "attacks or spells", "attacks and spells"}


def event_requirements(event, action, producer, record, listener, status_kinds, spell_facts):
    """None means a contradiction; requirement tokens describe unproved/configurable requirements."""
    p = listener.get("trigger", {}).get("params", {})
    verb = action["verb"]
    ap = action.get("params", {})
    unresolved = []
    if (
        p.get("manual")
        or listener.get("trigger", {}).get("timing") == "before"
        or p.get("timing") == "prevented"
    ):
        return None
    wanted_direction = p.get("direction")
    direction = action.get("magnitude", {}).get("direction")
    if wanted_direction:
        if direction and wanted_direction != direction:
            return None
        if not direction:
            unresolved.append(("req", "stat_direction", wanted_direction))
    requested = {stat(x) for x in p.get("stats", [])} | (
        {stat(p["stat"])} if p.get("stat") else set()
    )
    produced = {stat(x) for x in action.get("stats", [])}
    if event == "stat_change:target":
        exceptions = action.get("params", {}).get("except", [])
        if isinstance(exceptions, str):
            exceptions = [exceptions]
        if requested and requested <= {stat(x) for x in exceptions}:
            return None
        excluded = stat(p.get("except"))
        if excluded and produced and produced <= {excluded}:
            return None
        if requested and "all" not in produced:
            if produced and not produced & requested:
                if not produced & {"highest_stat", "lowest_stat", "random", "other"}:
                    return None
                unresolved.append(("req", "affected_stat", tuple(sorted(requested))))
            if not produced:
                unresolved.append(("req", "affected_stat", tuple(sorted(requested))))
    wanted_statuses = set(p.get("statuses", [])) | ({p["status"]} if p.get("status") else set())
    # A status named in a damage formula is not its damage source or activation.
    actual_statuses = (
        set(action.get("statuses", []))
        if verb in ("apply_status", "detonate", "remove_status", "status_modifier")
        else set()
    )
    if wanted_statuses and not wanted_statuses & actual_statuses:
        # Ending unnamed statuses can end the wanted one when the target has it.
        if verb not in ("remove_status", "status_modifier") or actual_statuses:
            return None
        kinds = {status_kinds.get(s) for s in wanted_statuses}
        if action.get("statusKind") and action["statusKind"] not in kinds:
            return None
        unresolved.append(("req", "has_status", "/".join(sorted(wanted_statuses))))
    # An attack's damage pairs only with listeners that name attacks as the damage source.
    if verb == "attack" and event.startswith("deal_damage"):
        if normal(p.get("source")) not in ATTACK_SOURCES:
            return None
    if verb in ("dodge_modifier", "crit_chance_modifier") and not (
        str(ap.get("kind", "")).startswith("always") or ap.get("always")
    ):
        unresolved.append(("req", "chance"))
    if event == "effect_activation:actor" and normal(p.get("mechanic")) != normal(
        ap.get("mechanic")
    ):
        return None
    if event == "lose_minion:target":
        wanted = {minion_name(m) for m in p.get("minions", [])}
        # A minion leaving on its own pairs only with listeners that name it.
        if verb == "summon_minion" and explicit_minion(action) not in wanted:
            return None
        if verb != "summon_minion" and wanted:
            unresolved.append(("req", "minion", tuple(p["minions"])))
    # A status's own damage or healing comes later from the status, so it pairs only with
    # listeners that name that status.
    if (
        verb == "apply_status"
        and not event.startswith("apply_status")
        and not (p.get("source") in actual_statuses or wanted_statuses & actual_statuses)
    ):
        return None
    if (
        p.get("statusKind")
        and not any(status_kinds.get(s) == p["statusKind"] for s in actual_statuses)
        and action.get("statusKind") != p["statusKind"]
    ):
        return None
    actor = normal(action.get("actor"))
    if (
        not actor
        and record.get("type") == "spells"
        and producer.get("trigger", {}).get("type") == "activated"
    ):
        actor = "caster"
    by = normal(p.get("by"))
    if by in ("an enemy", "enemy", "enemies"):
        if actor in ("caster", "holder", "allies", "ally", "your_creatures"):
            return None
        if actor not in ("enemy", "enemies", "random_enemy"):
            unresolved.append(("req", "enemy_cause"))
    elif by in ("holder", "allies", "your own creatures", "your creatures"):
        if actor in ("enemy", "enemies", "random_enemy"):
            return None
        # A Perk belongs to the player, so it never acts as the holder.
        if not actor and by == "holder" and record.get("type") == "perks":
            return None
        if not actor:
            unresolved.append(("req", "allied_cause"))
        if by == "holder":
            unresolved.append(("req", "holder_cause"))
    elif by and by not in {normal(s) for s in wanted_statuses}:
        unresolved.append(("req", "caused_by", p["by"]))
    source = normal(p.get("source"))
    # A listener naming the status whose own effect this is needs no other source.
    named_status_effect = verb == "apply_status" and wanted_statuses & actual_statuses
    if source and source not in ("any source",) and not named_status_effect:
        if p.get("source") in status_kinds:
            if verb not in ("detonate", "apply_status") or p["source"] not in actual_statuses:
                return None
        elif source in (
            "attack",
            "attacks",
            "spell",
            "spells",
            "attack or spell",
            "indirect",
            "indirect damage",
            "a debuff",
        ):
            damage_kind = (
                "attack"
                if verb == "attack"
                else "spell"
                if verb == "deal_damage"
                and (
                    record.get("type") == "spells"
                    and producer.get("trigger", {}).get("type") == "activated"
                    or normal(ap.get("countsAs")) == "spell damage"
                )
                else "status"
                if verb in ("detonate", "apply_status")
                else "indirect"
                if verb == "deal_damage"
                else None
            )
            wanted = (
                {"attack", "spell"}
                if source == "attack or spell"
                else {"status"}
                if source == "a debuff"
                else {"indirect", "status"}
                if source.startswith("indirect")
                else {source.rstrip("s")}
            )
            if damage_kind and damage_kind not in wanted:
                return None
            if not damage_kind:
                unresolved.append(("req", "damage_source", p["source"]))
        else:
            unresolved.append(("req", "source", p["source"]))
    if event == "timeline_move:target" and p.get("to"):
        to = ap.get("to")
        moved = normal(ap.get("direction"))
        if to and to != p["to"]:
            return None
        if not to and (
            "up" in moved and p["to"] == "bottom" or "down" in moved and p["to"] == "top"
        ):
            return None
        if not to:
            unresolved.append(("req", "qualifier", "to", p["to"]))
    if event in ("cast:actor", "cast:target"):
        named = spell_facts.get(normal(ap.get("spell")))
        spell_class = ap.get("spellClass") or (named.get("class") if named else None)
        # A cast of an unnamed spell pairs only with listeners every spell satisfies; whether it
        # meets a class or type depends on the Spell Gem.
        if p.get("spellClass"):
            if not spell_class or normal(spell_class) != normal(p["spellClass"]):
                return None
        if p.get("spell") and normal(ap.get("spell")) != normal(p["spell"]):
            return None
        typ = normal(p.get("spellType"))
        if typ:
            known = None
            if named:
                target = named.get("targets")
                if typ == "arsenal":
                    known = named.get("arsenal")
                elif typ == "booze":
                    known = named.get("booze")
                elif typ == "single-target":
                    known = target == "one" if target else None
                elif typ == "multi-target":
                    known = target != "one" if target else None
                elif typ == "damaging":
                    known = "DAMAGE" in named.get("tags", []) if "tags" in named else None
                elif typ == "healing":
                    known = "HEAL" in named.get("tags", []) if "tags" in named else None
            if not named or known is False:
                return None
            if known is None:
                unresolved.append(("req", "spell_type", p["spellType"]))
    # Never silently discard the remaining qualifiers from a claimed direct chain.
    handled = {
        "manual",
        "timing",
        "direction",
        "stat",
        "stats",
        "except",
        "status",
        "statuses",
        "statusKind",
        "source",
        "by",
        "spell",
        "spellClass",
        "spellType",
        "to",
        # Every move an effect makes is forced, and "event" restates the trigger in words.
        "forced",
        "event",
        "mechanic",
        "minions",
    }
    # With a typed mechanic or minion list, "what" only restates it.
    if p.get("mechanic") or p.get("minions"):
        handled.add("what")
    for key, value in p.items():
        if key not in handled and value is not None:
            unresolved.append(("req", "qualifier", key, frozen(value)))
    return list(dict.fromkeys(unresolved))


def native_conflict(a, b):
    x = a.get("meta", {})
    y = b.get("meta", {})
    return bool(
        x.get("specialization")
        and y.get("specialization")
        and x["specialization"] != y["specialization"]
        and x.get("anointment") is False
        and y.get("anointment") is False
    )


def minion_name(value):
    name = normal(value)
    return {"zombie": "zombies"}.get(name, name)


def explicit_minion(action):
    name = minion_name(action.get("params", {}).get("minion"))
    if not name or any(
        s in name for s in ("random", "same minion", "copy of", "one of", "sacrificed", "stolen")
    ):
        return None
    return name


def explicit_minions(action):
    """The minions a modifier names; empty when it affects every minion it does not except."""
    named = [minion_name(m) for m in action.get("params", {}).get("minions", [])]
    return set(filter(None, named + [explicit_minion(action)]))


def excepted_minions(action):
    return {minion_name(m) for m in action.get("params", {}).get("exceptMinions", [])}


def damage_fact(action, rule, record, spells):
    verb = action["verb"]
    requirements = []
    actor = action.get("actor")
    target = action.get("target")
    if verb == "attack":
        channels = {"attack"}
    elif verb == "detonate":
        channels = {"status:" + s for s in action.get("statuses", [])}
    elif verb == "deal_damage":
        channels = {
            "spell"
            if record.get("type") == "spells"
            and rule.get("trigger", {}).get("type") == "activated"
            or normal(action.get("params", {}).get("countsAs")) == "spell damage"
            else "indirect"
        }
    elif verb == "cast":
        spell = spells.get(normal(action.get("params", {}).get("spell")))
        if not spell or "tags" in spell and "DAMAGE" not in spell["tags"]:
            return None
        if "tags" not in spell:
            requirements.append(("req", "damaging_spell"))
        channels = {"spell"}
    else:
        return None
    if action.get("params", {}).get("additional"):
        requirements.append(("req", "base_action"))
    if (
        not actor
        and record.get("type") == "spells"
        and rule.get("trigger", {}).get("type") == "activated"
    ):
        actor = "caster"
    if not actor:
        return None
    return {"channels": channels, "actor": actor, "target": target, "requirements": requirements}


def amplifier_channels(action, status_kinds):
    magnitude = action.get("magnitude", {})
    verb = action["verb"]
    p = action.get("params", {})
    if magnitude.get("direction") != "up":
        return set()
    if verb == "spell_modifier":
        if "potency" not in normal(p.get("what")):
            return set()
        return {"spell"}
    if verb != "damage_modifier" or action.get("flow") not in ("dealt", "taken"):
        return set()
    source = normal(p.get("source"))
    # Without a damage source the modifier raises every damage on its side, so no producer pairs
    # with it more than any other.
    if not source:
        return set()
    if source in ("attack", "attacks"):
        return {"attack"}
    if source in ("spell", "spells"):
        return {"spell"}
    if source in ("attacks and spells", "attack or spell", "attacks or spells"):
        return {"attack", "spell"}
    if source in ("indirect", "indirect damage"):
        return {"indirect", "status:*"}
    if p.get("source") in status_kinds:
        return {"status:" + p["source"]}
    return set()


def channels_overlap(produced, wanted):
    return bool(
        produced & wanted or "status:*" in wanted and any(x.startswith("status:") for x in produced)
    )
