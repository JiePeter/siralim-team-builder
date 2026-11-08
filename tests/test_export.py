import json
import tempfile
import unittest
from pathlib import Path
from kb.export import (
    FILE_BUDGET,
    SYNERGY_ITEM_FIELDS,
    SYNERGY_RULE_FIELDS,
    BudgetError,
    base_synergies,
    check_budget,
    export,
    joined,
    object_path,
)
from kb.facts import render
from kb.knowledge import Knowledge

TRAIT = "trait:803"
CARRIER = "creature:561"
UPPERCASE = "artifact_property:48"


class ExportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.kb = Knowledge()
        cls.out = Path(cls.temp.name) / "data"
        cls.sizes = export(cls.out, cls.kb, objects=[TRAIT, UPPERCASE, CARRIER], owners=[TRAIT])
        cls.manifest = json.loads((cls.out / "manifest.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def load(self, relative):
        return json.loads((self.out / relative).read_text(encoding="utf-8"))

    def test_pages_and_manifest_point_at_exactly_the_written_files(self):
        pages = {key: self.load(object_path(key)) for key in (TRAIT, UPPERCASE, CARRIER)}
        listed = {object_path(key) for key in pages}
        listed |= {page["synergies"] for page in pages.values() if "synergies" in page}
        listed |= set(self.manifest["cards"].values())
        written = {p.relative_to(self.out).as_posix() for p in self.out.rglob("*.json")}
        self.assertEqual(set(self.sizes), written)
        self.assertEqual({p for p in written if "/" in p}, listed)
        self.assertEqual(self.manifest["objects"], {})
        self.assertRegex(self.manifest["pack"], r"^[0-9a-f]{12}$")
        for path in written:
            self.assertRegex(path, r"^[A-Za-z0-9_./-]+$")
        self.assertEqual(pages[UPPERCASE], self.kb.ability(UPPERCASE))

    def test_synergies_expand_to_the_card_fields_of_the_api_result(self):
        path = self.load(object_path(TRAIT))["synergies"]
        self.assertEqual(self.load(object_path(CARRIER))["synergies"], path)
        shared = self.load("synergy-rules.json")
        compact = self.load(path)
        expected = self.kb.connections(CARRIER, compact=True)
        self.assertEqual(len(compact["items"]), len(expected["items"]))

        def facts(ids):
            return [shared["facts"][i] for i in ids]

        def stored(tokens):
            return [[t[0], t[1], render(t)] for t in tokens]

        def expand(row):
            key, point, strength, rule, constraints, requirements, side, rank, perk = (
                row + [None] * 5
            )[:9]
            relation, event, _degree = shared["points"][point]
            optional = {"source_rank": rank, "source_perk": perk and shared["perks"][perk]}
            return {
                "id": shared["objects"][key]["id"],
                "relation": shared["relations"][relation],
                "event_label": event,
                "strength": shared["strengths"][strength],
                "shared_constraints": constraints or [],
                "target_rule": rule,
                "witness": {
                    k: v
                    for k, v in (("requirements", requirements), ("requires_target_side", side))
                    if v
                },
                **{k: v for k, v in optional.items() if v},
            }

        # Only TRAIT's file is written, so each of its points has one owner.
        self.assertEqual({degree for *_, degree in shared["points"].values()}, {1})
        for row, original in zip(compact["items"], expected["items"]):
            item = expand(row)
            self.assertEqual(item["event_label"], original["event_label"])
            rule = shared["rules"][item["target_rule"]]
            target = original["target_rule"]
            self.assertEqual(rule.get("text", joined(rule["segments"])), target["text"])
            self.assertEqual(facts(rule["conditions"]), stored(target["conditions"]))
            self.assertEqual(
                {k: v for k, v in rule.items() if k not in ("text", "conditions")},
                {
                    k: target[k]
                    for k in SYNERGY_RULE_FIELDS
                    if k in target and k not in ("text", "conditions")
                },
            )
            self.assertEqual(
                facts(item["shared_constraints"]), stored(original["shared_constraints"])
            )
            self.assertEqual(
                {
                    k: item[k]
                    for k in SYNERGY_ITEM_FIELDS
                    if k in item and k != "shared_constraints"
                },
                {
                    k: original[k]
                    for k in SYNERGY_ITEM_FIELDS
                    if k in original and k != "shared_constraints"
                },
            )
            witness = item.get("witness", {})
            self.assertEqual(
                facts(witness.get("requirements", [])),
                stored(original["witness"].get("requirements", [])),
            )
            self.assertEqual(
                witness.get("requires_target_side"),
                original["witness"].get("requires_target_side") or None,
            )
            self.assertEqual(shared["objects"][row[0]]["name"], original["name"])

    def test_base_synergies_join_its_perks_without_suggesting_them(self):
        beam = {"id": "trait:beam", "relation": "Event chain"}
        perks = {
            "perk:a": {"items": [beam, {"id": "perk:b", "relation": "Event chain"}]},
            "perk:b": {"items": [beam, {"id": "spell:x", "relation": "Scope overlap"}]},
        }
        result = base_synergies(perks)
        self.assertEqual(
            [(i["id"], i["source_perk"]) for i in result["items"]],
            [("trait:beam", "perk:a"), ("trait:beam", "perk:b"), ("spell:x", "perk:b")],
        )

    def test_catalog_carries_artifact_formulas_and_no_nether_stone(self):
        catalog = self.load("catalog.json")
        self.assertNotIn("nether_traits", catalog)
        formulas = {p["name"]: p["formula"] for p in catalog["artifact_properties"]}
        self.assertEqual(formulas["Attack Damage"], {"base": 10, "mult": 1.5, "unit": "%"})
        self.assertEqual(formulas["Spell Gem Slots"], {"base": 1, "div": 25, "unit": "flat"})
        self.assertEqual(catalog["artifact_primary"]["Sword"]["stat"], "Attack")

    def test_potency_sources_are_the_potency_based_on_variants(self):
        self.assertEqual(self.load("team-rules.json")["potency_sources"], [5, 19, 21, 22])

    def test_anointment_capacity_comes_from_the_perks_that_raise_it(self):
        anointments = self.load("catalog.json")["anointments"]
        self.assertEqual(
            anointments,
            {
                "base": 5,
                "perks": {
                    "perk:464": {"count": 3, "all_ascended": 5},
                    "perk:449": {"count": 10},
                },
            },
        )

    def test_budget_rejects_large_file_and_total(self):
        check_budget({"a.json": FILE_BUDGET})
        with self.assertRaisesRegex(BudgetError, "big.json"):
            check_budget({"big.json": FILE_BUDGET + 1})
        with self.assertRaisesRegex(BudgetError, "total"):
            check_budget({f"{i}.json": FILE_BUDGET for i in range(101)})


if __name__ == "__main__":
    unittest.main()
