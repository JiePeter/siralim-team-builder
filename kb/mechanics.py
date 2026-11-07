"""Typed, directed effect connections and short conditional continuations.

Upstream annotations describe individual rules, not proven builds. We join only
compatible events/selectors; conditions remain attached to each step.
"""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from functools import cache, cached_property
from typing import NamedTuple
from .annotations import PHASES, event_key, named_statuses, reacts, trigger_id, trigger_label
from .facts import (
    conditions,
    condition as condition_token,
    event as event_token,
    frozen,
    listened,
    restricts,
)
from .matching import (
    event_requirements,
    native_conflict,
    normal,
    stat,
    explicit_minion,
    explicit_minions,
    excepted_minions,
    damage_fact,
    amplifier_channels,
    channels_overlap,
)

# The events an action produces: its verb with the side of it whose scope is the subject.
EVENTS = {
    "attack": [
        ("attack:actor", "actor"),
        ("attack:target", "target"),
        ("deal_damage:target", "target"),
        ("deal_damage:actor", "actor"),
    ],
    "remove_minion": [("lose_minion:target", "target")],
    "cast": [("cast:actor", "actor"), ("cast:target", "target")],
    "heal": [("heal:target", "target"), ("heal:actor", "actor")],
    "deal_damage": [("deal_damage:target", "target"), ("deal_damage:actor", "actor")],
    "kill": [("kill:target", "target"), ("kill:actor", "actor")],
    "resurrect": [("resurrect:target", "target")],
    "defend": [("defend:actor", "actor")],
    "provoke": [("provoke:actor", "actor")],
    "stat_change": [("stat_change:target", "target")],
    "summon_minion": [("summon_minion:target", "target")],
    "timeline_move": [("timeline_move:target", "target")],
}
ACTIVATION_EVENTS = [
    ("death", "kill:target"),
    ("resurrect", "resurrect:target"),
    ("defend", "defend:actor"),
    ("provoke", "provoke:actor"),
    ("dodge", "dodge:actor"),
    ("stat gain", "stat_change:target"),
    ("on-buff", "apply_status:target:buff"),
    ("on-debuff", "apply_status:target:debuff"),
    ("on-minion", "summon_minion:target"),
    ("on-heal", "heal:target"),
    ("the healing", "heal:target"),
    ("on-attack", "attack:actor"),
    ("attacks", "attack:actor"),
    ("on-cast", "cast:actor"),
    ("spell casts", "cast:actor"),
    ("when-attacked", "attack:target"),
    ("on-critical", "critical_hit:actor"),
    ("critical damage", "critical_hit:actor"),
]
ADDITIONAL_EVENTS = {"attack": "attack:actor", "cast": "cast:actor"}


def activation(action):
    """How an action makes other effects run: ("call", events) runs them now, ("repeat", events)
    runs them additional times. Suppressing, limiting or Spell Gem property effects produce none."""
    p = action.get("params", {})
    what = normal(p.get("what"))
    words = list(dict.fromkeys(e for word, e in ACTIVATION_EVENTS if word in what))
    if p.get("additional"):
        return "repeat", [ADDITIONAL_EVENTS[action["verb"]]] if action[
            "verb"
        ] in ADDITIONAL_EVENTS else words
    if action["verb"] != "activation_modifier" or p.get("property") or "spell gem" in what:
        return None, []
    if p.get("mode") == "activate now" or p.get("effect") == "activate":
        return "call", words
    if not p.get("mode") and not p.get("effect"):
        return "repeat", words
    return None, []


# Statuses that act on their holder each turn or when they run out, and the event that action is.
TICKING = {
    "Bleeding": "deal_damage:target",
    "Blighted": "deal_damage:target",
    "Bomb": "deal_damage:target",
    "Burning": "deal_damage:target",
    "Poisoned": "deal_damage:target",
    "Mending": "heal:target",
    "Leeching": "heal:target",
    "Rebirth": "resurrect:target",
}
# Demons leave battle on their own or when their master sacrifices them.
LEAVING_MINIONS = {
    "brim fiends",
    "chaos satyrs",
    "fire imps",
    "asmodeus",
    "beelzebub",
    "belphegor",
    "leviathan",
    "lucifer",
    "mammon",
    "satanachia",
}


# Removal by an effect and expiry by the status's own end condition are distinct game events.
ENDING_EVENTS = ("remove_status", "expire_status")


def shortens(action):
    """Whether a status modifier makes statuses expire sooner."""
    if action["verb"] != "status_modifier":
        return False
    p = action.get("params", {})
    if p.get("duration") == "1 turn" or p.get("turns") == 1:
        return True
    return "duration" in str(p.get("property")) and (
        action.get("magnitude", {}).get("direction") == "down"
    )


ON_X_EFFECTS = {
    "attack:actor": "on-attack effects",
    "cast:actor": "on-cast effects",
    "defend:actor": "on-defend effects",
    "heal:target": "on-heal effects",
}


