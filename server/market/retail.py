"""Deterministic retail clearing with externally supplied demand and buyer priority.

No population-demand formula, price elasticity, or geographical coefficients are
assumed here. The caller supplies integer demand, reach eligibility, and the
priority ordering, all of which require a separately approved rules version.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

MAX = 2**63 - 1


class MarketError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class RetailOffer:
    offer_id: str
    company_id: str
    store_id: str
    city_id: str
    product_id: str
    unit_price: int
    available: int


@dataclass(frozen=True)
class PopulationDemand:
    cohort_id: str
    city_id: str
    product_id: str
    quantity: int
    budget: int
    # Ordered offer IDs, explicitly determined by upstream policy.
    # No hidden alphabetical/company priority is used.
    preferred_offers: tuple[str, ...]


@dataclass(frozen=True)
class RetailRequest:
    period_id: str
    operation_id: str
    rules_version: int
    offers: tuple[RetailOffer, ...]
    demands: tuple[PopulationDemand, ...]


@dataclass(frozen=True)
class RetailSale:
    cohort_id: str
    offer_id: str
    company_id: str
    store_id: str
    product_id: str
    quantity: int
    unit_price: int
    revenue: int


@dataclass(frozen=True)
class RetailResult:
    request: RetailRequest
    sales: tuple[RetailSale, ...]
    remaining_stock: tuple[tuple[str, int], ...]
    unfilled_demand: tuple[tuple[str, int], ...]
    remaining_budget: tuple[tuple[str, int], ...]
    company_revenue: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class RetailState:
    completed: Mapping[tuple[str, str], RetailResult]


def _number(value: int, field: str, *, positive: bool = False) -> None:
    if type(value) is not int or not (1 if positive else 0) <= value <= MAX:
        raise MarketError("INVALID_AMOUNT", f"{field}: требуется целое число {'1' if positive else '0'}..{MAX}")


def _id(value: str, field: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 128 or not value.isascii() or not all(
        ch.isalnum() or ch in "_-" for ch in value
    ):
        raise MarketError("INVALID_ID", f"{field}: идентификатор 1..128, ASCII буквы/цифры/_/-")


def _validate(request: RetailRequest) -> tuple[dict[str, RetailOffer], dict[str, PopulationDemand]]:
    if not isinstance(request, RetailRequest):
        raise MarketError("INVALID_REQUEST", "ожидается RetailRequest")
    _id(request.period_id, "period_id")
    _id(request.operation_id, "operation_id")
    _number(request.rules_version, "rules_version", positive=True)
    if not isinstance(request.offers, tuple) or not isinstance(request.demands, tuple):
        raise MarketError("INVALID_REQUEST", "offers и demands должны быть tuple")
    offers: dict[str, RetailOffer] = {}
    for offer in request.offers:
        if not isinstance(offer, RetailOffer):
            raise MarketError("INVALID_OFFER", "ожидается RetailOffer")
        for field in ("offer_id", "company_id", "store_id", "city_id", "product_id"):
            _id(getattr(offer, field), field)
        if offer.offer_id in offers:
            raise MarketError("DUPLICATE_OFFER", offer.offer_id)
        _number(offer.unit_price, "unit_price", positive=True)
        _number(offer.available, "available")
        offers[offer.offer_id] = offer
    demands: dict[str, PopulationDemand] = {}
    for demand in request.demands:
        if not isinstance(demand, PopulationDemand):
            raise MarketError("INVALID_DEMAND", "ожидается PopulationDemand")
        for field in ("cohort_id", "city_id", "product_id"):
            _id(getattr(demand, field), field)
        if demand.cohort_id in demands:
            raise MarketError("DUPLICATE_COHORT", demand.cohort_id)
        _number(demand.quantity, "quantity")
        _number(demand.budget, "budget")
        if not isinstance(demand.preferred_offers, tuple):
            raise MarketError("INVALID_PREFERENCES", demand.cohort_id)
        if len(demand.preferred_offers) != len(set(demand.preferred_offers)):
            raise MarketError("DUPLICATE_PREFERENCE", demand.cohort_id)
        for offer_id in demand.preferred_offers:
            _id(offer_id, "preferred_offer")
            if offer_id not in offers:
                raise MarketError("UNKNOWN_OFFER", offer_id)
            offer = offers[offer_id]
            if (offer.city_id, offer.product_id) != (demand.city_id, demand.product_id):
                raise MarketError("INELIGIBLE_OFFER", offer_id)
        demands[demand.cohort_id] = demand
    return offers, demands


def clear_retail(request: RetailRequest, state: RetailState) -> tuple[RetailState, RetailResult]:
    """Pure clearing, deterministic by cohort ID and explicit preference order.

    Each cohort buys whole units at exact integer unit prices. If multiple
    cohorts want scarce stock, lexical cohort ID is an EXPLICIT PROVISIONAL
    tie-breaker, not an approved economic balancing rule. No floating point.
    Persist state and stock/ledger updates atomically in the orchestrator.
    """
    offers, demands = _validate(request)
    if not isinstance(state, RetailState) or not isinstance(state.completed, Mapping):
        raise MarketError("INVALID_STATE", "ожидается RetailState с completed")
    key = (request.period_id, request.operation_id)
    if key in state.completed:
        previous = state.completed[key]
        if not isinstance(previous, RetailResult) or previous.request != request:
            raise MarketError("IDEMPOTENCY_CONFLICT", "ключ операции уже использован")
        return state, previous
    stock = {key: value.available for key, value in offers.items()}
    remaining_budget = {key: value.budget for key, value in demands.items()}
    unfilled = {}
    sales: list[RetailSale] = []
    revenue: dict[str, int] = {}
    for cohort_id in sorted(demands):
        demand = demands[cohort_id]
        needed = demand.quantity
        for offer_id in demand.preferred_offers:
            if not needed:
                break
            offer = offers[offer_id]
            count = min(needed, stock[offer_id], remaining_budget[cohort_id] // offer.unit_price)
            if not count:
                continue
            total = count * offer.unit_price
            if total > MAX - revenue.get(offer.company_id, 0):
                raise MarketError("REVENUE_OVERFLOW", offer.company_id)
            stock[offer_id] -= count
            needed -= count
            remaining_budget[cohort_id] -= total
            revenue[offer.company_id] = revenue.get(offer.company_id, 0) + total
            sales.append(RetailSale(cohort_id, offer_id, offer.company_id, offer.store_id,
                                    offer.product_id, count, offer.unit_price, total))
        unfilled[cohort_id] = needed
    result = RetailResult(request, tuple(sales), tuple(sorted(stock.items())),
                          tuple(sorted(unfilled.items())),
                          tuple(sorted(remaining_budget.items())),
                          tuple(sorted(revenue.items())))
    completed = dict(state.completed)
    completed[key] = result
    return RetailState(completed), result
