"""Versioned 2.0.38 game data: the entities, links and typed routes every other source supplements."""

import functools
import json
import re
import unicodedata
from .importer import ROOT, eid

SNAPSHOT = ROOT / "data/raw/siralim-json/2.0.38-0.3.0"
# Community spellings of game names, which the sheets may still use.
CREATURE_ALIASES = {
    "Avaritia Sin": "Avarita Sin",
    "Bashcloak": "Bashloack",
    "Gloopdiator": "Gloopidator",
    "Holyguanodon": "Holyguanadon",
    "Marionette Charlatan": "Maionette Charlatan",
    "Manticore Conqueror": "Manticore Conquerer",
    "Phenomenal Possum": "Phenominal Possum",
}
SPELL_ALIASES = {
    "Chaos Channeling": "Chaos Channelling",
    "Colorwave (Chaos)": "Colorwave",
    "Icicle Rain": "Iceicle Rain",
    "Ignis Fatuus": "Ignus Fatuus",
    "Prismatic Channeling": "Prismatic Channelling",
    "Vilify": "Villify",
}
# The game lists this gemstone's four concrete properties without one name for them.
ENCHANTMENT_NAMES = {"Citrine": "Chance to Cast After Action"}
ENCHANTMENT_ALIASES = {"Generosity": "Generous"}
# Saved acquisition source ids use the community's names for these game sources.
SOURCE_NAMES = {"Otherworld Portals": "Otherworld Portal", "Nether Realm": "Nether Realms"}
CLASSES = ("Chaos", "Death", "Life", "Nature", "Sorcery")
GUILD_CURRENCY = {
    "nature": "Crystal",
    "chaos": "Brimstone",
    "sorcery": "Essence",
    "death": "Granite",
    "life": "Power",
}


def norm(text):
    return " ".join(unicodedata.normalize("NFKC", str(text)).replace("’", "'").casefold().split())


def records(name):
    return json.loads((SNAPSHOT / name).read_text(encoding="utf-8-sig"))


@functools.cache
def manifest():
    return json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))


@functools.cache
def tokens():
    return records("tokens.json")


def text(value):
    value = str(value or "").replace("\\\\n", "\n").replace("\\n", "\n")
    for _ in range(6):
        updated = re.sub(r"\{([^{}]+)\}", lambda m: str(tokens().get(m[1], m[0])), value)
        if updated == value:
            break
        value = updated
    value = re.sub(r"\[[a-z_]+(?:,\d+)?\]", "", value)
    value = re.sub(r"<([\d.]+)>%", r"\1% per rank", value)
    value = re.sub(r"<([\d.]+)>", r"\1 per rank", value)
    return re.sub(r"[ \t]+", " ", value).strip()


@functools.cache
def assets():
    base = ROOT / "app/public/assets/siralim"
    return frozenset(p.relative_to(base).as_posix() for p in base.rglob("*.png"))


def image(path):
    return "/assets/siralim/" + path if path in assets() else None


def swapped_class(label):
    """The class a Class Swap property turns its Spell Gem into, as the data names classes."""
    found = re.fullmatch(r"Class Swap: (\w+)", label)
    return {"class": found[1]} if found else {}


def spelled(kind, name):
    """The community's spelling of a game name."""
    aliases = {
        "creature": CREATURE_ALIASES,
        "spell": SPELL_ALIASES,
        "enchantment": ENCHANTMENT_ALIASES,
    }.get(kind, {})
    return aliases.get(name, name)