def effect_activation(rule):
    """A rule that answers its own holder's attack, cast, defend or heal is that creature's on-X
    effect; its activating is the event "after on-X effects activate" listeners wait for."""
    trigger = rule.get("trigger", {})
    mechanic = ON_X_EFFECTS.get(event_key(trigger))
    if (
        not mechanic
        or trigger.get("timing") == "before"
        or trigger.get("subject") not in ("holder", "caster")
    ):
        return []
    return [
        {"verb": "activate_effect", "actor": "trigger_subject", "params": {"mechanic": mechanic}}
    ]


def raises_chance(action):
    """The event a standing dodge or critical chance makes happen, like a duration change makes
    statuses expire."""
    p = action.get("params", {})
    direction = action.get("magnitude", {}).get("direction")
    if action["verb"] == "dodge_modifier" and direction != "down":
        kind = p.get("kind")
        if (
            kind == "always dodge"
            or not kind
            and (direction or "dodge chance" in str(p.get("effect")))
        ):
            return "dodge:actor"
    if action["verb"] == "crit_chance_modifier" and direction != "down":
        return "critical_hit:actor"
    return None


def selector(scope, rule, action=None, role="target"):
    if role == "target" and scope == "allies" and (action or {}).get("params", {}).get("others"):
        scope = "other_allies"
    if scope == "trigger_subject":
        return selector(rule.get("trigger", {}).get("subject", "any"), {})
    if scope == "target":
        # Attacks and spells can target either side; a trigger alone proves neither.
        return ("unknown", "target")
    if scope == "other" and rule.get("trigger", {}).get("params", {}).get("who"):
        return ("ally", "named:" + normal(rule["trigger"]["params"]["who"]))
    if scope == "relic":
        return ("relic", "relic")
    if scope in ("holder", "caster"):
        return ("ally", scope)
    if scope in (
        "allies",
        "ally",
        "other_allies",
        "adjacent_allies",
        "your_creatures",
        "random_ally",
        "owner",
    ):
        return ("ally", scope)
    if scope in (
        "enemy",
        "enemies",
        "random_enemy",
        "random_enemies",
        "all_enemies",
        "adjacent_enemies",
    ):
        return ("enemy", scope)
    return ("unknown", scope or "any")


def counted(rule):
    """The events a rule counts over the battle, each shaped as the trigger that would see it."""
    found = [
        c
        for action in rule.get("actions", [])
        for c in action.get("magnitude", {}).get("counts", [])
    ] + [
        c
        for cond in rule.get("conditions", [])
        for c in (cond.get("params") or {}).get("counts", [])
    ]
    return [{**c, "timing": "after"} for c in found]


SAME_CREATURE = ("req", "same_creature")


def compatible(left, right):
    if left[0] != "unknown" and right[0] != "unknown" and left[0] != right[0]:
        return None
    if left[1].startswith("named:") and right[1].startswith("named:") and left[1] != right[1]:
        return None
    facts = []
    for unknown, known in ((left, right), (right, left)):
        if unknown[0] != "unknown":
            continue
        if unknown[1] not in ("any", "target", None):
            return None
        if unknown[1] == "target" and known[0] in ("ally", "enemy"):
            facts.append(("req", "target_side", known[0]))
        if known[0] == "relic":
            return None
    if left[1] in ("holder", "caster") and right[1] in ("holder", "caster"):
        facts.append(SAME_CREATURE)
    if selected_holder_requirement(left, right):
        facts.append(("req", "selected_holder"))
    for named, other in ((left, right), (right, left)):
        # Only the named creature's own events or effects take part.
        if named[1].startswith("named:") and not other[1].startswith("named:"):
            facts.append(("req", "named_holder", named[1][6:]))
    if left[1] in ("other_allies", "adjacent_allies") or right[1] in (
        "other_allies",
        "adjacent_allies",
    ):
        facts.append(
            ("req", "other_ally" if "other_allies" in (left[1], right[1]) else "adjacent_ally")
        )
    return facts


def target_side_requirement(left, right):
    for variable, known in ((left, right), (right, left)):
        if variable == ("unknown", "target") and known[0] in ("ally", "enemy"):
            return known[0]
    return None


def selected_holder_requirement(left, right):
    return left[1] in ("ally", "random_ally", "random_any") and right[1] in ("holder", "caster")


def scope_binding(left, right):
    return {
        "requires_target_side": target_side_requirement(left, right),
        "requires_selected_holder": selected_holder_requirement(left, right),
    }


