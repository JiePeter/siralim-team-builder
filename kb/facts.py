"""Typed fact tokens shared by synergy matching, ranking and display.

A token is a tuple (layer, name, *args) of JSON scalars, or tuples of them:
  ev     an event an action produces in battle
  mod    a modifier of another effect's amount
  req    a requirement that must hold for the link to happen
  avail  how the effect becomes available (Specialization, Ascension, Relic rank)
  lim    a limit on how often the effect activates
  subject  display-only text that could not be typed; it never links
"""

from .matching import (
    frozen,
    named,
    qualifier_text,
    qualitative,
    spell_class_text,
    spell_type_text,
    worded,
)
from .messages import _, name as local_name, phrase

GAIN_EVENTS = {
    "stat_change:target",
    "apply_status:target:buff",
    "apply_status:target:debuff",
    "summon_minion:target",
}
STAT_SET = {"setTo", "setEqualTo", "setToPct"}
STAT_AMOUNT = {"amplifies", "addedTo"}


def thawed(value):
    return [thawed(v) for v in value] if isinstance(value, tuple) else value


def event(rule, action, name, who):
    """The event token an action produces, or None when it produces no event in battle."""
    # Grants before the battle starts do not activate on-gain effects; attacks and casts there do.
    phase = (
        "grant"
        if rule.get("trigger", {}).get("event") == "battle_start" and name in GAIN_EVENTS
        else "battle"
    )
    return ("ev", name, who, phase, "yes" if logged(action) or name not in GAIN_EVENTS else "no")


def logged(action):
    """Whether a gain or loss activates on-gain effects; sets, averages, amount modifiers and gains
    the game marks as not activating them do not."""
    p = action.get("params", {})
    if p.get("noOnBuffEffects") or p.get("noOnStatGainEffects") or p.get("noOnMinionEffects"):
        return False
    if action["verb"] != "stat_change":
        return True
    if STAT_AMOUNT & set(p) or STAT_SET & set(p):
        return False
    return bool(action.get("magnitude", {}).get("direction")) or "effect" not in p


def listened(token):
    return token[3] == "battle" and token[4] != "no"


def restricts(token):
    """Whether a fact narrows when a link happens, and so lowers its rank."""
    # An outcome condition branches on this effect's own result.
    return token[0] == "req" and token[1] != "outcome"


MODIFIER_TARGETS = {
    "vsClass": "Against {what}",
    "vsWith": "Against enemies with {what}",
    "appliesTo": "Applies to {what}",
    "who": "Creature: {what}",
}
EQUIPMENT = {
    "spellGems": "Spell Gems:",
    "topSpellGemSlot": "Top Spell Gem slot:",
    "what": "Requires",
    "equals": "to be",
}
# The side a condition's subject is on when it is not the effect's own side.
SIDES = {"target": "target", "enemy": "enemy", "enemies": "enemy"}
COUNT_BOUNDS = ("atLeast", "greaterThan", "exactly", "equals", "all", "atMost", "lessThan", "max")
COMPARISONS = {
    "equals": "is",
    "lowerThan": "lower than",
    "higherThan": "higher than",
    "greaterThan": "greater than",
    "within": "within",
}


