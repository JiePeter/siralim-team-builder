"""The tables that read and write links of Siralim Planner.

A link holds three parts for each creature. A part's code is the first six hex digits of the md5
of "family_creature_trait", lowercased, as the Compendium's Traits sheet spells them. Other codes
are the planner's own short names, kept in data/planner/codes.json.
"""

import hashlib
import json
from collections import defaultdict

from .current import norm
from .importer import DEFAULT_RAW, ROOT, read_xlsx

CODES = ROOT / "data/planner/codes.json"


def part_code(family, creature, trait):
    name = f"{family}_{creature}_{trait}".lower()
    return hashlib.md5(name.encode("utf-8")).hexdigest()[:6]


def planner_pack(db):
    """`traits` maps a part code to the creature and material that carry its Trait, if any."""
    names = {}
    for key, kind, name in db.execute("SELECT id,kind,name FROM entity"):
        names.setdefault((kind, norm(name)), key)
    for key, kind, alias in db.execute(
        "SELECT a.entity_id,e.kind,a.alias FROM entity_alias a JOIN entity e ON e.id=a.entity_id"
    ):
        names.setdefault((kind, norm(alias)), key)
    innate = dict(db.execute("SELECT src,dst FROM edge WHERE rel='innate_trait'"))
    materials = defaultdict(list)
    for material, trait in db.execute(
        "SELECT g.src,g.dst FROM edge g JOIN entity e ON e.id=g.src WHERE g.rel='grants_trait' AND e.kind='material' ORDER BY g.src"
    ):
        materials[trait].append(material)
    traits = {}
    for sheet, num, cells in read_xlsx(DEFAULT_RAW / "compendium.xlsx"):
        if sheet != "Traits" or num <= 2 or not all(cells.get(c) for c in "BCD"):
            continue
        trait = names[("trait", norm(cells["D"]))]
        creature = names.get(("creature", norm(cells["C"])))
        named = names.get(("material", norm(cells.get("F", ""))))
        material = named if named in materials[trait] else next(iter(materials[trait]), None)
        traits[part_code(cells["B"], cells["C"], cells["D"])] = [
            creature if innate.get(creature) == trait else None,
            material,
        ]
    return {"traits": traits, **json.loads(CODES.read_text(encoding="utf-8"))}
