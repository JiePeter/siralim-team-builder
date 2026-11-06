"""Runtime and canonical-Spell regression checks."""

import unittest
from kb.knowledge import Knowledge


class SynergyRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = Knowledge()

    def test_shop_spell_presentation_preserves_original_purchase_record(self):
        god = self.kb.ability("god:28")
        offer = next(
            o for o in god["god_contents"]["shops"][0]["offers"] if o.get("via") == "Inscription"
        )
        self.assertEqual(offer["item"]["kind"], "spell")
        self.assertTrue(offer["cost"])
        self.assertTrue(self.kb.ability(offer["item"]["id"]))

    def test_source_products_keep_only_routes_for_the_current_source(self):
        with __import__("sqlite3").connect(self.kb.path) as db:
            key = db.execute(
                "SELECT r.location FROM route r JOIN entity e ON e.id=r.location WHERE e.kind='acquisition_source' LIMIT 1"
            ).fetchone()[0]
        page = self.kb.ability(key)
        for product in page["products"]:
            self.assertTrue(all(route["location"] == key for route in product["routes"]))


if __name__ == "__main__":
    unittest.main()
