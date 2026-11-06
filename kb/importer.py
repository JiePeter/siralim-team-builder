"""Rebuild derived SQLite data from the game data snapshot and community XLSX supplements.

Usage: python -m kb.importer [--raw DIRECTORY] [--db FILE]
No network, credentials, Excel installation or third-party packages required.
"""

import argparse
import difflib
import hashlib
import json
import re
import sqlite3
import tempfile
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = ROOT / "data/raw/community/2026-10-27"
DEFAULT_DB = ROOT / "data/knowledge.sqlite3"
SCHEMA = """
CREATE TABLE entity(id TEXT PRIMARY KEY,kind TEXT,name TEXT,description TEXT DEFAULT '',attrs TEXT DEFAULT '{}',UNIQUE(kind,name));
CREATE TABLE edge(src TEXT,rel TEXT,dst TEXT,row_id TEXT,attrs TEXT DEFAULT '{}',UNIQUE(src,rel,dst,row_id));
CREATE INDEX edge_src ON edge(src); CREATE INDEX edge_dst ON edge(dst);
CREATE TABLE route(id INTEGER PRIMARY KEY,entity_id TEXT,method TEXT,location TEXT,requirements TEXT,certainty TEXT,row_id TEXT,notes TEXT);
CREATE INDEX route_entity ON route(entity_id);
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE game_entity(kind TEXT,game_id TEXT,entity_id TEXT,body TEXT,row_id TEXT,PRIMARY KEY(kind,game_id));
CREATE INDEX game_entity_local ON game_entity(entity_id);
CREATE TABLE entity_alias(entity_id TEXT,alias TEXT,UNIQUE(entity_id,alias));
CREATE TABLE component(id TEXT PRIMARY KEY REFERENCES entity(id),kind TEXT NOT NULL,class TEXT,race TEXT,availability_basis TEXT NOT NULL);
CREATE TABLE shop_offer(id TEXT PRIMARY KEY,shop_id TEXT NOT NULL,item_id TEXT NOT NULL,delivery TEXT NOT NULL,quantity INTEGER NOT NULL,cost TEXT NOT NULL,requirements TEXT NOT NULL,row_id TEXT NOT NULL);
CREATE TABLE configuration(id TEXT PRIMARY KEY,kind TEXT,name TEXT,body TEXT);
CREATE TABLE sheet_override(entity_id TEXT,field TEXT,game_value TEXT,sheet_value TEXT,row_id TEXT,UNIQUE(entity_id,field));
"""


def clean(value):
    value = str(value or "").strip()
    # Numeric identifiers such as 4080 are names in specific columns.
    return re.sub(r"^(\d+)\.0$", r"\1", value)


def eid(kind, name):
    return kind + ":" + hashlib.sha256(name.casefold().encode()).hexdigest()[:20]


def read_xlsx(path):
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        rels = {
            r.attrib["Id"]: r.attrib["Target"]
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        }
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = [
                "".join(si.itertext()) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))
            ]
        for sh in ET.fromstring(z.read("xl/workbook.xml")).find("s:sheets", ns):
            target = rels[
                sh.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            ]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            for row in ET.fromstring(z.read(target)).findall("s:sheetData/s:row", ns):
                cells = {}
                for cell in row:
                    val = cell.find("s:v", ns)
                    inline = cell.find("s:is", ns)
                    text = (
                        val.text
                        if val is not None
                        else "".join(inline.itertext())
                        if inline is not None
                        else ""
                    )
                    if cell.attrib.get("t") == "s" and text:
                        text = strings[int(text)]
                    if text:
                        cells[re.sub(r"\d", "", cell.attrib["r"])] = text
                if cells:
                    yield sh.attrib["name"], int(row.attrib["r"]), cells


