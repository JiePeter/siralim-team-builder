"""Build-facing catalog and acquisition aggregates over the preserved evidence store."""

import json
from .importer import eid


def project(db):
    # Availability needs a route, the game's own lists or an existing material mapping.
    db.execute("""INSERT INTO component SELECT id,kind,NULL,NULL,'player_directory' FROM entity e
                  WHERE kind IN ('spell','relic') OR kind='creature' AND EXISTS(SELECT 1 FROM route r WHERE r.entity_id=e.id
                  OR r.entity_id IN (SELECT src FROM edge WHERE dst=e.id AND rel='unlocks_creature'))""")
    db.execute("""INSERT INTO component SELECT DISTINCT e.id,e.kind,NULL,NULL,'game238' FROM entity e
                  JOIN game_entity g ON g.entity_id=e.id WHERE e.kind IN ('specialization','perk')""")
    db.execute("""INSERT OR IGNORE INTO component SELECT e.id,e.kind,NULL,NULL,'explicit_material' FROM entity e
                  WHERE e.kind='material' AND EXISTS(SELECT 1 FROM edge g WHERE g.src=e.id AND g.rel='grants_trait')""")
    db.execute("""INSERT OR IGNORE INTO component SELECT e.id,e.kind,NULL,NULL,'player_component_mapping' FROM entity e
                  WHERE e.kind IN ('trait','enchantment') AND EXISTS(
                  SELECT 1 FROM edge g LEFT JOIN component c ON c.id=g.src WHERE g.dst=e.id
                  AND (g.rel IN ('innate_trait','grants_trait') AND c.id IS NOT NULL OR g.rel='adds_property'))""")
    # Only a family some creature belongs to classifies a trait as that race.
    for rel, field, real in [
        ("listed_class", "class", ""),
        ("has_class", "class", ""),
        (
            "listed_family",
            "race",
            "AND EXISTS(SELECT 1 FROM edge b WHERE b.dst=n.id AND b.rel='belongs_to')",
        ),
        ("belongs_to", "race", ""),
    ]:
        db.execute(
            f"""UPDATE component SET {field}=COALESCE({field},(SELECT n.name FROM edge g JOIN entity n ON n.id=g.dst
                       WHERE g.src=component.id AND g.rel=? AND n.kind=? {real} LIMIT 1))""",
            (rel, "class" if field == "class" else "race"),
        )
    db.execute("""UPDATE component SET class=(SELECT json_extract(attrs,'$.class') FROM entity e
                  WHERE e.id=component.id) WHERE kind='spell'""")
    for item, shop, req, row in db.execute(
        "SELECT entity_id,location,requirements,row_id FROM route WHERE method='purchase'"
    ).fetchall():
        req = json.loads(req)
        delivery = {
            "Mana": "summon_unlock",
            "Inscription": "craft_unlock",
            "Heart": "project_material",
        }.get(req.get("item_type"), "item")
        # Stable identity is shop, output and delivery.
        key = eid("shop_offer", shop + "|" + item + "|" + delivery)
        cost = {
            k: req[k] for k in ("cost", "currency", "reported_cost", "price_evidence") if k in req
        }
        conditions = {k: v for k, v in req.items() if k not in cost}
        db.execute(
            "INSERT OR IGNORE INTO shop_offer VALUES(?,?,?,?,1,?,?,?)",
            (key, shop, item, delivery, json.dumps(cost), json.dumps(conditions), row),
        )
