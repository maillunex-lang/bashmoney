import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server.catalog import Catalog, Product, Recipe, Ingredient, EnterpriseType, EquipmentType
from server.economy import (EconomyError, ProductionRequest, ProductionState,
                            execute_production, start_next_period)
MAX = 2**63 - 1

def catalog():
    return Catalog(1, (Product("grain", "Зерно", "g"), Product("flour", "Мука", "g"),
                       Product("bread", "Хлеб", "pcs"), Product("water", "Вода", "l")),
                   (EnterpriseType("mill", "Мельница"),),
                   (EquipmentType("stones", "Жернова"),),
                   (Recipe("grind", "mill", (Ingredient("grain", 3),), (Ingredient("flour", 2),), "stones"),
                    Recipe("bake", "mill", (Ingredient("flour", 2),), (Ingredient("bread", 1),)),
                    Recipe("multi", "mill", (Ingredient("grain", 2),),
                           (Ingredient("flour", 3), Ingredient("water", 1))),
                    Recipe("extract", "mill", (), (Ingredient("grain", 5),)),
                    Recipe("recycle", "mill", (Ingredient("grain", 2),), (Ingredient("grain", 1),))))

def req(op="a", batches=5, capacity=5, recipe="grind", period="p1", version=1):
    return ProductionRequest(period, op, recipe, version, batches, capacity)

def state(stock=None, pending=None, completed=None):
    return ProductionState(stock if stock is not None else {"grain": 15},
                           pending if pending is not None else {}, completed if completed is not None else {})

def run(request=None, snapshot=None, space=None):
    return execute_production(catalog(), request or req(), snapshot or state(),
                              {"flour": 100} if space is None else space)