def load(db):
    db.execute("INSERT INTO meta VALUES(?,?)", ("game_version", manifest()["version"]))
    db.execute("INSERT INTO meta VALUES(?,?)", ("game_data_release", manifest()["release"]))
    data = {}
    rowids = {}
    for path in SNAPSHOT.glob("*.json"):
        name = path.name
        if name == "manifest.json":
            continue
        data[name] = records(name)
        if not isinstance(data[name], list):
            continue
        for index, record in enumerate(data[name]):
            rowids[name, str(record.get("id", record.get("name", index)))] = (
                "game238:" + name + ":" + str(index)
            )
    mapped = {}

    def attrs_of(key):
        return json.loads(db.execute("SELECT attrs FROM entity WHERE id=?", (key,)).fetchone()[0])

    def edge(src, rel, dst, row):
        db.execute("INSERT OR IGNORE INTO edge VALUES(?,?,?,?,'{}')", (src, rel, dst, row))

    def put(kind, record, filename, attrs=None, description=None, key=None):
        name = record["name"]
        gid = str(record.get("id", name))
        # The game's own number survives renames and respellings; races have none.
        key = key or (f"{kind}:{gid}" if "id" in record else eid(kind, name))
        previous = db.execute("SELECT attrs,description FROM entity WHERE id=?", (key,)).fetchone()
        values = json.loads(previous[0]) if previous else {}
        values.update(attrs or {})
        portrait = image(record.get("battleSprite")) or image(record.get("icon"))
        if portrait:
            values["image"] = portrait
        description = text(
            description if description is not None else record.get("description", "")
        )
        if previous:
            db.execute(
                "UPDATE entity SET name=?,description=?,attrs=? WHERE id=?",
                (name, description or previous[1], json.dumps(values, ensure_ascii=False), key),
            )
        else:
            db.execute(
                "INSERT INTO entity VALUES(?,?,?,?,?)",
                (key, kind, name, description, json.dumps(values, ensure_ascii=False)),
            )
        if spelled(kind, name) != name:
            db.execute("INSERT OR IGNORE INTO entity_alias VALUES(?,?)", (key, spelled(kind, name)))
        mapped[kind, gid] = key
        db.execute(
            "INSERT OR REPLACE INTO game_entity VALUES(?,?,?,?,?)",
            (kind, gid, key, json.dumps(record, ensure_ascii=False), rowids.get((filename, gid))),
        )
        return key

    for cls in CLASSES:
        db.execute(
            "INSERT INTO entity VALUES(?,'class',?,'',?)",
            (
                eid("class", cls),
                cls,
                json.dumps({"image": image("images/misc/class/" + cls.lower() + ".png")}),
            ),
        )
    for r in data["races.json"]:
        race = put("race", r, "races.json")
        bonuses = r.get("cardBonuses") or {}
        if bonuses:
            tiers = sorted(bonuses, key=int)
            card = eid("card_set", r["name"])
            db.execute(
                "INSERT OR REPLACE INTO entity VALUES(?,?,?,?,?)",
                (
                    card,
                    "card_set",
                    r["name"],
                    "\n".join(text(bonuses[t]) for t in tiers),
                    json.dumps({"tiers": " / ".join(tiers)}),
                ),
            )
            edge(race, "card_rewards", card, rowids["races.json", r["name"]])
    for r in data["realms.json"]:
        put("realm", r, "realms.json", attrs={"image": image(r["emblemIcon"])})
    for r in data["gods.json"]:
        put("god", r, "gods.json")
    gods = {g["id"]: g for g in data["gods.json"]}
    for r in data["realms.json"]:
        god = mapped["god", str(r["god"])]
        row = rowids["realms.json", str(r["id"])]
        edge(god, "rules_realm", mapped["realm", str(r["id"])], row)
        shop = eid("shop", gods[r["god"]]["name"] + " God Shop")
        db.execute(
            "INSERT OR IGNORE INTO entity VALUES(?,'shop',?,'',?)",
            (
                shop,
                gods[r["god"]]["name"] + " God Shop",
                json.dumps({"image": attrs_of(god).get("image")}),
            ),
        )
        edge(god, "has_shop", shop, row)
    sourced = [r for r in data["creatures.json"] if r["sources"]]
    used_traits = {r["trait"] for r in sourced}
    for r in sorted(data["traits.json"], key=lambda r: r["id"] not in used_traits):
        put("trait", r, "traits.json")
    # Creatures without any game source stay addressable; a supplement may still give one a route.
    for r in sorted(data["creatures.json"], key=lambda r: not r["sources"]):
        cls = r["class"].title()
        race = mapped.get(("race", r["race"]))
        key = put(
            "creature",
            r,
            "creatures.json",
            attrs={
                "stats": {k: str(v) for k, v in r["statGrowth"].items()},
            },
            description="",
        )
        row = rowids["creatures.json", str(r["id"])]
        edge(key, "has_class", eid("class", cls), row)
        if race:
            edge(key, "belongs_to", race, row)
        trait = mapped.get(("trait", str(r["trait"])))
        if trait:
            edge(key, "innate_trait", trait, row)
            attrs = attrs_of(trait)
            if image(r["battleSprite"]):
                attrs.setdefault("image", image(r["battleSprite"]))
                db.execute("UPDATE entity SET attrs=? WHERE id=?", (json.dumps(attrs), trait))
    # A trait is classified by the creature the game names as its owner.
    creatures = {r["id"]: r for r in data["creatures.json"]}
    for r in data["traits.json"]:
        owner = creatures.get(r.get("creature"))
        if owner:
            trait = mapped["trait", str(r["id"])]
            row = rowids["traits.json", str(r["id"])]
            edge(trait, "has_class", eid("class", owner["class"].title()), row)
            if ("race", owner["race"]) in mapped:
                edge(trait, "belongs_to", mapped["race", owner["race"]], row)
    specs = {r["id"]: r for r in data["specializations.json"]}
    for r in specs.values():
        key = put(
            "specialization",
            r,
            "specializations.json",
            key=f"spec:{r['id']}",
            description="\n\n".join(r["description"]),
        )
        meta = {
            "image": image(r["icon"]),
            "description": text("\n\n".join(r["description"])),
        }
        db.execute(
            "INSERT OR REPLACE INTO configuration VALUES(?,?,?,?)",
            (key, "specialization", r["name"], json.dumps(meta)),
        )
    for r in data["perks.json"]:
        spec = specs[r["specialization"]]
        meta = {
            "specialization": spec["name"],
            "ranks": r["maxRanks"],
            "anointment": r["anointable"],
            "ascension": spec["ascendedPerk"] == r["id"],
            "short_name": r["name"],
            "image": image(r["icon"]),
        }
        key = put("perk", r, "perks.json", attrs=meta)
        # Perk display names include their specialization because many names repeat.
        db.execute("UPDATE entity SET name=? WHERE id=?", (r["name"] + " · " + spec["name"], key))
        db.execute(
            "INSERT OR REPLACE INTO configuration VALUES(?,?,?,?)",
            (key, "perk", r["name"] + " · " + spec["name"], json.dumps(meta)),
        )
    for r in data["spells.json"]:
        put(
            "spell",
            r,
            "spells.json",
            attrs={
                "class": r["class"].title(),
                "charges": r["maxCharges"],
                "property_compatibility": r["propertyCompatibility"],
                "manually_castable": r["manuallyCastable"],
                "obtainable": r["obtainable"],
                "image": image("images/misc/category/spell.png"),
            },
        )
    # A trait material is evidenced here when its trait is innate to a creature the player can
    # get, or a race master drops it; the community lists supply the remaining ones.
    traits = {r["id"]: r for r in data["traits.json"]}
    materials = {r["id"] for r in data["materials.json"]}
    obtainable = used_traits | {r["master"]["trait"] for r in data["races.json"] if r.get("master")}
    for r in data["materials.json"]:
        key = put("material", r, "materials.json")
        trait = traits.get(r.get("trait"))
        if (
            trait
            and r["slot"] == "trait"
            and trait["id"] in obtainable
            and (trait.get("item") == r["id"] or trait.get("item") not in materials)
        ):
            edge(
                key,
                "grants_trait",
                mapped["trait", str(trait["id"])],
                rowids["materials.json", str(r["id"])],
            )
    for r in data["conditions.json"]:
        values = {"type": r["type"]}
        for source, target in [
            ("initialDuration", "duration"),
            ("leaveChance", "leave_chance"),
            ("maxStacks", "max_stacks"),
        ]:
            if source in r:
                values[target] = r[source]
        put("condition", r, "conditions.json", attrs=values)
        if r["type"] in ("buff", "debuff"):
            db.execute("INSERT OR REPLACE INTO mechanic_status VALUES(?,?)", (r["name"], r["type"]))
    # A gemstone names one logical property; the game splits some into several concrete ones.
    props = {r["id"]: r for r in data["spellProperties.json"]}
    for r in data["spellPropertyItems.json"]:
        material = put("enchantment_material", r, "spellPropertyItems.json")
        name = ENCHANTMENT_NAMES.get(r["name"]) or text(r["description"]).split("\n\n")[-1]
        name = name.split(":")[0].strip()
        attrs = {
            "game_property_ids": r["spellProperties"],
            "variants": [
                {
                    "id": gid,
                    "label": text(props[gid]["shortDescription"]),
                    "image": image(props[gid]["icon"]),
                    **swapped_class(props[gid]["shortDescription"]),
                }
                for gid in r["spellProperties"]
            ],
            "image": image(r["icon"]),
        }
        prop = f"enchantment:{r['id']}"
        db.execute(
            "INSERT INTO entity VALUES(?,'enchantment',?,'',?)", (prop, name, json.dumps(attrs))
        )
        if spelled("enchantment", name) != name:
            db.execute("INSERT INTO entity_alias VALUES(?,?)", (prop, spelled("enchantment", name)))
        edge(material, "adds_property", prop, rowids["spellPropertyItems.json", str(r["id"])])

    def route(kind, filename, record, method, place, req):
        key = mapped[kind, str(record["id"])]
        rid = rowids[filename, str(record["id"])]
        if method == "purchase":
            req["item_type"] = {"creature": "Mana", "spell": "Inscription", "heart": "Heart"}.get(
                kind
            )
            if not req["item_type"]:
                del req["item_type"]
        if kind == "spell" and method == "purchase":
            method = "purchase_inscription_then_craft"
            inscription = eid("inscription", record["name"])
            db.execute(
                "INSERT OR IGNORE INTO entity VALUES(?,'inscription',?,'','{}')",
                (inscription, record["name"]),
            )
            edge(inscription, "unlocks_spell", key, rid)
            req["inscription"] = inscription
        db.execute(
            "INSERT INTO route(entity_id,method,location,requirements,certainty,row_id,notes) VALUES(?,?,?,?,?,?,'')",
            (
                key,
                method,
                place,
                json.dumps(req),
                "purchase_guaranteed"
                if method.startswith("purchase")
                else "encounter_rng"
                if method.startswith("realm_")
                else "explicit_game",
                rid,
            ),
        )
        if method.startswith("purchase"):
            delivery = {
                "creature": "summon_unlock",
                "spell": "craft_unlock",
                "heart": "project_material",
            }.get(kind, "item")
            item = req.get("inscription", key)
            # Stable identity is shop, output and delivery.
            offer = eid("shop_offer", place + "|" + item + "|" + delivery)
            cost = {k: req[k] for k in ("cost", "currency") if k in req}
            conditions = {k: v for k, v in req.items() if k not in cost}
            db.execute(
                "INSERT OR REPLACE INTO shop_offer VALUES(?,?,?,?,1,?,?,?)",
                (offer, place, item, delivery, json.dumps(cost), json.dumps(conditions), rid),
            )

    def place(name):
        key = eid("acquisition_source", name)
        db.execute(
            "INSERT OR IGNORE INTO entity VALUES(?,'acquisition_source',?,'','{}')", (key, name)
        )
        return key

    projects = {r["id"]: r for r in data["projects.json"]}
    unlocking = {
        r["unlockedCreature"]: r["name"]
        for r in projects.values()
        if r.get("unlockedCreature") is not None
    }
    hearts = {
        i["id"]
        for r in data["realms.json"]
        for tier in r["godShop"].values()
        for i in tier
        if i["type"] == "projectItem"
    }
    by_heart = {
        projects[p].get("unlockedCreature")
        for r in data["projectItems.json"]
        if r["id"] in hearts
        for p in r["projects"]
    }
    for kind, filename in [
        ("creature", "creatures.json"),
        ("spell", "spells.json"),
        ("material", "materials.json"),
        ("enchantment_material", "spellPropertyItems.json"),
    ]:
        for record in data[filename]:
            for source in record.get("sources") or []:
                typ = source["type"]
                if typ == "realm":
                    route(
                        kind,
                        filename,
                        record,
                        "realm_encounter",
                        mapped["realm", str(source["realm"])],
                        {},
                    )
                elif typ == "guild":
                    name = source["class"].title() + " Guild"
                    db.execute(
                        "INSERT OR IGNORE INTO entity VALUES(?,'shop',?,'','{}')",
                        (eid("shop", name), name),
                    )
                    req = {
                        "cost": source["cost"],
                        "currency": GUILD_CURRENCY[source["class"]],
                        "rank": source["rank"],
                    }
                    route(kind, filename, record, "purchase", eid("shop", name), req)
                elif typ == "gotg":
                    req = {"target": gods[source["god"]]["name"] if source["god"] in gods else ""}
                    route(kind, filename, record, "game_source", place("Gate of the Gods"), req)
                elif typ in ("gambling", "arena"):
                    name = "Gambling Dwarf Shop" if typ == "gambling" else "Arena Shop"
                    db.execute(
                        "INSERT OR IGNORE INTO entity VALUES(?,'shop',?,'','{}')",
                        (eid("shop", name), name),
                    )
                    req = {k: source[k] for k in ("cost", "rank") if k in source}
                    route(kind, filename, record, "purchase", eid("shop", name), req)
                elif typ == "special":
                    desc = source["desc"]
                    if desc == "Project" and record["id"] not in by_heart:
                        desc = unlocking.get(record["id"])
                    elif desc in ("Project", "???") or desc.startswith("God Shop"):
                        # A Heart or the god shop list already routes these; "???" names nothing.
                        desc = None
                    if desc:
                        name = SOURCE_NAMES.get(desc, desc)
                        route(kind, filename, record, "game_source", place(name), {})
    for r in data["races.json"]:
        master = r.get("master")
        if master and ("material", str(master["item"])) in mapped:
            record = next(m for m in data["materials.json"] if m["id"] == master["item"])
            route(
                "material",
                "materials.json",
                record,
                "game_source",
                place(r["name"] + " Master"),
                {},
            )
    # Each realm's god shop list is complete; an item's own sources can omit its shop.
    stock = {
        "creature": ("creature", "creatures.json"),
        "spell": ("spell", "spells.json"),
        "material": ("material", "materials.json"),
        "spellPropertyItem": ("enchantment_material", "spellPropertyItems.json"),
        "projectItem": ("heart", "projectItems.json"),
    }
    for r in data["realms.json"]:
        god = gods[r["god"]]["name"]
        for rank, items in sorted(r["godShop"].items(), key=lambda tier: int(tier[0])):
            for item in items:
                if item["type"] not in stock:
                    continue
                kind, filename = stock[item["type"]]
                record = next(x for x in data[filename] if x["id"] == item["id"])
                if (kind, str(item["id"])) not in mapped:
                    put(kind, record, filename)
                    for project in record.get("projects", []):
                        unlocked = projects[project].get("unlockedCreature")
                        if ("creature", str(unlocked)) in mapped:
                            edge(
                                mapped[kind, str(item["id"])],
                                "unlocks_creature",
                                mapped["creature", str(unlocked)],
                                rowids[filename, str(item["id"])],
                            )
                            # A god's shop sells the Heart that its Godspawn's project consumes.
                            edge(
                                mapped["god", str(r["god"])],
                                "godspawn",
                                mapped["creature", str(unlocked)],
                                rowids[filename, str(item["id"])],
                            )
                req = {"cost": item["cost"], "currency": god + " Emblems", "favor_rank": int(rank)}
                route(kind, filename, record, "purchase", eid("shop", god + " God Shop"), req)