NO_MATERIAL = ("no material exists", "none", "n/a", "unobtainable")
# Kinds the game data defines. A community row names one of these rather than creating it.
GAME_KINDS = {
    "class",
    "condition",
    "creature",
    "enchantment",
    "enchantment_material",
    "god",
    "heart",
    "material",
    "race",
    "realm",
    "spell",
    "trait",
}
# The same entity under a spelling that normalization cannot join.
SHEET_SPELLINGS = {
    ("spell", "flame strike"): "Flamestrike",
    ("trait", "ramses' conspiracy"): "Ramses's Conspiracy",
    ("trait", "ramses' deception"): "Ramses's Deception",
    ("trait", "ramses' plot"): "Ramses's Plot",
    ("material", "ramses' crest"): "Ramses's Crest",
    ("material", "ramses' eye"): "Ramses's Eye",
    ("material", "ramses' mane"): "Ramses's Mane",
}
# The Creatures sheet gives these three each other's stats, rotated by one row.
SHEET_STATS_MISALIGNED = {"Priest Vizier", "Priest of Light", "Priest of Radiance"}
# Every other sheet name only respells the game's. These are different names or fix a game typo.
SHEET_NAMES = {
    ("enchantment", "Generous"),
    ("material", "Faded Garnet"),
    ("material", "Gruesome Tree Trunk"),
    ("material", "Kaito Banner"),
    ("material", "Math Textbook"),
    ("material", "Occultist Orb"),
    ("material", "Particle of 8004"),
    ("material", "Transient Spectre"),
    ("material", "Unguided Splinters"),
    ("material", "Woeful Spectre"),
    ("trait", "One of Us Must Change"),
}


