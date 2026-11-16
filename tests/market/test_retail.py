import unittest
from dataclasses import replace

from server.market import (MarketError, RetailOffer, PopulationDemand,
                           RetailRequest, RetailState, clear_retail)

MAX = 2**63 - 1


def offer(offer_id="a", company_id="firm_a", available=10, unit_price=3,
          city_id="ufa", product_id="bread"):
    return RetailOffer(offer_id, company_id, "store_" + offer_id,
                       city_id, product_id, unit_price, available)


def demand(cohort_id="residents", quantity=8, budget=30, preferred_offers=("a",),
           city_id="ufa", product_id="bread"):
    return PopulationDemand(cohort_id, city_id, product_id, quantity,
                            budget, preferred_offers)


def request(offers=None, demands=None):
    return RetailRequest("period_1", "sale_1", 1,
                         tuple(offers if offers is not None else (offer(),)),
                         tuple(demands if demands is not None else (demand(),)))


def run(req=None, state=None):
    return clear_retail(req if req is not None else request(),
                        state if state is not None else RetailState({}))


class MarketTests(unittest.TestCase):
    def assert_error(self, code, req=None, state=None):
        with self.assertRaises(MarketError) as ctx:
            run(req, state)
        self.assertEqual(ctx.exception.code, code)

    def test_normal_sale(self):
        _, result = run()
        self.assertEqual(result.sales[0].quantity, 8)
        self.assertEqual(result.sales[0].revenue, 24)
        self.assertEqual(dict(result.remaining_stock)["a"], 2)
        self.assertEqual(dict(result.remaining_budget)["residents"], 6)

    def test_two_competing_companies(self):
        req = request([offer("a", "firm_a", 3), offer("b", "firm_b", 9)],
                      [demand(preferred_offers=("a", "b"))])
        _, result = run(req)
        self.assertEqual([(s.company_id, s.quantity) for s in result.sales],
                         [("firm_a", 3), ("firm_b", 5)])
        self.assertEqual(dict(result.company_revenue),
                         {"firm_a": 9, "firm_b": 15})

    def test_competition_respects_explicit_preference(self):
        req = request([offer("a", "firm_a"), offer("b", "firm_b")],
                      [demand(preferred_offers=("b", "a"))])
        _, result = run(req)
        self.assertEqual(result.sales[0].company_id, "firm_b")

    def test_no_preferences_means_no_sales(self):
        _, result = run(request(demands=[demand(preferred_offers=())]))
        self.assertEqual(result.sales, ())
        self.assertEqual(dict(result.unfilled_demand)["residents"], 8)

    def test_no_demand(self):
        _, result = run(request(demands=[]))
        self.assertEqual(result.sales, ())

    def test_no_offers(self):
        _, result = run(request(offers=[], demands=[demand(preferred_offers=())]))
        self.assertEqual(result.sales, ())

    def test_zero_stock(self):
        _, result = run(request(offers=[offer(available=0)]))
        self.assertEqual(result.sales, ())

    def test_zero_budget(self):
        _, result = run(request(demands=[demand(budget=0)]))
        self.assertEqual(result.sales, ())

    def test_zero_demand(self):
        _, result = run(request(demands=[demand(quantity=0)]))
        self.assertEqual(result.sales, ())

    def test_budget_limit(self):
        _, result = run(request(demands=[demand(budget=7)]))
        self.assertEqual(result.sales[0].quantity, 2)
        self.assertEqual(dict(result.remaining_budget)["residents"], 1)

    def test_stock_limit(self):
        _, result = run(request(offers=[offer(available=2)]))
        self.assertEqual(result.sales[0].quantity, 2)

    def test_exact_budget(self):
        _, result = run(request(demands=[demand(budget=24)]))
        self.assertEqual(dict(result.remaining_budget)["residents"], 0)

    def test_exact_stock(self):
        _, result = run(request(offers=[offer(available=8)]))
        self.assertEqual(dict(result.remaining_stock)["a"], 0)

    def test_cohort_tie_breaker_independent_of_input_order(self):
        a, b = demand("a", 6), demand("b", 6)
        first = run(request(offers=[offer(available=8)], demands=[b, a]))[1]
        second = run(request(offers=[offer(available=8)], demands=[a, b]))[1]
        self.assertEqual(first.sales, second.sales)
        self.assertEqual([(s.cohort_id, s.quantity) for s in first.sales],
                         [("a", 6), ("b", 2)])

    def test_repeat_returns_previous_without_double_sale(self):
        state, result = run()
        next_state, replay = run(state=state)
        self.assertIs(state, next_state)
        self.assertIs(result, replay)

    def test_repeat_conflicting_payload(self):
        state, _ = run()
        self.assert_error("IDEMPOTENCY_CONFLICT",
                          request(demands=[demand(quantity=1)]), state)

    def test_distinct_operation(self):
        state, _ = run()
        _, result = run(replace(request(), operation_id="sale_2"), state)
        self.assertEqual(len(result.sales), 1)

    def test_input_unchanged(self):
        req, state = request(), RetailState({})
        run(req, state)
        self.assertEqual(req.offers[0].available, 10)
        self.assertEqual(state.completed, {})

    def test_price_max(self):
        req = request(offers=[offer(unit_price=MAX)],
                      demands=[demand(quantity=1, budget=MAX)])
        _, result = run(req)
        self.assertEqual(result.sales[0].revenue, MAX)

    def test_revenue_overflow(self):
        req = request(offers=[offer("a", "firm_a", 1, MAX),
                              offer("b", "firm_a", 1, 1)],
                      demands=[demand("a", 1, MAX, ("a",)),
                               demand("b", 1, 1, ("b",))])
        self.assert_error("REVENUE_OVERFLOW", req)

    def test_large_integer_precision(self):
        value = 10**15 + 1
        req = request(offers=[offer(available=value, unit_price=1)],
                      demands=[demand(quantity=value, budget=value)])
        _, result = run(req)
        self.assertEqual(result.sales[0].quantity, value)

    def test_duplicate_offer(self):
        self.assert_error("DUPLICATE_OFFER", request(offers=[offer(), offer()]))

    def test_duplicate_cohort(self):
        self.assert_error("DUPLICATE_COHORT", request(demands=[demand(), demand()]))

    def test_unknown_offer(self):
        self.assert_error("UNKNOWN_OFFER", request(demands=[demand(preferred_offers=("b",))]))

    def test_cross_city_rejected(self):
        self.assert_error("INELIGIBLE_OFFER",
                          request(demands=[demand(city_id="sterlitamak")]))

    def test_cross_product_rejected(self):
        self.assert_error("INELIGIBLE_OFFER",
                          request(demands=[demand(product_id="milk")]))

    def test_duplicate_preference(self):
        self.assert_error("DUPLICATE_PREFERENCE",
                          request(demands=[demand(preferred_offers=("a", "a"))]))

    def test_bad_preference_type(self):
        self.assert_error("INVALID_PREFERENCES",
                          request(demands=[demand(preferred_offers=["a"])]))

    def test_invalid_price_zero(self):
        self.assert_error("INVALID_AMOUNT", request(offers=[offer(unit_price=0)]))

    def test_invalid_price_negative(self):
        self.assert_error("INVALID_AMOUNT", request(offers=[offer(unit_price=-1)]))

    def test_invalid_price_bool(self):
        self.assert_error("INVALID_AMOUNT", request(offers=[offer(unit_price=True)]))

    def test_invalid_stock(self):
        self.assert_error("INVALID_AMOUNT", request(offers=[offer(available=-1)]))

    def test_invalid_demand(self):
        self.assert_error("INVALID_AMOUNT", request(demands=[demand(quantity=-1)]))

    def test_invalid_budget(self):
        self.assert_error("INVALID_AMOUNT", request(demands=[demand(budget=-1)]))

    def test_invalid_overflow(self):
        self.assert_error("INVALID_AMOUNT", request(demands=[demand(budget=MAX + 1)]))

    def test_invalid_id(self):
        self.assert_error("INVALID_ID", request(offers=[offer(offer_id="bad id")]))

    def test_invalid_version(self):
        self.assert_error("INVALID_AMOUNT", replace(request(), rules_version=0))

    def test_invalid_state(self):
        self.assert_error("INVALID_STATE", state=RetailState(None))

    def test_invalid_offer_type(self):
        self.assert_error("INVALID_OFFER", request(offers=[None]))

    def test_invalid_demand_type(self):
        self.assert_error("INVALID_DEMAND", request(demands=[None]))

    def test_invalid_request_type(self):
        self.assert_error("INVALID_REQUEST", "not a request")

    def test_invalid_collection_type(self):
        self.assert_error("INVALID_REQUEST", replace(request(), offers=[]))

    def test_invalid_operation_id(self):
        self.assert_error("INVALID_ID", replace(request(), operation_id=""))

    def test_zero_unit_fraction_is_not_sold(self):
        _, result = run(request(demands=[demand(budget=2)]))
        self.assertEqual(result.sales, ())


if __name__ == "__main__":
    unittest.main()