def condition(c):
    """The token for a rule condition; thresholds and counts do not change what connects."""
    kind = c.get("type")
    p = c.get("params") or {}
    if kind == "has_status":
        return ("req", "has_status", str(p.get("status") or "/".join(p.get("statuses", []))))
    if kind == "count_comparison" and "Relic rank" in str(p.get("what")):
        return ("avail", "relic_rank_condition", *(str(v) for v in p.values()))
    if kind == "count_comparison" and p.get("what"):
        bound = next((k for k in COUNT_BOUNDS if k in p), None)
        if p.get(bound) in (0, "0") or (bound == "lessThan" and p[bound] == 1):
            mode = "none"
        elif bound in ("atMost", "lessThan", "max"):
            mode = "limited"
        else:
            mode = "all" if bound == "all" else "some"
        return ("req", "count", mode, p["what"])
    if kind == "health_threshold":
        if p.get("at") == "100%":
            return ("req", "full_health")
        side = next((k for k in ("below", "above", "at") if k in p), "at")
        return ("req", "health_threshold", side, p.get("after") or "")
    if kind == "damage_threshold" and ("exceeds" in p or "exceedsPct" in p):
        return ("req", "fatal_damage" if "fatal" in str(p.get("exceeds")) else "damage_threshold")
    if kind == "stat_comparison" and p.get("stat"):
        return ("req", "stat_comparison", p["stat"], p.get("who") or "", p.get("higherThan") or "")
    if kind == "comparison" and p.get("what"):
        op = next((k for k in COMPARISONS if k in p), None)
        of = p.get("of") if p.get("of") != "trigger_subject" else None
        return ("req", "comparison", p["what"], of or "", op or "", str(p[op]) if op else "")
    if kind == "resource_threshold":
        return ("req", "resource", *((k, str(v)) for k, v in p.items()))
    if kind in ("race_is", "class_is"):
        values = p.get("races") or p.get("classes") or [p.get("race") or p.get("class")]
        whose = SIDES.get(c.get("who"), "")
        return ("req", kind[:-3], whose, tuple(str(v) for v in values if v))
    if kind == "team_composition" and p.get("race"):
        if p.get("scope") == "all":
            return ("req", "party_all", p["race"])
        return ("req", "party_has", p["race"])
    if kind == "action_state" and p.get("state"):
        return ("req", "action_state", SIDES.get(c.get("who"), ""), p["state"])
    if kind == "lacks_status" and p.get("status"):
        return ("req", "lacks_status", p["status"])
    if kind == "timeline_position" and p.get("at"):
        return ("req", "timeline_position", p["at"])
    if kind == "equipment":
        return ("req", "equipment", *(EQUIPMENT.get(k, k) + " " + str(v) for k, v in p.items()))
    if kind == "damage_threshold" and p.get("condition"):
        return ("req", "action_state", SIDES.get(c.get("who"), ""), p["condition"])
    if kind == "count_comparison" and p.get("of") and p.get("inParty"):
        return ("req", "party_count", p["of"], p["inParty"])
    # Conditions without a typed reading show their non-numeric values.
    values = tuple(qualitative(str(v)) for v in p.values() if type(v) not in (int, float))
    if kind == "once_per_battle":
        return ("lim", "activation", *values)
    if kind == "outcome":
        return ("req", "outcome", *values)
    return ("req", "condition", kind or "", *values)


TRIGGER_QUALIFIERS = (
    "race",
    "class",
    "spellClass",
    "spellType",
    "source",
    "status",
    "by",
    "who",
    "stat",
    "stats",
    "direction",
    "condition",
    "what",
)


def conditions(rule, record):
    """The facts a rule carries regardless of its partner, in display order."""
    facts = []
    meta = record.get("meta", {})
    if meta.get("specialization"):
        facts.append(
            ("avail", "specialization", meta["specialization"], bool(meta.get("anointment")))
        )
        if meta.get("ascension"):
            facts.append(("avail", "ascension"))
    for c in rule.get("conditions", []):
        token = condition(c)
        if render(token):
            facts.append(token)
    p = rule.get("trigger", {}).get("params", {})
    # A typed mechanic or minion list already says what "what" restates, as a status does "by".
    restated = {"what"} if p.get("mechanic") or p.get("minions") else set()
    if p.get("by") and p.get("by") == p.get("status"):
        restated.add("by")
    for key in TRIGGER_QUALIFIERS:
        if p.get(key) and key not in restated:
            facts.append(("req", "qualifier", key, frozen(p[key])))
    if meta.get("rank"):
        facts.append(("avail", "relic_rank", meta["rank"]))
    return list(dict.fromkeys(facts))


def _count(mode, what):
    template = {"none": "No {what}", "limited": "Limited {what}", "all": "Requires all {what}"}
    return _(template.get(mode, "Requires {what}"), what=phrase(what))


def _comparison(what, of, op, value):
    text = what + (" of " + of if of else "") + (" " + COMPARISONS[op] + " " + value if op else "")
    text = qualitative(text)
    return phrase(text[:1].upper() + text[1:])


def _subject(whose, field, values):
    template = "Requires " + (whose + " " if whose else "") + field + ": {values}"
    return _(template, values=phrase(" or ").join(local_name(field, v) for v in values))


def _health(side, after):
    threshold = _("Health " + side + " threshold")
    if after:
        return _("{threshold} after {after}", threshold=threshold, after=phrase(after))
    return threshold


def _stat_comparison(stat, who, higher):
    subject = _("{what} of {of}", what=phrase(stat), of=phrase(who)) if who else phrase(stat)
    if higher:
        return _("{stat} higher than {higher}", stat=subject, higher=phrase(higher))
    return _("{stat} above threshold", stat=subject)


STATES = {
    "provoking": "While provoking",
    "defending": "While defending",
    "defending or provoking": "While defending or provoking",
    "dead": "While dead",
    "alive": "While alive",
    "off-turn": "Outside its own turn",
    "own turn": "During its own turn",
}


def _state(whose, state):
    if whose:
        return _("{whose} is {state}", whose=phrase(whose.capitalize()), state=phrase(state))
    return _(STATES[state]) if state in STATES else phrase(state[:1].upper() + state[1:])


def _clauses(values):
    return phrase("; ").join(phrase(v) for v in values)


