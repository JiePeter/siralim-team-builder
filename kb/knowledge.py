"""Read model over the knowledge base that the data pack export is built from."""

from contextlib import contextmanager
import functools
import json
from pathlib import Path
import sqlite3
from .importer import DEFAULT_DB
from .builds import catalog as build_catalog
from .mechanics import Engine
from .discovery import Discovery
from .pages import PageTables, page


@contextmanager
def database(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def rows(db, sql, params=()):
    return [dict(row) for row in db.execute(sql, params)]


class Knowledge:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.compact_rules = {}

    def _with_db(self, factory):
        with database(self.path) as db:
            return factory(db)

    @functools.cache
    def discovery(self):
        cards = self.cards()
        return self._with_db(lambda db: Discovery(db, cards))

    def ability(self, key):
        from .cards import CHAIN_KINDS

        if self.cards().entities.get(key, {}).get("kind") in CHAIN_KINDS:
            return None
        return page(self, key)

    @functools.cache
    def cards(self):
        from .cards import Cards

        return self._with_db(Cards)

    @functools.cache
    def page_tables(self):
        return self._with_db(PageTables)

    def detail(self, key):
        entity = self.cards().entities.get(key)
        if not entity:
            return None
        component = self.page_tables().components.get(key)
        return {
            **entity,
            "selectable": bool(component) and entity["attrs"].get("obtainable", True),
            "classification": [component] if component else [],
        }

    def gem_properties(self):
        with database(self.path) as db:
            properties = rows(
                db,
                "SELECT DISTINCT e.id,e.name FROM entity e JOIN edge g ON g.dst=e.id AND g.rel='adds_property' ORDER BY e.name",
            )
            for prop in properties:
                attrs = db.execute("SELECT attrs FROM entity WHERE id=?", (prop["id"],)).fetchone()
                prop.update(json.loads(attrs[0]))
                prop["routes"] = self.cards().routes[prop["id"]]
            return properties

    @functools.cache
    def mechanics(self):
        return self._with_db(Engine)

    @functools.cache
    def build_catalog(self):
        result = dict(self._with_db(build_catalog))
        refs = self.cards().inline
        for group in ("perks", "artifact_properties", "spells"):
            enriched = []
            for item in result[group]:
                segments = refs.segments(item["id"], item["description"])
                enriched.append(
                    {
                        **item,
                        "segments": segments,
                        "description": "".join(p["text"] for p in segments),
                    }
                )
            result[group] = enriched
        result["relics"] = [
            {
                **relic,
                "effects": [
                    {
                        **effect,
                        "segments": refs.segments(
                            relic["id"], effect["description"], effect["rank"]
                        ),
                    }
                    for effect in relic["effects"]
                ],
            }
            for relic in result["relics"]
        ]
        return result

    @functools.cache
    def carried_traits(self):
        with database(self.path) as db:
            return dict(
                db.execute("SELECT src,dst FROM edge WHERE rel IN ('innate_trait','grants_trait')")
            )

    def synergy_owner(self, key):
        """Creatures and materials share the Synergies of the trait they carry."""
        return self.carried_traits().get(key, key)

    @functools.cache
    def synergy_object(self, key):
        cards = self.cards()
        fields = {"image": cards.entities.get(key, {}).get("attrs", {}).get("image")}
        cls = cards.classification.get(key, {}).get("class")
        return fields | ({"classification": [{"class": cls}]} if cls else {})

    def synergy_rule(self, key, rule):
        """One compact rule per engine rule, so that an export can recognize repeats by identity."""
        found = self.compact_rules.get(id(rule))
        if found is None:
            segments = self.cards().inline.segments(key, rule["text"], rule.get("rank"))
            found = self.compact_rules[id(rule)] = {**rule, "segments": segments}
        return found

    def connections(self, key, compact=False):
        key = self.synergy_owner(key)
        result = self.mechanics().connections(key)
        if not compact:
            return result
        items = [
            {
                **item,
                **self.synergy_object(item["id"]),
                "target_rule": self.synergy_rule(item["id"], item["target_rule"]),
            }
            for item in result["items"]
        ]
        return {**result, "items": items}
