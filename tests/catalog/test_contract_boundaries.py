"""Boundary and negative contract tests for the T1 pure catalog engine."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server.catalog import (
    Catalog, CatalogError, EnterpriseType, EquipmentType, Ingredient,
    Product, Recipe, plan_production, validate_catalog,
)

MAX = 2**63 - 1


def sample():
    return Catalog(
        1,
        (Product("grain", "Зерно", "g"), Product("flour", "Мука", "g")),
        (EnterpriseType("mill", "Мельница"),),
        (EquipmentType("stones", "Жернова"),),
        (Recipe("grind", "mill", (Ingredient("grain", 3),),
                (Ingredient("flour", 2),), "stones"),),
    )


class ContractTests(unittest.TestCase):
    def assert_code(self, code, action):
        with self.assertRaises(CatalogError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_invalid_catalog_version_zero(self):
        c = sample()
        self.assert_code("INVALID_QUANTITY", lambda: validate_catalog(
            Catalog(0, c.products, c.enterprises, c.equipment, c.recipes)))

    def test_invalid_catalog_version_boolean(self):
        c = sample()
        self.assert_code("INVALID_QUANTITY", lambda: validate_catalog(
            Catalog(True, c.products, c.enterprises, c.equipment, c.recipes)))

    def test_invalid_product_id(self):
        c = sample()
        self.assert_code("INVALID_ID", lambda: validate_catalog(
            Catalog(1, (Product("Bad ID", "Зерно", "g"),), c.enterprises, c.equipment, ())))

    def test_empty_product_name(self):
        c = sample()
        self.assert_code("EMPTY_NAME", lambda: validate_catalog(
            Catalog(1, (Product("grain", " ", "g"),), c.enterprises, c.equipment, ())))

    def test_empty_product_unit(self):
        c = sample()
        self.assert_code("EMPTY_UNIT", lambda: validate_catalog(
            Catalog(1, (Product("grain", "Зерно", ""),), c.enterprises, c.equipment, ())))

    def test_invalid_tradable_flag(self):
        c = sample()
        self.assert_code("INVALID_FLAG", lambda: validate_catalog(
            Catalog(1, (Product("grain", "Зерно", "g", 1),), c.enterprises, c.equipment, ())))

    def test_unknown_equipment(self):
        c = sample()
        r = Recipe("grind", "mill", (Ingredient("grain", 3),),
                   (Ingredient("flour", 2),), "missing")
        self.assert_code("UNKNOWN_EQUIPMENT", lambda: validate_catalog(
            Catalog(1, c.products, c.enterprises, c.equipment, (r,))))

    def test_zero_ingredient(self):
        c = sample()
        r = Recipe("grind", "mill", (Ingredient("grain", 0),),
                   (Ingredient("flour", 2),))
        self.assert_code("INVALID_QUANTITY", lambda: validate_catalog(
            Catalog(1, c.products, c.enterprises, c.equipment, (r,))))

    def test_boolean_ingredient(self):
        c = sample()
        r = Recipe("grind", "mill", (Ingredient("grain", True),),
                   (Ingredient("flour", 2),))
        self.assert_code("INVALID_QUANTITY", lambda: validate_catalog(
            Catalog(1, c.products, c.enterprises, c.equipment, (r,))))

    def test_duplicate_output(self):
        c = sample()
        r = Recipe("grind", "mill", (), (Ingredient("flour", 1), Ingredient("flour", 2)))
        self.assert_code("DUPLICATE_INGREDIENT", lambda: validate_catalog(
            Catalog(1, c.products, c.enterprises, c.equipment, (r,))))

    def test_negative_requested_batches(self):
        self.assert_code("INVALID_QUANTITY", lambda: plan_production(sample(), "grind", {}, -1))

    def test_requested_batches_over_max(self):
        self.assert_code("INVALID_QUANTITY", lambda: plan_production(sample(), "grind", {}, MAX + 1))

    def test_stock_float_rejected(self):
        self.assert_code("INVALID_QUANTITY", lambda: plan_production(sample(), "grind", {"grain": 3.0}, 1))

    def test_stock_over_max_rejected(self):
        self.assert_code("INVALID_QUANTITY", lambda: plan_production(sample(), "grind", {"grain": MAX + 1}, 1))

    def test_exact_batch_boundary(self):
        p = plan_production(sample(), "grind", {"grain": 3}, 1)
        self.assertEqual(p.batches, 1)
        self.assertEqual(p.remaining, (Ingredient("grain", 0),))

    def test_one_below_batch_boundary(self):
        p = plan_production(sample(), "grind", {"grain": 2}, 1)
        self.assertEqual(p.batches, 0)
        self.assertEqual(p.remaining, (Ingredient("grain", 2),))

    def test_requested_batch_cap(self):
        p = plan_production(sample(), "grind", {"grain": 100}, 2)
        self.assertEqual(p.batches, 2)
        self.assertEqual(p.produced, (Ingredient("flour", 4),))

    def test_stock_order_does_not_affect_result(self):
        a = plan_production(sample(), "grind", {"grain": 9, "flour": 7}, 10)
        b = plan_production(sample(), "grind", {"flour": 7, "grain": 9}, 10)
        self.assertEqual(a, b)

    def test_no_mutation_even_with_zero_batches(self):
        stock = {"grain": 2}
        plan_production(sample(), "grind", stock, 100)
        self.assertEqual(stock, {"grain": 2})

    def test_output_overflow_limits_batches(self):
        c = sample()
        r = Recipe("huge", "mill", (), (Ingredient("flour", MAX),))
        c = Catalog(1, c.products, c.enterprises, c.equipment, (r,))
        p = plan_production(c, "huge", {}, MAX)
        self.assertEqual(p.batches, 1)
        self.assertEqual(p.produced, (Ingredient("flour", MAX),))


if __name__ == "__main__":
    unittest.main()
