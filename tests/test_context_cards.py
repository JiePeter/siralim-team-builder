"""Reference content against the checked-in derived snapshot."""

import unittest
from kb.knowledge import Knowledge


class ContextCardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = Knowledge()
        cls.cards = cls.kb.cards()

    def get(self, kind, name):
        return self.kb.ability(self.cards.by_kind_name[kind, name.casefold()])

    def test_realm_rows_include_creature_effect_and_identity(self):
        page = self.get("realm", "Titan's Wound")
        self.assertEqual(len(page["creatures"]), 48)
        for item in page["creatures"]:
            self.assertTrue(item["effects"])
            self.assertTrue(item["attrs"]["class_id"])
            self.assertTrue(item["attrs"]["race_id"])
            self.assertTrue(all(e["description"] for e in item["effects"]))

    def test_chain_materials_are_a_step_in_the_routes_of_what_they_serve(self):
        for kind, name, target, via in [
            ("heart", "Heart of Aja Birku", "Aja Birku", "Heart of Aja Birku"),
            ("enchantment_material", "Agate", None, "Agate"),
            ("inscription", "Absolute Corruption", "Absolute Corruption", "Inscription"),
        ]:
            material = self.cards.by_kind_name[kind, name.casefold()]
            self.assertIsNone(self.kb.ability(material))
            page = self.kb.ability(self.cards.chain[material])
            if target:
                self.assertEqual(page["name"], target)
            routes = [r for r in page["routes"] if r.get("via") == via]
            self.assertTrue(routes and all(r["location"] for r in routes))
            self.assertTrue(all("inscription" not in r["requirements"] for r in page["routes"]))
            self.assertNotIn(material, [i["id"] for s in page["sections"] for i in s["items"]])
        regular = self.get("material", "Red Amber")
        self.assertIn("Attack", regular["effects"][0]["description"])
        self.assertFalse(regular["traits"])

    def test_god_relic_contents_without_reverse_expansion(self):
        god = self.get("god", "Mortem")
        relic = god["god_contents"]["relics"][0]
        self.assertEqual(relic["name"], "Bloodseeker, Hungering Dagger of Mortem")
        self.assertEqual([e["rank"] for e in relic["effects"]], list(range(10, 101, 10)))
        self.assertNotIn("God", [s["title"] for s in self.kb.ability(relic["id"])["sections"]])
        shop = god["god_contents"]["shops"][0]
        self.assertIn(str(len(self.kb.ability(shop["id"])["offers"])) + " Items", shop["facts"])

    def test_god_page_has_direct_five_part_contents(self):
        god = self.get("god", "4080")
        content = god["god_contents"]
        self.assertEqual(content["realms"][0]["name"], "Forgotten Lab")
        self.assertEqual(content["relics"][0]["name"], "5740-NG, Impenetrable Plate of 4080")
        self.assertEqual(content["godspawn"][0]["name"], "8004")
        self.assertEqual(content["ultimate_spells"][0]["name"], "Heat Beam")
        self.assertTrue(content["shops"][0]["offers"])
        self.assertTrue(all(o["item"]["effects"] for o in content["shops"][0]["offers"]))
        self.assertEqual(god["sections"], [])
        relic = self.kb.ability(content["relics"][0]["id"])
        self.assertEqual(relic["sections"], [])
        self.assertEqual(
            {
                s["text"]
                for e in relic["effects"]
                for s in e["segments"]
                if s.get("kind") == "spell"
            },
            {"Iron Skin", "Stone Skin"},
        )

    def test_named_casts_are_reference_lists_not_fabricated_synergy(self):
        spell = self.get("spell", "Lightning Storm")
        users = next(s for s in spell["sections"] if s["title"] == "Cast by")["items"]
        self.assertTrue(any(i["name"] == "Storm of the Century" for i in users))
        trait = next(i for i in users if i["name"] == "Storm of the Century")
        self.assertIn(
            spell["id"], [s["id"] for s in self.kb.ability(trait["id"])["segments"] if s.get("id")]
        )
        self.assertTrue(all("sections" not in i for i in users))
        relic = next(i for i in users if i["kind"] == "relic")
        self.assertTrue(any(h["rank"] for h in relic["matched_rules"]))
        self.assertNotIn("matched_rules", self.cards.card(relic["id"]))

    def test_discovery_uses_core_effects_without_changing_identity(self):
        for name, kind in [
            ("Adolescent Egg", "material"),
            ("Lunar Hemomancer", "creature"),
        ]:
            card = self.cards.card(self.cards.by_kind_name[kind, name.casefold()])
            self.assertEqual(card["kind"], kind)
            self.assertTrue(card["effects"])

    def test_race_links_card_rewards_and_complete_family(self):
        race = self.get("race", "Hemomancer")
        self.assertEqual(
            len(next(s for s in race["sections"] if s["title"] == "Creatures")["items"]), 6
        )
        bonus = next(s for s in race["sections"] if s["title"] == "Card bonuses")["items"][0]
        self.assertEqual([e["label"] for e in bonus["effects"]], ["2 Cards", "4 Cards", "6 Cards"])

    def test_artifact_configuration_catalog_retains_effect_text(self):
        catalog = self.kb.build_catalog()
        self.assertTrue(next(s for s in catalog["spells"] if s["name"] == "Volcano")["description"])


if __name__ == "__main__":
    unittest.main()