@dataclass(eq=False)
class Rule:
    """A rule with what every link through it repeats. Unpacks as (typed, record, row)."""

    owner: str
    typed: dict
    record: dict
    row: str

    def __iter__(self):
        return iter((self.typed, self.record, self.row))

    @cached_property
    def event(self):
        return event_key(self.typed.get("trigger", {}))

    @cached_property
    def facts(self):
        return conditions(self.typed, self.record)

    @cached_property
    def restricted(self):
        return any(restricts(condition_token(c)) for c in self.typed.get("conditions", []))

    @cached_property
    def identity(self):
        return json.dumps(self.typed, sort_keys=True)

    @cached_property
    def listeners(self):
        """What the rule hears, by event: a rule-shaped listener and the relation it makes."""
        heard = defaultdict(list)
        if not self.record.get("flags", {}).get("manualCastOnly"):
            heard[self.event].append((self.typed, "Event chain"))
        for c in counted(self.typed):
            heard[event_key(c)].append(({"trigger": c}, "Event count"))
        return {
            event: [x for x in found if not x[0].get("trigger", {}).get("params", {}).get("manual")]
            for event, found in heard.items()
        }

    @cached_property
    def brief(self):
        trigger = self.typed.get("trigger", {})
        side, scope = selector(trigger.get("subject"), self.typed)
        return {
            "text": self.record["text"],
            "scope": {
                "side": side,
                "set": "holder" if scope in ("holder", "caster") else "all",
            },
            "typed": self.typed,
            "reference": self.record.get("id"),
            "rank": self.record.get("meta", {}).get("rank"),
            "trigger_label": trigger_label(trigger_id(trigger)),
            "conditions": self.facts,
        }


class Step(NamedTuple):
    """An action a rule performs: its own, or one of the spell it casts."""

    rule: Rule
    action: dict
    source: dict
    source_record: dict
    inherited: bool
    facts: list
    requirements: list
    via: dict
    produces_event: bool


def listed_by_both(link):
    """Overlaps and stacking status modifiers hold both ways, so each side lists them as outgoing."""
    return link["relation"] == "Scope overlap" or (
        link["relation"] == "Status condition" and "modifier" in link["witness"]
    )


def same_link(edge, own):
    """Whether a link from a partner says what the owner's own link to that partner already says."""
    return (
        edge["relation"] == own["relation"]
        and edge["event_label"] == own["event_label"]
        and edge["witness"] == own["witness"]
        and edge["target_rule"]["reference"] == own["source_rule"]["reference"]
        and edge["source_rule"]["reference"] == own["target_rule"]["reference"]
        and edge["target_rule"]["typed"] == own["source_rule"]["typed"]
        and edge["source_rule"]["typed"] == own["target_rule"]["typed"]
    )


