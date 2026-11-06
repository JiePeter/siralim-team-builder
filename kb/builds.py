"""Configuration definitions: specializations, perks, artifact properties, relics and spells."""

import json


def catalog(db):
    result = {"specializations": [], "perks": [], "artifact_properties": []}
    for key, kind, name, body in db.execute(
        "SELECT id,kind,name,body FROM configuration ORDER BY name"
    ):
        meta = json.loads(body)
        text = db.execute("SELECT description FROM entity WHERE id=?", (key,)).fetchone()[0]
        item = {"id": key, "name": meta.get("short_name", name), "description": text, **meta}
        result[
            {
                "specialization": "specializations",
                "perk": "perks",
                "artifact_property": "artifact_properties",
            }[kind]
        ].append(item)
    result["specializations"] = [
        s
        for s in result["specializations"]
        if any(p["specialization"] == s["name"] for p in result["perks"])
    ]
    result["class_icons"] = {
        name: json.loads(attrs).get("image")
        for name, attrs in db.execute(
            "SELECT name,attrs FROM entity WHERE kind='class' ORDER BY name"
        )
    }
    result["relics"] = []
    for key, name in db.execute("SELECT id,name FROM entity WHERE kind='relic' ORDER BY name"):
        effects = []
        for text, attrs in db.execute(
            "SELECT e.description,e.attrs FROM edge g JOIN entity e ON e.id=g.dst WHERE g.src=? AND g.rel='rank_effect'",
            (key,),
        ):
            effects.append({"rank": int(json.loads(attrs)["rank"]), "description": text})
        result["relics"].append(
            {"id": key, "name": name, "effects": sorted(effects, key=lambda e: e["rank"])}
        )
    result["spells"] = [
        {"id": r[0], "name": r[1], "description": r[2]}
        for r in db.execute(
            "SELECT e.id,e.name,e.description FROM entity e JOIN component c ON c.id=e.id WHERE e.kind='spell' AND COALESCE(json_extract(e.attrs,'$.obtainable'),1)<>0 ORDER BY e.name"
        )
    ]
    return result