LABELS = {
    ("req", "same_creature"): lambda: _("Same creature"),
    ("req", "target_side"): lambda side: _(
        "Requires the affected target to be an ally"
        if side == "ally"
        else "Requires the affected target to be an enemy"
    ),
    ("req", "selected_holder"): lambda: _("Selected creature must carry the reacting effect"),
    ("req", "named_holder"): lambda holder: _(
        "Trait holder: {holder}", holder=phrase(holder.title())
    ),
    ("req", "other_ally"): lambda: _("Another allied creature"),
    ("req", "adjacent_ally"): lambda: _("Adjacent allied creature"),
    ("req", "applied_by_holder"): lambda: _("Status applied by the Trait holder"),
    ("req", "stat_direction"): lambda d: _(
        "Requires a stat gain" if d == "up" else "Requires a stat loss"
    ),
    ("req", "affected_stat"): lambda stats: _(
        "Requires the affected stat: {stats}",
        stats=phrase(", ").join(phrase(s.title()) for s in stats),
    ),
    ("req", "enemy_cause"): lambda: _("Requires an enemy to cause the event"),
    ("req", "allied_cause"): lambda: _("Requires an allied cause"),
    ("req", "holder_cause"): lambda: _("Event caused by the Trait holder"),
    ("req", "caused_by"): lambda by: _("Event caused by {by}", by=phrase(by)),
    ("req", "damage_source"): lambda source: _(
        "Requires damage from {source}", source=worded(source)
    ),
    ("req", "source"): lambda source: _("Requires source: {source}", source=worded(source)),
    ("req", "spell_class"): spell_class_text,
    ("req", "spell_type"): spell_type_text,
    ("req", "damaging_spell"): lambda: _("Requires a damaging spell"),
    ("req", "base_action"): lambda: _("Extra attack or cast"),
    ("req", "critical"): lambda: _("Requires critical damage"),
    ("req", "modifier_target"): lambda field, value: _(
        MODIFIER_TARGETS.get(field, "Requires {what}"),
        what=worded(qualitative(str(thawed(value)))),
    ),
    ("req", "qualifier"): lambda key, value: qualifier_text(key, thawed(value)),
    ("req", "has_status"): lambda status: _("Requires {what}", what=worded(status)),
    ("req", "lacks_status"): lambda status: _("Requires no {status}", status=worded(status)),
    ("req", "race"): lambda whose, values: _subject(whose, "race", values),
    ("req", "class"): lambda whose, values: _subject(whose, "class", values),
    ("req", "party_all"): lambda race: _(
        "Requires a party of only {race} creatures", race=named("race", race)
    ),
    ("req", "party_has"): lambda race: _("Requires {race} in the party", race=named("race", race)),
    ("req", "party_count"): lambda of, count: _(
        "Requires {count} creatures of a {of}", count=count, of=phrase(of)
    ),
    ("req", "action_state"): _state,
    ("req", "equipment"): lambda *values: phrase(" ".join(values)),
    ("req", "timeline_position"): lambda at: _("At the {at} of the Timeline", at=phrase(at)),
    ("req", "count"): _count,
    ("req", "full_health"): lambda: _("Full Health"),
    ("req", "manual_cast"): lambda: _("Requires a manual cast"),
    ("req", "chance"): lambda: _("Depends on chance"),
    ("req", "minion"): lambda minions: _(
        "Requires {what}", what=phrase(" or ").join(worded(m) for m in minions)
    ),
    ("req", "health_threshold"): _health,
    ("req", "fatal_damage"): lambda: _("Fatal damage"),
    ("req", "damage_threshold"): lambda: _("Damage exceeds threshold"),
    ("req", "stat_comparison"): _stat_comparison,
    ("req", "comparison"): _comparison,
    ("req", "resource"): lambda *pairs: phrase(
        " ".join(k.capitalize() + " " + qualitative(v) for k, v in pairs)
    ),
    ("mod", "scales_with"): lambda per: phrase("For each " + qualitative(per)),
    ("avail", "specialization"): lambda specialization, anointment: _(
        "{specialization} Perk / Anointment" if anointment else "{specialization} Specialization",
        specialization=local_name("specialization", specialization),
    ),
    ("avail", "ascension"): lambda: _("Requires Ascension"),
    ("avail", "relic_rank"): lambda rank: _("Relic Rank {rank}", rank=rank),
    ("avail", "relic_rank_condition"): lambda *values: _clauses(values),
    ("req", "outcome"): lambda *values: _clauses(values),
    ("req", "condition"): lambda kind, *values: _clauses(values),
    ("lim", "activation"): lambda *values: _clauses(values),
    ("subject", "text"): phrase,
}


def render(token):
    text = LABELS[token[:2]](*token[2:])
    return text[:1].upper() + text[1:]