class Engine:
    def __init__(self, db):
        self.nodes = {}
        self.cache = {}
        self.connection_cache = {}
        self.byname = {}
        self.statusKinds = dict(db.execute("SELECT name,kind FROM mechanic_status"))
        for key, name, kind, body, row in db.execute(
            "SELECT m.entity_id,e.name,e.kind,m.body,m.row_id FROM mechanic_record m JOIN entity e ON e.id=m.entity_id WHERE COALESCE(json_extract(e.attrs,'$.obtainable'),1)<>0"
        ):
            record = json.loads(body)
            node = self.nodes.setdefault(
                key, {"id": key, "name": name, "kind": kind, "rules": [], "text": record["text"]}
            )
            for rule in record["rules"]:
                node["rules"].append(Rule(key, rule, record, row))
            self.byname[(kind, name.casefold())] = key
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='entity_alias'").fetchone():
            for key, alias in db.execute("SELECT entity_id,alias FROM entity_alias"):
                if key in self.nodes:
                    self.byname.setdefault((self.nodes[key]["kind"], alias.casefold()), key)
        self.triggers = defaultdict(set)
        self.counters = defaultdict(set)
        self.statuses = defaultdict(set)
        for key, node in self.nodes.items():
            for rule, record, row in node["rules"]:
                self.triggers[event_key(rule.get("trigger", {}))].add(key)
                trigger = rule.get("trigger", {})
                if trigger.get("event") in ENDING_EVENTS:
                    for status in named_statuses(trigger.get("params", {})):
                        self.statuses[status].add(key)
                for c in counted(rule):
                    self.counters[event_key(c)].add(key)
                for condition in rule.get("conditions", []):
                    p = condition.get("params", {})
                    for status in [p.get("status")] + p.get("statuses", []):
                        if status and condition.get("type") == "has_status":
                            self.statuses[status].add(key)
                inherited = [
                    step[0] for x in rule.get("actions", []) for step in self.payload(x, rule)
                ]
                for a in rule.get("actions", []) + inherited:
                    if a["verb"] in ("status_modifier", "detonate"):
                        for status in a.get("statuses", []):
                            self.statuses[status].add(key)
        self.spell_facts = {
            normal(n["name"]): r.get("meta", {})
            for n in self.nodes.values()
            if n["kind"] == "spell"
            for _, r, _ in n["rules"]
        }
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='game_entity'").fetchone():
            for (body,) in db.execute("SELECT body FROM game_entity WHERE kind='spell'"):
                data = json.loads(body)
                self.spell_facts[normal(data["name"])] = data
        self.minion_modifiers = defaultdict(set)
        for key, node in self.nodes.items():
            for rule, record, _ in node["rules"]:
                inherited = [
                    step[0] for x in rule.get("actions", []) for step in self.payload(x, rule)
                ]
                for action in rule.get("actions", []) + inherited:
                    if action["verb"] == "minion_modifier":
                        names = explicit_minions(action)
                        for name in names:
                            self.minion_modifiers[name].add(key)
                        if not names:
                            self.minion_modifiers["*"].add(key)
        self.amplifiers = defaultdict(set)
        for key, node in self.nodes.items():
            for rule, record, _ in node["rules"]:
                for action in rule.get("actions", []):
                    for channel in amplifier_channels(action, self.statusKinds):
                        self.amplifiers[channel].add(key)

    def action_events(self, action):
        # A copied buff or debuff is gained like an applied one.
        if action["verb"] in ("apply_status", "copy"):
            kinds = {self.statusKinds.get(s) for s in action.get("statuses", [])} | {
                action.get("statusKind")
            }
            gained = [
                ("apply_status:target:" + k, "target") for k in ("debuff", "buff") if k in kinds
            ]
            ticks = {TICKING[s] for s in action.get("statuses", []) if s in TICKING}
            if action["verb"] == "copy" or not ticks:
                return gained
            return gained + [("status_effect:target", "target")] + [(e, "target") for e in ticks]
        ending = (
            "remove_status"
            if action["verb"] == "remove_status"
            else "expire_status"
            if shortens(action)
            else None
        )
        if ending:
            kinds = {self.statusKinds.get(s) for s in action.get("statuses", [])} | {
                action.get("statusKind")
            }
            # Without a named status or kind, the effect may end either kind.
            if not kinds - {None}:
                kinds = {"buff", "debuff"}
            return [(ending + ":target", "target")] + [
                (ending + ":target:" + k, "target") for k in ("debuff", "buff") if k in kinds
            ]
        if action["verb"] == "detonate":
            return [("status_effect:target", "target"), ("deal_damage:target", "target")]
        # Current Health is not a stat; changing only it is neither a stat change nor healing.
        if action["verb"] == "stat_change" and {stat(s) for s in action.get("stats", [])} == {
            "current health"
        }:
            return []
        raised = raises_chance(action)
        if raised:
            return [(raised, "target")]
        events = list(EVENTS.get(action["verb"], []))
        p = action.get("params", {})
        if action["verb"] == "deal_damage" and p.get("alwaysCritical"):
            events.append(("critical_hit:actor", "actor"))
        # Effects of a named mechanic (Celerity, Retribution) are activations its listeners wait for.
        if p.get("mechanic"):
            events.append(("effect_activation:actor", "actor" if action.get("actor") else "target"))
        if action["verb"] == "summon_minion" and explicit_minion(action) in LEAVING_MINIONS:
            events.append(("lose_minion:target", "target"))
        return events

    def payload(self, action, rule):
        """The on-use actions of the named spell an action casts, as the casting rule performs them:
        the spell's caster becomes the cast's actor and its target the cast's target."""
        p = action.get("params", {})
        if action["verb"] != "cast" or p.get("additional"):
            return []
        key = self.byname.get(("spell", str(p.get("spell", "")).casefold()))
        caster = action.get("actor")
        if not key or not caster or selector(caster, rule, action, "actor")[0] == "enemy":
            return []
        record = {**self.nodes[key]["rules"][0].record, "name": self.nodes[key]["name"]}
        steps = []
        for spell_rule, _, _ in self.nodes[key]["rules"]:
            if spell_rule.get("trigger", {}).get("type") != "activated":
                continue
            for spell_action in spell_rule.get("actions", []):
                moved = dict(spell_action)
                for role in ("actor", "target"):
                    scope = spell_action.get(role)
                    if scope == "caster" or role == "actor" and not scope:
                        moved[role] = caster
                    elif scope == "target" and action.get("target"):
                        moved[role] = action["target"]
                # Which side a spell's target acts for is unknown when the cast names no target.
                if moved.get("actor") == "target":
                    continue
                steps.append((moved, spell_rule, record))
        return steps

    @cache
    def steps(self, rule):
        a, ar = rule.typed, rule.record
        actions = a.get("actions", [])
        performed = [(action, a, ar) for action in actions + effect_activation(a)] + [
            step for action in actions for step in self.payload(action, a)
        ]
        found = []
        for action, sa, sar in performed:
            inherited = sa is not a
            # Facts of both rules when the action comes from a spell this rule casts.
            cast_facts = conditions(sa, sar) if inherited else []
            found.append(
                Step(
                    rule,
                    action,
                    sa,
                    sar,
                    inherited,
                    rule.facts + cast_facts,
                    # The spell's own conditions narrow the link like the listener's do.
                    [t for t in cast_facts if restricts(t)],
                    {"via": sar["name"]} if inherited else {},
                    # A standing duration change makes statuses expire while it holds.
                    bool(shortens(action) or raises_chance(action))
                    or event_key(a.get("trigger", {})) not in ("passive", "non_combat"),
                )
            )
        return found

    def plans(self, step):
        """What a step can link to: the matcher, its argument, the owners it can reach, and whether
        the link is directed, so that those owners can only learn of it as incoming."""
        a, action = step.rule.typed, step.action
        verb, params = action["verb"], action.get("params", {})
        # An action-count modifier does not generate an action by itself.
        produces = step.produces_event and not params.get("additional")
        if produces:
            events = [
                event_token(step.source, action, event, who)
                for event, who in self.action_events(action)
            ]
            for _, event, who, *_ in filter(listened, events):
                subject = action.get(who)
                if not subject and verb in ("defend", "provoke"):
                    subject = action.get("target")
                if (
                    not subject
                    and who == "actor"
                    and step.rule.record.get("type") == "spells"
                    and a.get("trigger", {}).get("type") == "activated"
                ):
                    subject = "caster"
                if subject:
                    role = who if action.get(who) else "target"
                    yield (
                        self.event_links,
                        (event, subject, selector(subject, a, action, role)),
                        self.triggers[event] | self.counters[event],
                        True,
                    )
        mode, activated = activation(action)
        for event in activated:
            yield self.activation_links, (mode, event), self.triggers[event], True
        # Explicit named casts can continue into that spell's on-use payload.
        if verb == "cast" and not step.inherited and produces:
            spell = params.get("spell", "")
            target = self.byname.get(("spell", spell.casefold()))
            if target:
                yield self.named_spell_links, spell, {target}, False
        if verb == "apply_status":
            for status in action.get("statuses", []):
                yield self.status_links, status, self.statuses[status], True
        # Effects that strengthen the same status on the same side stack on each other.
        if verb == "status_modifier" and action.get("magnitude", {}).get("direction") == "up":
            for status in action.get("statuses", []):
                yield self.stacking_links, status, self.statuses[status], False
        if verb == "summon_minion":
            minion = explicit_minion(action)
            owners = self.minion_modifiers["*"] | self.minion_modifiers.get(minion, set())
            yield self.minion_links, minion, owners, True
        # A cast already amplifies as spell damage, so the damage it inherits does not.
        skip = step.inherited and verb == "deal_damage"
        fact = (
            None if skip else damage_fact(action, step.source, step.source_record, self.spell_facts)
        )
        if fact:
            owners = set()
            for channel in fact["channels"]:
                owners.update(self.amplifiers[channel])
                if channel.startswith("status:"):
                    owners.update(self.amplifiers["status:*"])
            yield self.amplification_links, fact, owners, True

    def event_links(self, step, occurrence, b):
        event, subject, produced = occurrence
        for listener, relation in b.listeners.get(event, ()):
            trigger = listener["trigger"]
            required = selector(trigger.get("subject"), listener)
            sides = compatible(produced, required)
            if sides is None:
                continue
            requirements = event_requirements(
                event,
                step.action,
                step.source,
                step.source_record,
                listener,
                self.statusKinds,
                self.spell_facts,
            )
            if requirements is None:
                continue
            yield (
                relation,
                trigger_label(trigger_id(trigger)),
                sides + step.facts + b.facts,
                {
                    "producer_id": step.rule.owner,
                    "consumer_id": b.owner,
                    "event": event,
                    "action": step.action,
                    "event_subject": subject,
                    **scope_binding(produced, required),
                    "requirements": requirements + step.requirements,
                    **step.via,
                },
            )

    def activation_links(self, step, occurrence, b):
        mode, event = occurrence
        if b.event != event:
            return
        a, action = step.rule.typed, step.action
        trigger = b.typed["trigger"]
        left = selector(
            action.get("actor", action.get("target")),
            a,
            action,
            "actor" if action.get("actor") else "target",
        )
        right = selector(trigger.get("subject"), b.typed)
        sides = compatible(left, right)
        # Calling a creature's effects runs only the listeners that creature
        # holds; no other creature sees the event.
        if mode == "call" and sides is not None:
            if left[0] != "ally" or right[1] not in ("holder", "caster"):
                return
            if action.get("target") == "trigger_subject" and SAME_CREATURE not in sides:
                sides = sides + [("req", "selected_holder")]
        # A repeated stat gain is itself a gain.
        repeated = (
            {**action, "magnitude": {"direction": "up"}}
            if event == "stat_change:target"
            else action
        )
        unrestricted = {
            **b.typed,
            "trigger": {
                **trigger,
                "params": {k: v for k, v in trigger.get("params", {}).items() if k != "manual"},
            },
        }
        requirements = event_requirements(
            event,
            repeated,
            step.source,
            step.source_record,
            unrestricted,
            self.statusKinds,
            self.spell_facts,
        )
        # Whether a repeated manual cast is itself manual is unknown.
        if requirements is not None and trigger.get("params", {}).get("manual"):
            if mode == "call":
                return
            requirements = requirements + [("req", "manual_cast")]
        if sides is not None and requirements is not None:
            yield (
                "Action modifier",
                trigger_label(trigger_id(trigger)),
                sides + step.facts + b.facts,
                {
                    "action": action,
                    "requirements": requirements + step.requirements,
                    **scope_binding(left, right),
                    **step.via,
                },
            )

    def named_spell_links(self, step, spell, b):
        if b.typed.get("trigger", {}).get("type") == "activated":
            yield (
                "Named spell",
                "Cast " + spell,
                step.rule.facts + b.facts,
                {"action": step.action, "spell": spell},
            )

    def status_links(self, step, status, b):
        a, action, rule = step.rule.typed, step.action, b.typed
        trigger = rule.get("trigger", {})
        matching = [
            c
            for c in rule.get("conditions", [])
            if c.get("type") == "has_status"
            and status
            in [c.get("params", {}).get("status")] + c.get("params", {}).get("statuses", [])
        ]
        matching += [
            c
            for c in rule.get("actions", [])
            if c["verb"] in ("status_modifier", "detonate") and status in c.get("statuses", [])
        ]
        if trigger.get("event") in ENDING_EVENTS and status in named_statuses(
            trigger.get("params", {})
        ):
            matching.append({"who": trigger.get("subject")})
        for c in matching:
            scope = c.get("who", c.get("target", trigger.get("subject")))
            left, right = selector(action.get("target"), a, action), selector(scope, rule)
            sides = compatible(left, right)
            if sides is None:
                continue
            requirements = []
            if normal(c.get("params", {}).get("appliedBy")) in ("holder", "the holder"):
                actor = action.get("actor") or (
                    "caster" if step.source_record.get("type") == "spells" else None
                )
                if actor:
                    owner = compatible(selector(actor, a), selector("holder", rule))
                    if owner is None:
                        continue
                    sides += owner
                    if SAME_CREATURE not in owner:
                        requirements.append(("req", "applied_by_holder"))
                else:
                    requirements.append(("req", "applied_by_holder"))
            yield (
                "Status condition",
                status,
                sides + step.facts + b.facts,
                {
                    "requirements": requirements + step.requirements,
                    "status": status,
                    "action": action,
                    **step.via,
                    **scope_binding(left, right),
                },
            )

    def stacking_links(self, step, status, b):
        a, action = step.rule.typed, step.action
        for other in b.typed.get("actions", []):
            if (
                other["verb"] != "status_modifier"
                or status not in other.get("statuses", [])
                or other.get("magnitude", {}).get("direction") != "up"
            ):
                continue
            left = selector(action.get("target"), a, action)
            right = selector(other.get("target"), b.typed, other)
            sides = compatible(left, right)
            if sides is None:
                continue
            yield (
                "Status condition",
                status,
                sides + step.facts + b.facts,
                {
                    **step.via,
                    "requirements": step.requirements,
                    "status": status,
                    "action": action,
                    "modifier": other,
                    **scope_binding(left, right),
                },
            )

    def minion_links(self, step, minion, b):
        a, action = step.rule.typed, step.action
        for modifier in b.typed.get("actions", []):
            if modifier["verb"] != "minion_modifier":
                continue
            wanted = explicit_minions(modifier)
            if wanted and minion not in wanted or minion in excepted_minions(modifier):
                continue
            owner = (
                b.typed.get("trigger", {}).get("subject")
                if modifier.get("target") == "minions"
                else modifier.get("target")
            )
            left, right = selector(action.get("target"), a, action), selector(owner, b.typed)
            sides = compatible(left, right)
            if sides is None:
                continue
            yield (
                "Minion support",
                action.get("params", {}).get("minion", "Minions"),
                sides + step.facts + b.facts,
                {
                    **step.via,
                    "requirements": step.requirements,
                    "minion": minion,
                    "action": action,
                    "modifier": modifier,
                    **scope_binding(left, right),
                },
            )

    def amplification_links(self, step, fact, b):
        a, action = step.rule.typed, step.action
        for modifier in b.typed.get("actions", []):
            channels = amplifier_channels(modifier, self.statusKinds)
            if not channels_overlap(fact["channels"], channels):
                continue
            taken = modifier.get("flow") == "taken"
            left = selector(
                fact["target"] if taken else fact["actor"],
                a,
                action,
                "target" if taken else "actor",
            )
            right = selector(modifier.get("target"), b.typed, modifier)
            if right[0] != ("enemy" if taken else "ally"):
                continue
            sides = compatible(left, right)
            if sides is None:
                continue
            requirements = list(fact["requirements"])
            mp = modifier.get("params", {})
            for field in ("vsClass", "vsWith", "appliesTo", "which", "who", "criticalOnly"):
                if mp.get(field):
                    requirements.append(
                        ("req", "modifier_target", field, frozen(mp[field]))
                        if mp[field] is not True
                        else ("req", "critical")
                    )
            if mp.get("spellClass"):
                test = {"trigger": {"params": {"spellClass": mp["spellClass"]}}}
                extra = event_requirements(
                    "cast:actor",
                    action,
                    step.source,
                    step.source_record,
                    test,
                    self.statusKinds,
                    self.spell_facts,
                )
                if extra is None:
                    continue
                requirements += extra
            if modifier.get("magnitude", {}).get("per"):
                requirements.append(("mod", "scales_with", modifier["magnitude"]["per"]))
            yield (
                "Amplification",
                "Damage",
                sides + step.facts + b.facts,
                {
                    "action": action,
                    "modifier": modifier,
                    "requirements": requirements + step.requirements,
                    **scope_binding(left, right),
                    **step.via,
                },
            )

    def overlap_links(self, rule, event, b):
        """Shared-event overlap and additional actions, offered as suggestions."""
        if b.event != event:
            return
        a, other = rule.typed["trigger"], b.typed["trigger"]
        ap, bp = a.get("params", {}), other.get("params", {})
        # One event fires both its On and After effects, but not an effect that
        # replaces it before it happens.
        before = {t["timing"] == "before" for t in (a, other)}
        if len(before) > 1 or ap.get("timing") != bp.get("timing"):
            return
        # A battle or turn phase and the moment after its effects are not one event.
        if a["event"] in PHASES and trigger_id(a) != trigger_id(other):
            return
        if ap.get("direction") and bp.get("direction") and ap["direction"] != bp["direction"]:
            return
        if ap.get("status") and bp.get("status") and ap["status"] != bp["status"]:
            return
        if (
            ap.get("spellClass")
            and bp.get("spellClass")
            and normal(ap["spellClass"]) != normal(bp["spellClass"])
        ):
            return
        sides = compatible(
            selector(a.get("subject"), rule.typed), selector(other.get("subject"), b.typed)
        )
        if sides is not None:
            yield "Scope overlap", trigger_label(trigger_id(other)), sides + rule.facts + b.facts

    def rules_of(self, owners, key):
        for target in owners:
            if target != key:
                yield from self.nodes[target]["rules"]

    def candidates(self, key):
        if key in self.cache:
            return self.cache[key]
        if key not in self.nodes:
            return []
        result = []
        seen = {}
        for rule in self.nodes[key]["rules"]:
            for step in self.steps(rule):
                for match, argument, owners, _ in self.plans(step):
                    for b in self.rules_of(owners, key):
                        for link in match(step, argument, b):
                            self.add(result, seen, rule, b, *link)
            if reacts(rule.typed.get("trigger", {})):
                for b in self.rules_of(self.triggers[rule.event], key):
                    for link in self.overlap_links(rule, rule.event, b):
                        self.add(result, seen, rule, b, *link)
        result.sort(
            key=lambda r: (
                0
                if r["relation"] == "Event chain"
                else 1
                if r["relation"] == "Status condition"
                else 2,
                len(r["constraints"]),
                r["name"],
            )
        )
        self.cache[key] = result
        return result

    def add(self, result, seen, a, b, relation, event, facts, witness=None):
        witness = witness or {}
        if native_conflict(a.record, b.record):
            return
        target = self.nodes[b.owner]
        if self.nodes[a.owner]["kind"] == target["kind"] == "relic" and SAME_CREATURE in facts:
            return
        identity = (
            b.owner,
            relation,
            event,
            a.record.get("id"),
            b.record.get("id"),
            a.identity,
            b.identity,
        )
        witnesses = seen.setdefault(identity, [])
        if witness in witnesses:
            return
        witnesses.append(witness)
        own_conditions = set(a.facts + b.facts)
        result.append(
            {
                "id": b.owner,
                "name": target["name"],
                "kind": target["kind"],
                "relation": relation,
                "event_label": event,
                "constraints": list(dict.fromkeys(facts)) or [("subject", "text", event)],
                "status": "candidate",
                "rule_version": "structured-v16-local-v1",
                "shared_constraints": list(
                    dict.fromkeys(f for f in facts if f not in own_conditions)
                ),
                "strength": "context"
                if relation == "Scope overlap"
                else "reference"
                if relation == "Named spell"
                else "conditional"
                if any(restricts(t) for t in witness.get("requirements", []))
                or witness.get("requires_target_side")
                or witness.get("requires_selected_holder")
                or any(t[:2] == ("req", "named_holder") for t in facts)
                or a.restricted
                or b.restricted
                else "supported",
                "witness": witness,
                "source_rule": a.brief,
                "target_rule": b.brief,
                "source_row": a.row,
                "target_row": b.row,
            }
        )

    def replacements(self):
        """Effects that stop an event from happening ("would … instead"), with the listeners of that
        event they can silence. A link cannot show this, since it depends on both being in a build."""
        found = []
        for key, node in self.nodes.items():
            for rule, record, _ in node["rules"]:
                if not rule.get("modifiesDefault"):
                    continue
                trigger = rule["trigger"]
                event = event_key(rule.get("replaces") or trigger)
                replaced = selector(trigger.get("subject"), rule)
                direction = trigger.get("params", {}).get("direction")
                listeners = []
                for target in self.triggers[event] | self.counters[event]:
                    if target == key:
                        continue
                    for b, _, _ in self.nodes[target]["rules"]:
                        heard = [b["trigger"]] * (
                            event_key(b.get("trigger", {})) == event
                            and b["trigger"].get("timing") != "before"
                        ) + [c for c in counted(b) if event_key(c) == event]
                        for t in heard:
                            wanted = t.get("params", {}).get("direction")
                            if direction and wanted and direction != wanted:
                                continue
                            if compatible(selector(t.get("subject"), b), replaced) is None:
                                continue
                            listeners.append((target, t.get("subject") in ("holder", "caster")))
                if not listeners:
                    continue
                found.append(
                    {
                        "owner": key,
                        "rank": record.get("meta", {}).get("rank"),
                        "event": event,
                        "set": "holder"
                        if trigger.get("subject") in ("holder", "caster")
                        else "group",
                        "certain": not rule.get("chance") and not rule.get("conditions"),
                        "listeners": sorted(set(listeners)),
                    }
                )
        return found

    @cached_property
    def reach(self):
        """The owners each owner's links can go to."""
        found = {}
        for key, node in self.nodes.items():
            owners = set()
            for rule in node["rules"]:
                for step in self.steps(rule):
                    for _, _, targets, _ in self.plans(step):
                        owners |= targets
                if reacts(rule.typed.get("trigger", {})):
                    owners |= self.triggers[rule.event]
            found[key] = owners - {key}
        return found

    @cached_property
    def sources(self):
        """The owners with a directed link to each owner."""
        found = defaultdict(set)
        for key, node in self.nodes.items():
            reach = set()
            for rule in node["rules"]:
                for step in self.steps(rule):
                    for _, _, owners, directed in self.plans(step):
                        if directed:
                            reach |= owners
            for target in reach:
                found[target].add(key)
        return found

    @cached_property
    def content(self):
        """A hash of what links read of each owner: its own name, kind and records."""
        found = {}
        for key, node in self.nodes.items():
            records = {id(rule.record): rule.record for rule in node["rules"]}
            data = json.dumps(
                [node["name"], node["kind"], list(records.values())], sort_keys=True
            ).encode()
            found[key] = hashlib.sha256(data).hexdigest()
        return found

    @cache
    def performed(self, key):
        """An owner's content with that of the spells it casts, whose actions it performs."""
        spells = {
            self.byname.get(("spell", str(action.get("params", {}).get("spell")).casefold()))
            for rule in self.nodes[key]["rules"]
            for action in rule.typed.get("actions", [])
            if action["verb"] == "cast"
        }
        return self.content[key] + "".join(self.content[s] for s in sorted(spells - {None}))

    def fingerprint(self, key):
        """Changes whenever an owner's connections could, for the same code and shared tables."""
        if key not in self.nodes:
            return ""
        parts = [key, self.performed(key)]
        parts += [t + self.content[t] for t in sorted(self.reach[key])]
        parts += [s + self.performed(s) for s in sorted(self.sources[key] - {key})]
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()

    @cache
    def links_by_target(self, key):
        found = defaultdict(list)
        for item in self.candidates(key):
            found[item["id"]].append(item)
        return found

    def connections(self, key):
        if key not in self.nodes:
            return {"total": 0, "items": [], "categories": {}, "scope": ""}
        if key in self.connection_cache:
            return self.connection_cache[key]
        items = [{**item, "direction": "outgoing"} for item in self.candidates(key)]
        own = self.links_by_target(key)
        for source in sorted(self.sources[key] - {key}):
            for edge in self.links_by_target(source).get(key, ()):
                if listed_by_both(edge) or any(
                    same_link(edge, link) for link in own.get(source, ())
                ):
                    continue
                items.append(
                    {
                        **edge,
                        "id": source,
                        "name": self.nodes[source]["name"],
                        "kind": self.nodes[source]["kind"],
                        "source_rule": edge["target_rule"],
                        "target_rule": edge["source_rule"],
                        "source_row": edge["target_row"],
                        "target_row": edge["source_row"],
                        "direction": "incoming",
                    }
                )
        # Fixed calls stay available to internal traversal; their effect text references them.
        items = [item for item in items if item["relation"] != "Named spell"]
        order = {
            "Event chain": 0,
            "Action modifier": 1,
            "Event count": 1,
            "Amplification": 2,
            "Status condition": 3,
            "Minion support": 3,
            "Scope overlap": 5,
        }
        items.sort(
            key=lambda r: (
                {"supported": 0, "conditional": 1, "reference": 2, "context": 3}.get(
                    r["strength"], 3
                ),
                order.get(r["relation"], 4),
                len(r["witness"].get("requirements", [])),
                len(r["constraints"]),
                r["name"],
            )
        )
        categories = {}
        for i in items:
            categories[i["relation"]] = categories.get(i["relation"], 0) + 1
        result = {"total": len(items), "items": items, "categories": categories, "scope": ""}
        self.connection_cache[key] = result
        return result
