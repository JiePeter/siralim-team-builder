"""Concrete reference positions and conservative resolution, not a smoke suite."""

import unittest
from kb.knowledge import Knowledge


class InlineReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = Knowledge()
        cls.cards = cls.kb.cards()

    def card(self, kind, name):
        return self.cards.card(self.cards.by_kind_name[kind, name.casefold()])

    def refs(self, segments):
        return [p for p in segments if p.get("id")]

    def test_5740_ng_spells_are_on_their_own_ranks(self):
        card = self.card("relic", "5740-NG, Impenetrable Plate of 4080")
        ranks = {e["rank"]: self.refs(e["segments"]) for e in card["effects"]}
        self.assertEqual([p["text"] for p in ranks[60]], ["Stone Skin"])
        self.assertEqual([p["text"] for p in ranks[80]], ["Iron Skin"])
        self.assertFalse(ranks[50])
        self.assertFalse(self.cards.sections(card["id"]))

    def test_triumvir_conditions_and_spells_remain_local(self):
        card = self.card("relic", "Triumvir, Arcane Sceptre of Zonte")
        rank100 = next(e for e in card["effects"] if e["rank"] == 100)
        self.assertEqual(
            [(p["text"], p["kind"]) for p in self.refs(rank100["segments"])],
            [("Arcane", "condition"), ("Lightning Storm", "spell")],
        )
        self.assertNotIn("Snowstorm", rank100["description"])

    def test_primary_namespace_resolves_a_same_name_in_its_actual_position(self):
        refs = self.cards.inline
        key = "test:ambiguous-name"
        refs.raw[key, None] = "{RACE_Concoction} creatures cast [icons,1976]Concoction."
        segments = refs.segments(key, "Concoction creatures cast Concoction.")
        self.assertEqual(segments[0]["text"], "Concoction creatures cast ")
        self.assertEqual(len(self.refs(segments)), 1)
        self.assertEqual(self.refs(segments)[0]["kind"], "spell")

    def test_named_cast_cleanup_preserves_action_and_spacing(self):
        card = self.card("trait", "Storm of the Century")
        self.assertEqual(
            card["description"], "After this creature attacks, it casts Lightning Storm."
        )
        self.assertEqual(self.refs(card["segments"])[0]["text"], "Lightning Storm")

    def test_exact_embedded_spell_copy_is_removed_but_perk_conditions_remain(self):
        card = self.card("perk", "Acclimatization · Grovetender")
        self.assertIn("once per turn", card["description"])
        self.assertNotIn("Nutrition:", card["description"])
        self.assertTrue(self.refs(card["segments"]))
        different = card["description"] + "\n\nNutrition: Different effect that must remain."
        self.assertIn(
            "Different effect",
            "".join(p["text"] for p in self.cards.inline.segments(card["id"], different)),
        )

    def test_finite_spell_group_preserves_equipped_condition(self):
        card = self.card("trait", "Gathering Storm")
        self.assertEqual(
            [p["text"] for p in self.refs(card["segments"])],
            ["Snowstorm", "Firestorm", "Sandstorm"],
        )
        self.assertIn("if they're equipped", card["description"])

    def test_missing_definitions_and_variable_selectors_are_not_fabricated(self):
        card = self.card("trait", "Out For Blood")
        self.assertIn("Kill Streak", card["description"])
        self.assertFalse(self.refs(card["segments"]))
        self.assertFalse(
            self.refs(self.cards.inline.segments("test:random", "It casts a random spell."))
        )

    def test_named_spell_is_not_a_recommendation_but_internal_call_is_retained(self):
        card = self.card("relic", "5740-NG, Impenetrable Plate of 4080")
        engine = self.kb.mechanics()
        self.assertTrue(any(e["relation"] == "Named spell" for e in engine.candidates(card["id"])))
        result = engine.connections(card["id"])
        self.assertNotIn("Named spell", result["categories"])
        self.assertFalse(any(e["relation"] == "Named spell" for e in result["items"]))

    def test_non_obtainable_definitions_are_available_for_preview(self):
        key = next(
            k
            for k, e in self.cards.entities.items()
            if e["kind"] == "spell" and e["attrs"].get("obtainable") is False
        )
        card = self.cards.card(key)
        self.assertTrue(card["description"])
        self.assertFalse(card["attrs"]["obtainable"])


if __name__ == "__main__":
    unittest.main()
