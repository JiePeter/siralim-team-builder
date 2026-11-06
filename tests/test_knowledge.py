from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from kb.importer import build, eid, DEFAULT_RAW
from kb.knowledge import Knowledge


class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name)
        cls.db = cls.path / "knowledge.sqlite3"
        cls.report = build(DEFAULT_RAW, cls.db)
        cls.kb = Knowledge(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def named(self, kind, name):
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute(
                """SELECT id FROM entity WHERE kind=? AND name=?
                   UNION SELECT e.id FROM entity_alias a JOIN entity e ON e.id=a.entity_id
                   WHERE e.kind=? AND a.alias=?""",
                (kind, name, kind, name),
            ).fetchone()[0]

    def test_current_game_snapshot_and_preserved_source_detail(self):
        catalog = self.kb.build_catalog()
        self.assertEqual(len(catalog["specializations"]), 43)
        self.assertEqual(len(catalog["perks"]), 661)
        with closing(sqlite3.connect(self.db)) as db:
            version = db.execute("SELECT value FROM meta WHERE key='game_version'").fetchone()[0]
        self.assertEqual(version, "2.0.38")
        apis = self.kb.ability(self.named("creature", "Apis Adolescent"))
        route = apis["routes"][0]
        self.assertEqual(route["requirements"]["cost"], 50000)
        self.assertEqual(route["requirements"]["currency"], "Crystal")
        self.assertEqual(route["requirements"]["rank"], 10)
        self.assertTrue(apis["attrs"]["image"].startswith("/assets/siralim/"))
        phase = self.kb.ability(self.named("creature", "Phase Knight"))
        origins = phase["routes"]
        self.assertEqual(len(origins), 1)
        self.assertEqual(origins[0]["requirements"]["source_realm_depth"], "19")
        self.assertEqual(origins[0]["requirements"]["interaction"], "Portals")
        with closing(sqlite3.connect(self.db)) as db:
            self.assertGreaterEqual(
                db.execute(
                    "SELECT count(*) FROM mechanic_record m JOIN entity e ON e.id=m.entity_id WHERE e.kind='perk'"
                ).fetchone()[0],
                613,
            )

    def test_reference_destinations_are_searchable_but_not_build_components(self):
        data = self.kb.ability(self.kb.cards().by_kind_name["realm", "titan's wound"])
        self.assertFalse(data["selectable"])
        self.assertEqual(len(data["creatures"]), 48)
        self.assertEqual([g["name"] for g in data["related"]], ["Mortem"])
        self.assertEqual(
            {r["method"] for c in data["creatures"] for r in c["routes"]},
            {"realm_encounter", "realm_interaction"},
        )
        god = self.kb.ability(data["related"][0]["id"])
        self.assertTrue(god["attrs"]["image"].endswith("/god/Mortem.png"))
        self.assertEqual(
            god["god_contents"]["relics"][0]["name"],
            "Bloodseeker, Hungering Dagger of Mortem",
        )
        self.assertFalse(god["selectable"])

    def test_creature_material_and_family_keep_their_identities(self):
        creature = self.kb.ability(self.named("creature", "Lunar Hemomancer"))
        self.assertEqual(creature["name"], "Lunar Hemomancer")
        self.assertEqual(creature["traits"][0]["name"], "Abation")
        self.assertEqual(len(creature["family"]), 6)
        self.assertEqual(len(creature["materials"]), 1)
        material = self.kb.ability(creature["materials"][0]["id"])
        self.assertEqual(material["kind"], "material")
        self.assertEqual(material["creatures"][0]["id"], creature["id"])
        self.assertTrue(creature["attrs"]["class_icon"])
        self.assertTrue(creature["attrs"]["race_icon"])
        self.assertTrue(all(c["kind"] == "creature" for c in creature["family"]))

    def test_rank_and_perk_matches_keep_reference_locations(self):
        connections = self.kb.connections(self.named("trait", "Abnegation"))
        relics = [i for i in connections["items"] if i["kind"] == "relic"]
        self.assertTrue(relics)
        self.assertTrue(
            all(i["target_rule"].get("rank") and i["target_rule"].get("reference") for i in relics)
        )
        perk = self.kb.ability("perk:590")
        self.assertEqual(perk["parent"]["id"], "spec:39")
        relic = self.kb.ability(relics[0]["id"])
        self.assertEqual(len(relic["effects"]), 10)

    def test_referential_integrity(self):
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertFalse(
                db.execute(
                    "SELECT 1 FROM edge WHERE src NOT IN (SELECT id FROM entity) OR dst NOT IN (SELECT id FROM entity)"
                ).fetchone()
            )
            self.assertFalse(
                db.execute(
                    "SELECT 1 FROM route WHERE entity_id NOT IN (SELECT id FROM entity)"
                ).fetchone()
            )

    def test_search_consolidates_ability(self):
        self.assertEqual(
            self.kb.ability(self.named("creature", "Phase Knight"))["traits"][0]["id"],
            self.kb.ability(self.named("material", "Knight Prism"))["traits"][0]["id"],
        )
        ability = self.kb.ability(self.named("material", "Knight Prism"))
        self.assertEqual(ability["kind"], "material")
        self.assertTrue(ability["traits"])
        self.assertTrue(ability["creatures"])
        pandora = self.kb.ability(self.named("trait", "Pandora's Box"))
        self.assertTrue(any(o["kind"] == "creature" for o in pandora["options"]))
        self.assertFalse(any(o["kind"] == "material" for o in pandora["options"]))

    def test_creature_options_include_stats_classification_and_own_sources(self):
        ability = self.kb.ability(self.named("creature", "Apis Adolescent"))
        creature = ability
        self.assertEqual(creature["kind"], "creature")
        self.assertTrue(creature["family"])
        self.assertTrue(creature["traits"])
        self.assertTrue(creature["materials"])
        self.assertEqual(creature["attrs"]["stats"]["health"], "26")
        self.assertEqual(creature["classification"][0]["class"], "Life")
        self.assertEqual(creature["classification"][0]["race"], "Apis")
        self.assertTrue(creature["routes"])
        self.assertTrue(any(r["location_name"] == "Nature Guild" for r in creature["routes"]))

    def test_specialization_is_selectable(self):
        self.assertTrue(self.kb.ability("spec:17")["selectable"])

    def test_spell_pairing_is_available_from_listener_trait(self):
        links = self.kb.connections(self.named("trait", "Abnegation"))
        self.assertTrue(
            any(
                i["kind"] == "spell" and i["name"] == "Abundance" and i["direction"] == "incoming"
                for i in links["items"]
            )
        )

    def test_structured_links_cover_non_attack_effects(self):
        links = self.kb.connections("perk:248")
        self.assertTrue(any(i["relation"] == "Status condition" for i in links["items"]))

    def test_component_boundary(self):
        self.assertTrue(self.kb.detail(self.named("trait", "Pandora's Box"))["selectable"])
        phase = self.kb.detail(self.named("creature", "Phase Knight"))
        self.assertTrue(phase["classification"][0]["race"])

    def test_shop_aggregate(self):
        with closing(sqlite3.connect(self.db)) as db:
            self.assertGreater(db.execute("SELECT count(*) FROM shop_offer").fetchone()[0], 443)
            self.assertFalse(
                db.execute("SELECT 1 FROM shop_offer WHERE id LIKE '%God Shops%'").fetchone()
            )
            self.assertEqual(
                {r[0] for r in db.execute("SELECT DISTINCT delivery FROM shop_offer")},
                {"item", "summon_unlock", "craft_unlock", "project_material"},
            )

    def test_material_and_creature_favor_separate(self):
        creature = self.kb.ability(self.named("creature", "Alcazar"))
        material = self.kb.ability(self.named("material", "Alcazar Brick"))
        self.assertTrue(
            any(str(r["requirements"].get("favor_rank")) == "8" for r in creature["routes"])
        )
        self.assertTrue(
            any(
                str(r["requirements"].get("favor_rank")) == "10"
                for r in material["routes"]
                if r["method"] == "purchase"
            )
        )

    def test_phase_knight_portal_and_no_guaranteed_drop(self):
        detail = self.kb.ability(self.named("creature", "Phase Knight"))
        route = next(r for r in detail["routes"] if r["method"] == "realm_interaction")
        self.assertEqual(route["requirements"]["interaction"], "Portals")

    def test_unnamed_boss_continuation_is_not_given_a_name(self):
        self.assertIsNone(self.kb.detail(eid("boss_effect", "Cornered · Nether Tier 1")))

    def test_god_shop_sheet_price_wins(self):
        jade = [
            r
            for p in self.kb.gem_properties()
            for r in p["routes"]
            if r.get("via") == "Jade" and r["method"] == "purchase"
        ]
        self.assertTrue(jade)
        self.assertTrue(all(r["requirements"]["cost"] == 10 for r in jade))
        material = self.kb.ability(self.named("material", "Alcazar Brick"))
        self.assertEqual(
            next(r for r in material["routes"] if r["method"] == "purchase")["requirements"][
                "cost"
            ],
            10,
        )

    def test_connections_explain_binding(self):
        result = self.kb.connections(self.named("trait", "Reinvigoration"))
        self.assertGreater(result["total"], 0)
        self.assertTrue(
            all(r["constraints"] and r["status"] == "candidate" for r in result["items"])
        )
        self.assertTrue(
            all(r["kind"] not in ("boss_effect", "boss_trait") for r in result["items"])
        )


if __name__ == "__main__":
    unittest.main()