class ProductionTests(unittest.TestCase):
    def assert_error(self, code, callback):
        with self.assertRaises(EconomyError) as ctx:
            callback()
        self.assertEqual(ctx.exception.code, code)

    def test_full_batch(self):
        after, result = run()
        self.assertEqual(result.batches, 5)
        self.assertEqual(after.stock["grain"], 0)
        self.assertEqual(after.pending["flour"], 10)

    def test_no_input(self):
        after, result = run(snapshot=state({}))
        self.assertEqual(result.batches, 0)
        self.assertEqual(after.pending["flour"], 0)
        self.assertIn("INPUT_SHORTAGE_OR_LIMIT", result.reasons)

    def test_exact_boundary(self):
        self.assertEqual(run(snapshot=state({"grain": 3}))[1].batches, 1)

    def test_one_below_boundary(self):
        self.assertEqual(run(snapshot=state({"grain": 2}))[1].batches, 0)

    def test_partial_input(self):
        self.assertEqual(run(snapshot=state({"grain": 10}))[1].batches, 3)

    def test_capacity_limits(self):
        result = run(request=req(capacity=2))[1]
        self.assertEqual(result.batches, 2)
        self.assertIn("CAPACITY_LIMIT", result.reasons)

    def test_zero_capacity(self):
        self.assertEqual(run(request=req(capacity=0))[1].batches, 0)

    def test_zero_request(self):
        self.assertEqual(run(request=req(batches=0))[1].batches, 0)

    def test_space_limits(self):
        result = run(space={"flour": 5})[1]
        self.assertEqual(result.batches, 2)
        self.assertIn("WAREHOUSE_LIMIT", result.reasons)

    def test_no_space(self):
        self.assertEqual(run(space={})[1].batches, 0)

    def test_partial_space_does_not_consume(self):
        after, result = run(space={"flour": 3})
        self.assertEqual(result.batches, 1)
        self.assertEqual(after.stock["grain"], 12)

    def test_multiple_output_space(self):
        after, result = run(request=req(recipe="multi"), space={"flour": 20, "water": 2})
        self.assertEqual(result.batches, 2)
        self.assertEqual(after.pending["flour"], 6)
        self.assertEqual(after.pending["water"], 2)

    def test_pending_overflow_limits(self):
        after, result = run(snapshot=state({"grain": 15}, {"flour": MAX-1}), space={"flour": 10})
        self.assertEqual(result.batches, 0)
        self.assertEqual(after.pending["flour"], MAX-1)

    def test_max_integer(self):
        after, result = run(snapshot=state({"grain": MAX}), request=req(batches=MAX,capacity=MAX),
                            space={"flour": MAX})
        self.assertEqual(result.batches, MAX // 3)
        self.assertLessEqual(after.pending["flour"], MAX)

    def test_unchanged_input_snapshot(self):
        original = state({"grain": 15}, {"flour": 1})
        after, _ = run(snapshot=original)
        self.assertEqual(original.stock, {"grain": 15})
        self.assertEqual(original.pending, {"flour": 1})
        self.assertNotEqual(after.stock, original.stock)

    def test_retry_is_exactly_once(self):
        updated, original = run()
        repeated, result = run(snapshot=updated)
        self.assertIs(repeated, updated)
        self.assertIs(result, original)

    def test_retry_conflict(self):
        updated, _ = run()
        self.assert_error("IDEMPOTENCY_CONFLICT",
                          lambda: run(request=req(batches=4), snapshot=updated))

    def test_different_op_applies_remaining_stock(self):
        one, _ = run(request=req("a", batches=2))
        two, outcome = run(request=req("b", batches=5), snapshot=one)
        self.assertEqual(outcome.batches, 3)
        self.assertEqual(two.pending["flour"], 10)

    def test_different_period_same_op_is_new_key(self):
        one, _ = run(request=req("a", batches=2))
        two, result = run(request=req("a", period="p2", batches=2), snapshot=one)
        self.assertEqual(result.batches, 2)
        self.assertEqual(len(two.completed), 2)

    def test_pending_cannot_feed_bakery(self):
        one, _ = run()
        _, baked = run(request=req("b", recipe="bake"), snapshot=one,
                       space={"bread": 10})
        self.assertEqual(baked.batches, 0)

    def test_next_period_releases_output(self):
        one, _ = run()
        new = start_next_period(one)
        self.assertEqual(new.stock["flour"], 10)
        self.assertEqual(new.pending, {})
        self.assertEqual(len(new.completed), 1)

    def test_next_period_overflow(self):
        self.assert_error("STOCK_OVERFLOW",
                          lambda: start_next_period(state({"flour": MAX}, {"flour": 1})))

    def test_extract_no_inputs(self):
        after, result = run(request=req(recipe="extract", batches=2),
                            snapshot=state({}), space={"grain": 20})
        self.assertEqual(result.batches, 2)
        self.assertEqual(after.pending["grain"], 10)

    def test_recycle_no_same_tick_reuse(self):
        after, result = run(request=req(batches=10, recipe="recycle"),
                            snapshot=state({"grain": 3}), space={"grain": 100})
        self.assertEqual(result.batches, 1)
        self.assertEqual(after.stock["grain"], 1)
        self.assertEqual(after.pending["grain"], 1)

    def test_missing_recipe(self):
        self.assert_error("UNKNOWN_RECIPE", lambda: run(request=req(recipe="absent")))

    def test_version_mismatch(self):
        self.assert_error("CATALOG_VERSION_MISMATCH", lambda: run(request=req(version=2)))

    def test_unknown_stock_product(self):
        self.assert_error("UNKNOWN_PRODUCT", lambda: run(snapshot=state({"unknown": 2})))

    def test_unknown_space_product(self):
        self.assert_error("UNKNOWN_PRODUCT", lambda: run(space={"unknown": 10}))

    def test_negative_stock(self):
        self.assert_error("INVALID_AMOUNT", lambda: run(snapshot=state({"grain": -1})))

    def test_negative_pending(self):
        self.assert_error("INVALID_AMOUNT", lambda: run(snapshot=state(pending={"flour": -1})))

    def test_negative_space(self):
        self.assert_error("INVALID_AMOUNT", lambda: run(space={"flour": -1}))

    def test_float_space(self):
        self.assert_error("INVALID_AMOUNT", lambda: run(space={"flour": 1.0}))

    def test_bool_capacity(self):
        self.assert_error("INVALID_AMOUNT", lambda: run(request=req(capacity=True)))

    def test_oversized_request(self):
        self.assert_error("INVALID_AMOUNT", lambda: run(request=req(batches=MAX+1)))

    def test_invalid_op_id(self):
        self.assert_error("INVALID_IDENTIFIER", lambda: run(request=req(op=" ")))

    def test_reordering_stock_is_deterministic(self):
        a = run(snapshot=state({"grain": 15, "water": 7}))[1]
        b = run(snapshot=state({"water": 7, "grain": 15}))[1]
        self.assertEqual(a, b)

    def test_result_immutable(self):
        result = run()[1]
        with self.assertRaises(Exception):
            result.batches = 6

if __name__ == "__main__":
    unittest.main()