class Importer:
    """Community sheet rows. Their values replace the game's; each difference is recorded."""

    def __init__(self, db):
        from .current import norm

        self.db = db
        self.norm = norm
        self.names = {}
        self.claimed = set()
        self.material_of = {}
        for key, kind, name in db.execute("SELECT id,kind,name FROM entity"):
            self.names.setdefault((kind, norm(name)), key)
        for key, kind, alias in db.execute(
            "SELECT a.entity_id,e.kind,a.alias FROM entity_alias a JOIN entity e ON e.id=a.entity_id"
        ):
            self.names.setdefault((kind, norm(alias)), key)
        self.realms = {
            norm(name): key
            for key, name in db.execute("SELECT id,name FROM entity WHERE kind='realm'")
        }
        # The game defines a relic only as part of its god, so a relic takes the god's number.
        self.relics = {
            norm(json.loads(body)["relicName"]): "relic:" + number
            for number, body in db.execute("SELECT game_id,body FROM game_entity WHERE kind='god'")
        }

    def find(self, kind, name):
        name = clean(name)
        if kind == "god":
            name = re.sub(r"^Vertaag\b", "Vertraag", name)
        name = SHEET_SPELLINGS.get((kind, self.norm(name)), name)
        return self.names.get((kind, self.norm(name)))

    def entity(self, kind, name, row, description="", **attrs):
        name = clean(name)
        if kind in ("god", "shop", "currency"):
            name = re.sub(r"^Vertaag\b", "Vertraag", name)
        if not name:
            raise ValueError("Entity name must not be empty")
        if kind in GAME_KINDS:
            key = self.find(kind, name)
            if not key:
                return None
        else:
            key = self.relics[self.norm(name.split(",")[0])] if kind == "relic" else eid(kind, name)
            self.db.execute(
                "INSERT OR IGNORE INTO entity(id,kind,name,description,attrs) VALUES(?,?,?,?,'{}')",
                (key, kind, name, description),
            )
        if attrs:
            values = json.loads(
                self.db.execute("SELECT attrs FROM entity WHERE id=?", (key,)).fetchone()[0]
            )
            for k, v in attrs.items():
                values.setdefault(k, v)
            self.db.execute(
                "UPDATE entity SET attrs=? WHERE id=?",
                (json.dumps(values, ensure_ascii=False), key),
            )
        if description:
            self.db.execute(
                "UPDATE entity SET description=? WHERE id=? AND description=''", (description, key)
            )
        return key

    def claim(self, key, field):
        """The first sheet row to give a value for a field decides it."""
        if (key, field) in self.claimed:
            return False
        self.claimed.add((key, field))
        return True

    def record(self, key, field, game, sheet, row):
        self.db.execute(
            "INSERT OR IGNORE INTO sheet_override VALUES(?,?,?,?,?)",
            (key, field, str(game), str(sheet), row),
        )

    def describe(self, key, value, row):
        value = re.sub(r"[ \t]+", " ", str(value or "")).strip()
        if not value or not self.claim(key, "description"):
            return
        game = self.db.execute("SELECT description FROM entity WHERE id=?", (key,)).fetchone()[0]
        if " ".join(value.split()) != " ".join(game.split()):
            self.db.execute("UPDATE entity SET description=? WHERE id=?", (value, key))
            if game:
                self.record(key, "description", game, value, row)

    def rename(self, key, name, row):
        name = clean(name)
        kind, game = self.db.execute("SELECT kind,name FROM entity WHERE id=?", (key,)).fetchone()
        if (kind, name) not in SHEET_NAMES or not self.claim(key, "name"):
            self.alias(key, name)
            return
        if name == game:
            return
        if self.db.execute("SELECT 1 FROM entity WHERE kind=? AND name=?", (kind, name)).fetchone():
            self.alias(key, name)
            return
        self.db.execute("UPDATE entity SET name=? WHERE id=?", (name, key))
        self.db.execute("DELETE FROM entity_alias WHERE entity_id=? AND alias=?", (key, name))
        self.db.execute("INSERT OR IGNORE INTO entity_alias VALUES(?,?)", (key, game))
        self.names.setdefault((kind, self.norm(name)), key)
        self.record(key, "name", game, name, row)

    def alias(self, key, name):
        name = clean(name)
        kind, current = self.db.execute(
            "SELECT kind,name FROM entity WHERE id=?", (key,)
        ).fetchone()
        if self.norm(name) != self.norm(current):
            self.db.execute("INSERT OR IGNORE INTO entity_alias VALUES(?,?)", (key, name))
            self.names.setdefault((kind, self.norm(name)), key)

    def relate(self, key, rel, target, row):
        """Replace a game relation of one kind with the sheet's."""
        if not self.claim(key, rel):
            return
        old = [
            r[0] for r in self.db.execute("SELECT dst FROM edge WHERE src=? AND rel=?", (key, rel))
        ]
        if old == [target]:
            return
        self.db.execute("DELETE FROM edge WHERE src=? AND rel=?", (key, rel))
        self.edge(key, rel, target, row)
        if old:
            self.record(key, rel, ",".join(old), target, row)

    def edge(self, src, rel, dst, row, **attrs):
        self.db.execute(
            "INSERT OR IGNORE INTO edge VALUES(?,?,?,?,?)",
            (src, rel, dst, row, json.dumps(attrs, ensure_ascii=False)),
        )

    def route(self, entity, method, location, req, certainty, row, notes=""):
        self.db.execute(
            "INSERT INTO route(entity_id,method,location,requirements,certainty,row_id,notes) VALUES(?,?,?,?,?,?,?)",
            (entity, method, location, json.dumps(req, ensure_ascii=False), certainty, row, notes),
        )

    def game(self, key, kind):
        return [
            json.loads(body)
            for (body,) in self.db.execute(
                "SELECT body FROM game_entity WHERE entity_id=? AND kind=?", (key, kind)
            )
        ]

    def game_key(self, kind, gid):
        row = self.db.execute(
            "SELECT entity_id,row_id FROM game_entity WHERE kind=? AND game_id=?", (kind, str(gid))
        ).fetchone()
        return row or (None, None)

    def routed(self, entity, place):
        return self.db.execute(
            "SELECT id,requirements FROM route WHERE entity_id=? AND location=? ORDER BY id",
            (entity, place),
        ).fetchone()

    def supplement(self, found, req):
        """Add a sheet source's facts to the game's route for the same place."""
        values = json.loads(found[1])
        values.update(req)
        self.db.execute(
            "UPDATE route SET requirements=? WHERE id=?",
            (json.dumps(values, ensure_ascii=False), found[0]),
        )

    def trait(self, name, desc, material, row, creature=None):
        """The trait a row names, by name, its creature, or its material."""
        t = self.find("trait", name)
        if not t and creature:
            t = next(
                iter(
                    r[0]
                    for r in self.db.execute(
                        "SELECT dst FROM edge WHERE src=? AND rel='innate_trait'", (creature,)
                    )
                ),
                None,
            )
        named = self.find("material", material) if material else None
        if not t and named:
            records = self.game(named, "material")
            if records and records[0].get("trait") is not None:
                t = self.game_key("trait", records[0]["trait"])[0]
        if not t:
            if not material or material.casefold() in NO_MATERIAL or named:
                return None
            raise ValueError(f"Trait and material are not in the game data: {name}, {material}")
        self.rename(t, name, row)
        self.describe(t, desc, row)
        self.material(t, material, row)
        return t

    def material(self, trait, name, row):
        """A listed trait material is obtainable, and the sheet decides which item carries the trait."""
        if not name or name.casefold() in NO_MATERIAL:
            return None
        named = self.find("material", name)
        if trait in self.material_of:
            key = self.material_of[trait]
            if not named:
                self.alias(key, name)
            return key
        item = next(
            (r["item"] for r in self.game(trait, "trait") if r.get("item") is not None), None
        )
        key, rid = self.game_key("material", item) if item is not None else (None, None)
        trait_name = self.db.execute("SELECT name FROM entity WHERE id=?", (trait,)).fetchone()[0]
        if named and named != key:
            rid = self.db.execute(
                "SELECT row_id FROM game_entity WHERE kind='material' AND entity_id=?", (named,)
            ).fetchone()
            rid = rid[0] if rid else row
            if key:
                self.record(trait, "material", key, named, row)
            self.db.execute("DELETE FROM edge WHERE rel='grants_trait' AND dst=?", (trait,))
            key = named
        if not key:
            return None
        self.edge(key, "grants_trait", trait, rid)
        self.material_of[trait] = key
        # The sheets sometimes repeat the trait's name in their material columns.
        if not named:
            similar = difflib.SequenceMatcher(None, self.norm(name), self.norm(trait_name)).ratio()
            if similar < 0.9:
                self.rename(key, name, row)
        else:
            self.rename(key, name, row)
        return key

    def source_routes(self, entity, text, depth, row):
        # Commas inside parentheses belong to one source specification.
        for token in re.split(r",\s*(?![^()]*\))", text):
            token = token.strip()
            if not token:
                continue
            req = {"source_text": token}
            if depth:
                req["source_realm_depth"] = clean(depth)
            shop = re.fullmatch(
                r"([^+]+?) God Shop\s*(?:\(Favor Rank (\d+)\))?(?:\s*(\+ Project))?", token, re.I
            )
            god = self.find("god", shop[1]) if shop else None
            if god:
                place = self.entity("shop", shop[1] + " God Shop", row)
                if shop[2]:
                    req["favor_rank"] = int(shop[2])
                if shop[3]:
                    req["project_required"] = True
                found = self.routed(entity, place)
                if found:
                    self.supplement(found, req)
                # The game lists the Heart that a Godspawn's project consumes in this shop.
                elif not (
                    shop[3]
                    and self.db.execute(
                        "SELECT 1 FROM route r JOIN entity e ON e.id=r.entity_id WHERE r.location=? AND e.kind='heart'",
                        (place,),
                    ).fetchone()
                ):
                    self.route(
                        entity,
                        "god_shop_source",
                        place,
                        req,
                        "specified_source",
                        row,
                        "生物来源记录；完整价格／商品条件以独立商店商品记录为准",
                    )
                continue
            other_shop = re.fullmatch(
                r"(Arena Shop|Gambling Dwarf Shop|(?:Life|Death|Chaos|Nature|Sorcery) Guild)(?: \(Rank (\d+)\))?",
                token,
            )
            if other_shop:
                place = self.entity("shop", other_shop[1], row)
                if other_shop[2]:
                    req["rank"] = int(other_shop[2])
                found = self.routed(entity, place)
                if found:
                    self.supplement(found, req)
                else:
                    self.route(
                        entity,
                        "shop_source",
                        place,
                        req,
                        "specified_source",
                        row,
                        "来源表列出的商店／公会；未提供价格的字段不补写",
                    )
                continue
            realm = self.realms.get(self.norm(re.sub(r"\s*\([^)]*\)\s*$", "", token)))
            if realm:
                interaction = re.search(r"\(([^)]+)\)", token)
                if interaction:
                    req["interaction"] = interaction[1]
                method = "realm_interaction" if interaction else "realm_encounter"
                # The game names the realm; the sheet adds its depth and named interaction.
                found = self.db.execute(
                    "SELECT id,method FROM route WHERE entity_id=? AND location=? AND method IN ('realm_encounter','realm_interaction')",
                    (entity, realm),
                ).fetchone()
                if found:
                    if found[1] == "realm_encounter" or interaction:
                        self.db.execute(
                            "UPDATE route SET method=?,requirements=? WHERE id=?",
                            (method, json.dumps(req, ensure_ascii=False), found[0]),
                        )
                else:
                    self.route(
                        entity,
                        method,
                        realm,
                        req,
                        "encounter_rng",
                        row,
                        "来源存在，不保证每层出现；此记录不代表材料掉落保证",
                    )
                continue
            # Combined entries repeat purchases the game routes separately.
            if (
                re.search(r"God Shop|Guild", token)
                and self.db.execute(
                    "SELECT 1 FROM route WHERE entity_id=? AND method LIKE 'purchase%'", (entity,)
                ).fetchone()
            ):
                continue
            if token.endswith(" Master"):
                master = self.db.execute(
                    "SELECT r.id,r.requirements,e.id FROM route r JOIN entity e ON e.id=r.location WHERE r.entity_id=? AND e.name LIKE '% Master'",
                    (entity,),
                ).fetchone()
                if master:
                    self.rename(master[2], token, row)
                    self.supplement(master, req)
                    continue
            place = self.entity("acquisition_source", token, row)
            found = self.routed(entity, place)
            if found:
                self.supplement(found, req)
                continue
            self.route(
                entity,
                "other_source",
                place,
                req,
                "not_classified",
                row,
                "保留原始来源；未推定入口概率、可重复性或解锁条件",
            )

    def creature(self, c, row):
        cr = self.entity("creature", c["A"], row)
        if not cr:
            return None
        self.rename(cr, c["A"], row)
        values = json.loads(
            self.db.execute("SELECT attrs FROM entity WHERE id=?", (cr,)).fetchone()[0]
        )
        stats = {
            k: clean(c.get(col))
            for k, col in zip(("health", "attack", "intelligence", "defense", "speed"), "DEFGH")
        }
        if (
            clean(c["A"]) not in SHEET_STATS_MISALIGNED
            and all(re.fullmatch(r"\d+", v) for v in stats.values())
            and values.get("stats") != stats
        ):
            self.record(cr, "stats", json.dumps(values.get("stats")), json.dumps(stats), row)
            values.update(stats=stats)
        for kind, col, rel in (("race", "B", "belongs_to"), ("class", "C", "has_class")):
            target = self.find(kind, c[col]) if c.get(col) else None
            if target:
                self.relate(cr, rel, target, row)
        self.db.execute(
            "UPDATE entity SET attrs=? WHERE id=?", (json.dumps(values, ensure_ascii=False), cr)
        )
        return cr

    def spell(self, c, row):
        name = clean(c["C"])
        # Five sheet rows share the name Colorwave and differ by class; the game keeps them apart.
        qualified = self.find("spell", f"{name} ({c.get('A')})")
        s = qualified or self.find("spell", name)
        if not s:
            return
        if not qualified:
            self.rename(s, name, row)
        self.describe(s, c.get("D"), row)
        values = json.loads(
            self.db.execute("SELECT attrs FROM entity WHERE id=?", (s,)).fetchone()[0]
        )
        charges = clean(c.get("B"))
        if re.fullmatch(r"\d+", charges) and values.get("charges") != int(charges):
            self.record(s, "charges", values.get("charges"), charges, row)
            values["charges"] = int(charges)
        if c.get("A") and values.get("class") != c["A"]:
            self.record(s, "class", values.get("class"), c["A"], row)
            values["class"] = c["A"]
        self.db.execute(
            "UPDATE entity SET attrs=? WHERE id=?", (json.dumps(values, ensure_ascii=False), s)
        )

    def god_shop(self, c, row):
        god = re.sub(r"^Vertaag\b", "Vertraag", clean(c["A"]))
        shop = self.entity("shop", god + " God Shop", row)
        typ = c["E"]
        kind = {
            "Mana": "creature",
            "Trait": "material",
            "Inscription": "spell",
            "Crafting Material": "enchantment_material",
            "Heart": "heart",
        }.get(typ)
        item = self.find(kind, c["C"]) if kind else None
        if not item:
            return
        found = self.routed(item, shop)
        cost, rank = int(float(clean(c.get("D")))), int(float(clean(c.get("B"))))
        if found:
            values = json.loads(found[1])
            if values.get("cost") != cost:
                self.record(item, "price:" + god, values.get("cost"), cost, row)
            if values.get("favor_rank") != rank:
                self.record(item, "favor_rank:" + god, values.get("favor_rank"), rank, row)
            self.supplement(found, {"cost": cost, "favor_rank": rank})
            target = values.get("inscription", item)
            for offer, body, conditions in self.db.execute(
                "SELECT id,cost,requirements FROM shop_offer WHERE shop_id=? AND item_id=?",
                (shop, target),
            ).fetchall():
                self.db.execute(
                    "UPDATE shop_offer SET cost=?,requirements=? WHERE id=?",
                    (
                        json.dumps({**json.loads(body), "cost": cost}),
                        json.dumps({**json.loads(conditions), "favor_rank": rank}),
                        offer,
                    ),
                )
        else:
            self.route(
                item,
                "purchase",
                shop,
                {
                    "cost": cost,
                    "currency": god + " Emblems",
                    "favor_rank": rank,
                    "item_type": typ,
                },
                "guaranteed_purchase_when_unlocked",
                row,
            )
        if typ == "Crafting Material":
            prop = re.search(r"add the (.+?) property", c.get("F", ""), re.I)
            target = self.db.execute(
                "SELECT dst FROM edge WHERE src=? AND rel='adds_property'", (item,)
            ).fetchone()
            if prop and target:
                self.rename(target[0], prop[1], row)

    def load(self, rows):
        for source, sheet, num, c, rid in rows:
            if source == "compendium" and sheet == "Traits" and num > 2:
                if not c.get("D") or not c.get("E"):
                    continue
                creature = self.find("creature", c["C"]) if c.get("C") else None
                t = self.trait(c["D"], c["E"], c.get("F"), rid, creature)
                if not t:
                    continue
                family = self.find("race", c.get("B", "Unspecified"))
                if family:
                    self.edge(t, "listed_family", family, rid)
                cls = self.find("class", c.get("A", ""))
                if cls:
                    self.edge(t, "listed_class", cls, rid)
            elif source == "compendium" and sheet == "Spells" and num > 1 and c.get("C"):
                self.spell(c, rid)
            elif source == "creatures" and sheet == "Creatures" and num > 2:
                if not c.get("A") or not c.get("L"):
                    continue
                cr = self.creature(c, rid)
                if not cr:
                    continue
                self.trait(c["L"], c.get("N", ""), c.get("M"), rid, cr)
                self.source_routes(cr, c.get("K", ""), c.get("J"), rid)
            elif source == "creatures" and sheet == "Trait Items" and num > 1:
                if not c.get("A"):
                    continue
                t = self.trait(c["A"], c.get("D", ""), c.get("B"), rid)
                material = self.material(t, c.get("B"), rid) if t else None
                if material:
                    self.source_routes(material, c.get("C", ""), None, rid)
            elif source == "compendium" and sheet == "God Shops" and num > 1:
                if all(c.get(k) for k in ("A", "C", "E")):
                    self.god_shop(c, rid)
            elif source == "compendium" and sheet == "Relics" and num > 1 and c.get("B"):
                relic = self.entity("relic", c["B"], rid)
                effect = self.entity(
                    "relic_effect",
                    clean(c["B"]) + " · Rank " + clean(c.get("D")),
                    rid,
                    c.get("E", ""),
                    rank=clean(c.get("D")),
                )
                self.edge(relic, "rank_effect", effect, rid)
            elif (
                source == "compendium"
                and sheet == "Avatar Reference Sheet"
                and num > 1
                and c.get("A")
            ):
                god = self.find("god", c["A"])
                if not god:
                    continue
                creature = self.find("creature", c["B"]) if c.get("B") else None
                if creature:
                    self.relate(god, "godspawn", creature, rid)
                spell = self.find("spell", c["D"]) if c.get("D") else None
                if spell:
                    self.edge(god, "ultimate_spell", spell, rid)
            elif source == "creatures" and sheet == "Races" and num > 1 and c.get("A"):
                self.entity("race", c["A"], rid, c.get("B", ""))


