"""Object summaries shared across pages."""

import json
from collections import defaultdict
from .current import records
from .messages import _

# Each of these serves exactly one component: an inscription its Spell Gem, a Godspawn Heart its
# creature, a gemstone its Spell Gem property. They appear only as a step in that component's
# routes.
CHAIN_KINDS = ("inscription", "heart", "enchantment_material")


class Cards:
    def __init__(self, db):
        self.entities = {
            k: {"id": k, "kind": t, "name": n, "description": d, "attrs": json.loads(a)}
            for k, t, n, d, a in db.execute("SELECT id,kind,name,description,attrs FROM entity")
        }
        self.out = defaultdict(list)
        self.incoming = defaultdict(list)
        self.cache = {}
        for src, rel, dst in db.execute("SELECT DISTINCT src,rel,dst FROM edge"):
            self.out[src, rel].append(dst)
            self.incoming[dst, rel].append(src)
        self.classification = {
            k: {"class": c, "race": r}
            for k, c, r in db.execute("SELECT id,class,race FROM component")
        }
        self.by_kind_name = {(e["kind"], e["name"].casefold()): k for k, e in self.entities.items()}
        for key, alias in db.execute("SELECT entity_id,alias FROM entity_alias"):
            self.by_kind_name.setdefault((self.entities[key]["kind"], alias.casefold()), key)
        self.perks = defaultdict(list)
        for e in self.entities.values():
            if e["kind"] == "perk":
                self.perks[e["attrs"].get("specialization")].append(e["id"])
        self.projects = defaultdict(list)
        self.project_outputs = defaultdict(list)
        projects = {record["id"]: record for record in records("projects.json")}
        game_ids = {
            (t, str(g)): k
            for t, g, k in db.execute(
                "SELECT kind,game_id,entity_id FROM game_entity WHERE entity_id IS NOT NULL"
            )
        }
        for item in records("projectItems.json"):
            key = game_ids.get(("heart", str(item["id"])))
            if not key:
                continue
            for pid in item.get("projects", []):
                p = projects.get(pid, {})
                if p.get("name"):
                    self.projects[key].append(p["name"])
                for field, kind in [
                    ("unlockedCreature", "creature"),
                    ("unlockedRealm", "realm"),
                    ("unlockedSpecialization", "specialization"),
                ]:
                    target = game_ids.get((kind, str(p.get(field))))
                    if target:
                        self.project_outputs[key].append(target)
        self.god_titles = {}
        for key, body in db.execute("SELECT entity_id,body FROM game_entity WHERE kind='god'"):
            self.god_titles[key] = json.loads(body).get("title")
        self.spell_users = defaultdict(set)
        self.named_spells = defaultdict(set)
        self.spell_hits = defaultdict(list)
        for key, body in db.execute("SELECT entity_id,body FROM mechanic_record"):
            record = json.loads(body)
            for rule in record.get("rules", []):
                for action in rule.get("actions", []):
                    name = action.get("params", {}).get("spell")
                    target = self.by_kind_name.get(("spell", str(name).casefold()))
                    if action.get("verb") == "cast" and target and target != key:
                        self.spell_users[target].add(key)
                        self.named_spells[key].add(target)
                        hit = {
                            "entity_id": key,
                            "rank": record.get("meta", {}).get("rank"),
                            "reference": record.get("id"),
                        }
                        if hit not in self.spell_hits[target, key]:
                            self.spell_hits[target, key].append(hit)
        self.places = defaultdict(set)
        self.stock = defaultdict(set)
        self.offer_counts = dict(
            db.execute("SELECT shop_id,count(*) FROM shop_offer GROUP BY shop_id")
        )
        self.routes = defaultdict(list)
        columns = [r[1] for r in db.execute("PRAGMA table_info(route)")]
        for row in db.execute("SELECT * FROM route"):
            route = dict(zip(columns, row))
            route["requirements"] = json.loads(route["requirements"])
            place = self.entities.get(route["location"], {})
            route.update(
                location_name=place.get("name"), location_image=place.get("attrs", {}).get("image")
            )
            self.routes[route["entity_id"]].append(route)
        self.chain = {}
        for key, e in self.entities.items():
            targets = {
                "inscription": self.out[key, "unlocks_spell"],
                "heart": self.project_outputs[key],
                "enchantment_material": self.out[key, "adds_property"],
            }.get(e["kind"], [])
            if len(targets) == 1:
                self.chain[key] = targets[0]
        for material, target in self.chain.items():
            moved = self.routes.pop(material, [])
            # A Spell Gem's own routes already say its inscription is bought, then crafted.
            if self.entities[material]["kind"] != "inscription":
                via = self.via(material)
                places = {r["location"] for r in moved}
                # A Godspawn's own shop route records the same Heart purchase and project.
                self.routes[target] = [
                    r
                    for r in self.routes[target]
                    if not (r["location"] in places and r["requirements"].get("project_required"))
                ]
                if self.entities[material]["kind"] == "heart":
                    moved = [
                        {**r, "requirements": {**r["requirements"], "project_required": True}}
                        for r in moved
                    ]
                self.routes[target] += [{**r, "entity_id": target, "via": via} for r in moved]
        for routes in self.routes.values():
            for route in routes:
                if route["requirements"].pop("inscription", None):
                    route["via"] = _("Inscription")
                for field in ("entity_id", "certainty", "row_id", "notes"):
                    route.pop(field, None)
                for field in ("source_text", "item_type"):
                    route["requirements"].pop(field, None)
        for key, routes in list(self.routes.items()):
            for route in routes:
                if route["location"]:
                    self.places[key].add(route["location"])
                    self.stock[route["location"]].add(key)
        from .inline_refs import InlineReferences

        self.inline = InlineReferences(db, self.entities)

    def ids(self, key, rel, incoming=False):
        return (self.incoming if incoming else self.out).get((key, rel), [])

    def objects(self, keys):
        return [
            dict(self.card(k))
            for k in sorted(set(keys), key=lambda k: self.entities.get(k, {}).get("name", ""))
            if k in self.entities
        ]

    def card(self, key):
        if key in self.cache:
            return self.cache[key]
        item = self.entities[key]
        kind = item["kind"]
        attrs = dict(item["attrs"])
        effects = []
        facts = []

        def effect(k, label=None):
            e = self.entities[k]
            text = e["description"] or " / ".join(
                v["label"] for v in e["attrs"].get("variants", [])
            )
            if text:
                segments = self.inline.segments(k, text)
                effects.append(
                    {
                        "id": k,
                        "name": e["attrs"].get("short_name") or e["name"],
                        "description": "".join(p["text"] for p in segments),
                        "segments": segments,
                        "label": label,
                        "rank": int(e["attrs"]["rank"]) if e["attrs"].get("rank") else None,
                    }
                )

        rel = {
            "creature": "innate_trait",
            "material": "grants_trait",
        }.get(kind)
        if rel:
            for k in self.ids(key, rel):
                effect(k)
            if not effects and item["description"]:
                effect(key)
        elif kind == "relic":
            for k in sorted(
                self.ids(key, "rank_effect"),
                key=lambda k: int(self.entities[k]["attrs"].get("rank", 0)),
            ):
                effect(k, _("Rank {n}", n=self.entities[k]["attrs"]["rank"]))
        elif kind == "specialization":
            for k in sorted(
                self.perks[item["name"]],
                key=lambda k: (
                    bool(self.entities[k]["attrs"].get("ascension")),
                    self.entities[k]["name"],
                ),
            ):
                p = self.entities[k]
                effect(
                    k,
                    _("Ascension")
                    if p["attrs"].get("ascension")
                    else _("Rank 1–{n}", n=p["attrs"].get("ranks", 1)),
                )
        elif kind == "card_set":
            tiers = [n.strip() for n in str(attrs.get("tiers", "")).split("/") if n.strip()]
            lines = [line.strip() for line in item["description"].splitlines() if line.strip()]
            if tiers and len(tiers) == len(lines):
                effects.extend(
                    {
                        "id": key,
                        "name": item["name"],
                        "description": line,
                        "label": _("{tier} Cards", tier=tier),
                        "rank": None,
                    }
                    for tier, line in zip(tiers, lines)
                )
            else:
                effect(key)
        elif kind not in ("realm", "god", "shop", "class", "race", "acquisition_source"):
            effect(key)
        if kind == "spell":
            if attrs.get("charges") is not None:
                facts.append(_("{n} Charges", n=attrs["charges"]))
            if attrs.get("manually_castable") is False:
                facts.append(_("Automatic casts only"))
        if kind == "perk":
            if attrs.get("specialization"):
                facts.append(attrs["specialization"])
            facts.append(
                _("Ascension")
                if attrs.get("ascension")
                else _("Rank 1–{n}", n=attrs.get("ranks", 1))
            )
            if attrs.get("anointment"):
                facts.append(_("Anointment"))
        if kind in ("realm", "god", "shop", "acquisition_source"):
            if kind == "god" and self.god_titles.get(key):
                facts.append(self.god_titles[key])
            if kind == "realm":
                facts.extend(self.entities[k]["name"] for k in self.ids(key, "rules_realm", True))
            stock = [
                k
                for k in self.stock[key]
                if kind != "realm" or self.entities[k]["kind"] == "creature"
            ]
            count = self.offer_counts.get(key, len(stock))
            if count:
                if kind == "realm":
                    facts.append(_("{n} Creature", n=count) if count == 1 else _("{n} Creatures", n=count))
                else:
                    facts.append(_("{n} Item", n=count) if count == 1 else _("{n} Items", n=count))
        classification = self.classification.get(key, {})
        for field in ("class", "race"):
            name = classification.get(field) or attrs.get(field)
            ref = self.by_kind_name.get((field, str(name).casefold()))
            if ref:
                attrs.setdefault(field, name)
                attrs[field + "_id"] = ref
                attrs[field + "_icon"] = self.entities[ref]["attrs"].get("image")
        segments = self.inline.segments(key, item["description"])
        card = {
            **item,
            "description": "".join(p["text"] for p in segments),
            "segments": segments,
            "attrs": attrs,
            "effects": effects,
            "facts": list(dict.fromkeys(facts)),
            "routes": self.routes[key],
        }
        if kind == "creature":
            card["classification"] = [classification]
        self.cache[key] = card
        return card

    def via(self, material):
        """How a route names the chain step it goes through."""
        e = self.entities[material]
        return _("Inscription") if e["kind"] == "inscription" else e["name"]

    def sections(self, key):
        e = self.entities[key]
        kind = e["kind"]
        sections = []

        def add(title, keys):
            items = self.objects(k for k in keys if k != key)
            if items:
                sections.append({"title": title, "items": items})
            return items

        if kind == "spell":
            for item in add(_("Cast by"), self.spell_users[key]):
                item["matched_rules"] = self.spell_hits[key, item["id"]]

        def unplaced(owner):
            return self.named_spells[owner] - self.inline.anchored(owner)

        if kind in ("trait", "relic", "perk"):
            add(_("Spells"), unplaced(key))
        if kind in ("creature", "material"):
            traits = self.ids(key, "innate_trait" if kind == "creature" else "grants_trait")
            add(_("Spells"), {spell for trait in traits for spell in unplaced(trait)})
        if kind == "specialization":
            add(_("Spells"), {spell for perk in self.perks[e["name"]] for spell in unplaced(perk)})
        if kind == "race":
            add(_("Card bonuses"), self.ids(key, "card_rewards"))
            add(
                _("Creatures"),
                [
                    k
                    for k, c in self.classification.items()
                    if c.get("race") == e["name"] and self.entities[k]["kind"] == "creature"
                ],
            )
        if kind == "card_set":
            add(_("Race"), self.ids(key, "card_rewards", True))
        if kind == "class":
            for t, title in [("creature", _("Creatures")), ("spell", _("Spell Gems"))]:
                add(
                    title,
                    [
                        k
                        for k, c in self.classification.items()
                        if c.get("class") == e["name"] and self.entities[k]["kind"] == t
                    ],
                )
        return sections
