"""Object reference pages, independent of search grouping and build eligibility."""

import json
from collections import defaultdict


class PageTables:
    """The rows object pages read beyond the cards; an export builds thousands of pages from them."""

    def __init__(self, db):
        self.components = {
            r[0]: {"class": r[1], "race": r[2], "availability_basis": r[3]}
            for r in db.execute("SELECT id,class,race,availability_basis FROM component")
        }
        self.offers = defaultdict(list)
        for shop, *offer in db.execute(
            "SELECT shop_id,id,item_id,cost,requirements FROM shop_offer"
        ):
            self.offers[shop].append(offer)
        self.options = defaultdict(list)
        for trait, *option in db.execute(
            """SELECT DISTINCT g.dst,n.id,n.kind,n.name,n.attrs FROM edge g JOIN entity n ON n.id=g.src
            JOIN component c ON c.id=n.id WHERE g.rel IN ('innate_trait','grants_trait') ORDER BY n.kind,n.name"""
        ):
            self.options[trait].append(option)
        self.family = defaultdict(list)
        for race, key, kind, name, attrs, cls in db.execute(
            "SELECT c.race,e.id,e.kind,e.name,e.attrs,c.class FROM entity e JOIN component c ON c.id=e.id WHERE c.kind='creature' ORDER BY e.name"
        ):
            self.family[race].append(
                {
                    "id": key,
                    "kind": kind,
                    "name": name,
                    "image": json.loads(attrs or "{}").get("image"),
                    "classification": [{"class": cls}],
                }
            )
        self.god_relics = {}
        for key, body in db.execute("SELECT entity_id,body FROM game_entity WHERE kind='god'"):
            # The export's relicName and icon group use a different index
            # order. The deity's full relic title is independently stable.
            title = "%, " + json.loads(body).get("relicTitle", "")
            self.god_relics[key] = [
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT e.id FROM entity e LEFT JOIN entity_alias a ON a.entity_id=e.id"
                    " WHERE e.kind='relic' AND (e.name LIKE ? OR a.alias LIKE ?)",
                    (title, title),
                )
            ]
        self.perks = defaultdict(list)
        for specialization, key in db.execute(
            "SELECT json_extract(c.body,'$.specialization'),e.id FROM configuration c JOIN entity e ON e.id=c.id WHERE c.kind='perk' ORDER BY json_extract(c.body,'$.ascension'),json_extract(c.body,'$.short_name')"
        ):
            self.perks[specialization].append(key)
        self.specializations = {}
        for name, key in db.execute(
            "SELECT name,id FROM configuration WHERE kind='specialization'"
        ):
            self.specializations.setdefault(name, key)


def page(kb, key):
    focus = kb.detail(key)
    if not focus:
        return None
    cards = kb.cards()
    tables = kb.page_tables()
    core = cards.card(key)
    focus.update(
        description=core["description"],
        segments=core["segments"],
        attrs=core["attrs"],
        effects=core["effects"],
        facts=core["facts"],
        sections=cards.sections(key),
    )
    focus["routes"] = cards.routes[key]
    focus.update(
        offers=[],
        options=[],
        products=[],
        related=[],
        family=[],
        traits=[],
        materials=[],
        creatures=[],
        perks=[],
    )

    def summary(target):
        return {**cards.entities[target], **cards.card(target)}

    def objects(keys):
        found = {k for k in keys if k in cards.entities}
        return [summary(k) for k in sorted(found, key=lambda k: (cards.entities[k]["name"], k))]

    def linked(rel, source=key):
        return objects(cards.out[source, rel])

    def shop_offers(shop):
        offers = []
        for offer_id, item, cost, requirements in tables.offers[shop]:
            offer = {
                "id": offer_id,
                "cost": json.loads(cost),
                "requirements": json.loads(requirements),
            }
            target = cards.chain.get(item)
            if target:
                offer["via"] = cards.via(item)
                item = target
                offer["requirements"].pop("inscription", None)
            offer["item"] = {k: v for k, v in objects([item])[0].items() if k != "routes"}
            offers.append(offer)
        return offers

    kind = focus["kind"]
    if kind == "trait":
        focus["options"] = [
            {"id": r[0], "kind": r[1], "name": r[2], "image": json.loads(r[3]).get("image")}
            for r in tables.options[key]
        ]
    if kind in ("creature", "material"):
        focus["traits"] = linked("innate_trait" if kind == "creature" else "grants_trait")
        trait_ids = [t["id"] for t in focus["traits"]]
        for trait in trait_ids:
            carriers = objects(
                cards.incoming[trait, "innate_trait"] + cards.incoming[trait, "grants_trait"]
            )
            if kind == "creature":
                focus["materials"] += [c for c in carriers if c["kind"] == "material"]
            else:
                focus["creatures"] += [c for c in carriers if c["kind"] == "creature"]
        race = next((c["race"] for c in focus["classification"] if c.get("race")), None)
        if race:
            focus["family"] = tables.family[race]
    if kind in ("realm", "god", "shop", "acquisition_source"):
        focus["selectable"] = False
    if kind in ("realm", "acquisition_source"):
        for product in objects([k for k in cards.stock[key] if k in cards.classification]):
            product["routes"] = [r for r in product["routes"] if r["location"] == key]
            if kind == "acquisition_source":
                focus["products"].append(product)
            elif product["kind"] == "creature":
                product["traits"] = linked("innate_trait", product["id"])
                focus["creatures"].append(product)
    if kind == "realm":
        focus["related"] = objects(cards.incoming[key, "rules_realm"])
    if kind == "god":
        contents = linked("rules_realm") + linked("has_shop")
        contents += [summary(relic) for relic in tables.god_relics.get(key, [])]
        focus["god_contents"] = {
            "realms": [item for item in contents if item["kind"] == "realm"],
            "relics": [item for item in contents if item["kind"] == "relic"],
            "shops": [
                {**item, "offers": shop_offers(item["id"])}
                for item in contents
                if item["kind"] == "shop"
            ],
            "godspawn": linked("godspawn"),
            "ultimate_spells": linked("ultimate_spell"),
        }
        focus["sections"] = []
    if kind == "shop":
        focus["related"] = objects(cards.incoming[key, "has_shop"])
        focus["offers"] = shop_offers(key)
    if kind == "specialization":
        focus["perks"] = [summary(perk) for perk in tables.perks[focus["name"]]]
    if kind == "perk":
        parent = tables.specializations.get(focus["attrs"].get("specialization"))
        if parent:
            focus["parent"] = {"id": parent}
    return focus