def relics(db):
    """Art for the community's relics, matched by the game's relic name; the sheet keeps its texts."""
    for r in records("gods.json"):
        prefix = norm(r["relicName"].split(",")[0]) if r.get("relicName") else ""
        key = next(
            (
                key
                for key, name in db.execute("SELECT id,name FROM entity WHERE kind='relic'")
                if norm(name.split(",")[0]) == prefix
            ),
            None,
        )
        if not key:
            continue
        attrs = json.loads(db.execute("SELECT attrs FROM entity WHERE id=?", (key,)).fetchone()[0])
        attrs["image"] = image(r["relicBigIcon"])
        attrs["icon"] = image(r["relicSmallIcon"])
        db.execute("UPDATE entity SET attrs=? WHERE id=?", (json.dumps(attrs), key))
        for index, bonus in enumerate(r["relicBonuses"], 1):
            for effect, body, sheet, row in db.execute(
                """SELECT e.id,e.attrs,e.description,g.row_id FROM edge g JOIN entity e ON e.id=g.dst
                WHERE g.src=? AND g.rel='rank_effect'""",
                (key,),
            ).fetchall():
                if int(json.loads(body)["rank"]) != index * 10:
                    continue
                if not sheet:
                    db.execute("UPDATE entity SET description=? WHERE id=?", (text(bonus), effect))
                elif " ".join(sheet.split()) != " ".join(text(bonus).split()):
                    db.execute(
                        "INSERT OR IGNORE INTO sheet_override VALUES(?,'description',?,?,?)",
                        (effect, text(bonus), sheet, row),
                    )