def draw_traits_as_materials(db):
    """A trait no creature carries has no sprite of its own, so it takes its material's."""
    found = """SELECT json_extract(m.attrs,'$.image') FROM edge g JOIN entity m ON m.id=g.src
               WHERE g.rel='grants_trait' AND g.dst=entity.id
               AND json_extract(m.attrs,'$.image') IS NOT NULL ORDER BY m.name LIMIT 1"""
    db.execute(
        f"""UPDATE entity SET attrs=json_set(attrs,'$.image',({found}))
            WHERE kind='trait' AND json_extract(attrs,'$.image') IS NULL AND ({found}) IS NOT NULL"""
    )


def build(raw=DEFAULT_RAW, output=DEFAULT_DB):
    raw, output = Path(raw), Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Build separately and atomically replace derived data. User plans live elsewhere.
    fd, temp = tempfile.mkstemp(prefix="knowledge-", suffix=".sqlite3", dir=output.parent)
    os.close(fd)
    db = sqlite3.connect(temp)
    try:
        db.executescript(SCHEMA)
        rows = []
        for key, filename in (
            ("compendium", "compendium.xlsx"),
            ("creatures", "creature-trait-sheet.xlsx"),
        ):
            for sheet, num, cells in read_xlsx(raw / filename):
                rows.append((key, sheet, num, cells, f"{key}:{sheet}:{num}"))
        from . import annotations, catalog, current, reference

        annotations.load_names(db)
        current.load(db)
        Importer(db).load(rows)
        current.relics(db)
        draw_traits_as_materials(db)
        catalog.project(db)
        reference.load(db)
        annotations.load(db)
        db.execute("INSERT INTO meta VALUES('snapshot',?)", (raw.name,))
        db.commit()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(integrity)
        report = {
            "entities": dict(db.execute("SELECT kind,count(*) FROM entity GROUP BY kind")),
            "routes": db.execute("SELECT count(*) FROM route").fetchone()[0],
        }
        db.close()
        os.replace(temp, output)
        return report
    except BaseException:
        db.close()
        Path(temp).unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(build(args.raw, args.db), ensure_ascii=False, indent=2))
