from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from server.catalog import Catalog, CatalogError, Ingredient, plan_production, validate_catalog

MAX = 2**63 - 1

class EconomyError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")

@dataclass(frozen=True)
class ProductionRequest:
    period_id: str
    operation_id: str
    recipe_id: str
    catalog_version: int
    requested_batches: int
    capacity_batches: int

@dataclass(frozen=True)
class ProductionResult:
    request: ProductionRequest
    batches: int
    consumed: tuple[Ingredient, ...]
    produced_pending: tuple[Ingredient, ...]
    stock_after: tuple[Ingredient, ...]
    pending_after: tuple[Ingredient, ...]
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class ProductionState:
    """Pure snapshot; commit stock, pending and completed atomically in caller."""
    stock: Mapping[str, int]
    pending: Mapping[str, int]
    completed: Mapping[str, ProductionResult]

def _amount(value: int, name: str) -> None:
    if type(value) is not int or not 0 <= value <= MAX:
        raise EconomyError("INVALID_AMOUNT", f"{name}: требуется целое 0..{MAX}")

def _name(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise EconomyError("INVALID_IDENTIFIER", f"{field}: непустая строка до 128 символов")

def _stock(values: Mapping[str, int], name: str, products: set[str]) -> dict[str, int]:
    if not isinstance(values, Mapping):
        raise EconomyError("INVALID_STATE", f"{name}: требуется отображение")
    result = {}
    for pid, quantity in values.items():
        if pid not in products:
            raise EconomyError("UNKNOWN_PRODUCT", f"{name}.{pid}")
        _amount(quantity, f"{name}.{pid}")
        result[pid] = quantity
    return result

def _items(values: Mapping[str, int]) -> tuple[Ingredient, ...]:
    return tuple(Ingredient(pid, values[pid]) for pid in sorted(values))

def execute_production(
    catalog: Catalog, request: ProductionRequest,
    state: ProductionState, warehouse_free: Mapping[str, int]
) -> tuple[ProductionState, ProductionResult]:
    """Compute whole batches, consume available stock, defer output to next period.

    warehouse_free expresses unreserved remaining space for additional output
    per product. Missing entries mean zero space. Caller supplies capacity;
    no unapproved productivity formula or tick schedule is embedded.
    """
    validate_catalog(catalog)
    if not isinstance(request, ProductionRequest) or not isinstance(state, ProductionState):
        raise EconomyError("INVALID_STATE", "требуются ProductionRequest и ProductionState")
    for field in ("period_id", "operation_id", "recipe_id"):
        _name(getattr(request, field), field)
    _amount(request.catalog_version, "catalog_version")
    if request.catalog_version != catalog.version:
        raise EconomyError("CATALOG_VERSION_MISMATCH", "версия каталога отличается")
    for field in ("requested_batches", "capacity_batches"):
        _amount(getattr(request, field), field)
    products = {p.id for p in catalog.products}
    stock = _stock(state.stock, "stock", products)
    pending = _stock(state.pending, "pending", products)
    free = _stock(warehouse_free, "warehouse_free", products)
    if not isinstance(state.completed, Mapping):
        raise EconomyError("INVALID_STATE", "completed: требуется отображение")
    key = f"{request.period_id}:{request.operation_id}"
    if key in state.completed:
        prior = state.completed[key]
        if not isinstance(prior, ProductionResult) or prior.request != request:
            raise EconomyError("IDEMPOTENCY_CONFLICT", "ключ операции уже использован")
        return state, prior
    capped = min(request.requested_batches, request.capacity_batches)
    try:
        plan = plan_production(catalog, request.recipe_id, stock, capped)
    except CatalogError as exc:
        raise EconomyError(exc.code, str(exc)) from exc
    recipe = next(r for r in catalog.recipes if r.id == request.recipe_id)
    batches = plan.batches
    for output in recipe.outputs:
        batches = min(batches, free.get(output.product_id, 0) // output.quantity)
        batches = min(batches, (MAX - pending.get(output.product_id, 0)) // output.quantity)
    consumed = tuple(Ingredient(i.product_id, i.quantity * batches) for i in recipe.inputs)
    produced = tuple(Ingredient(i.product_id, i.quantity * batches) for i in recipe.outputs)
    for item in consumed:
        stock[item.product_id] = stock.get(item.product_id, 0) - item.quantity
    for item in produced:
        pending[item.product_id] = pending.get(item.product_id, 0) + item.quantity
    reasons = []
    if batches < request.requested_batches:
        if request.capacity_batches < request.requested_batches:
            reasons.append("CAPACITY_LIMIT")
        if plan.batches < capped:
            reasons.append("INPUT_SHORTAGE_OR_LIMIT")
        if batches < plan.batches:
            reasons.append("WAREHOUSE_LIMIT")
    result = ProductionResult(request, batches, consumed, produced, _items(stock), _items(pending), tuple(reasons))
    completed = dict(state.completed)
    completed[key] = result
    return ProductionState(stock, pending, completed), result

def start_next_period(state: ProductionState) -> ProductionState:
    """Pure helper: caller authorizes transition exactly once and persists it."""
    if not isinstance(state, ProductionState):
        raise EconomyError("INVALID_STATE", "требуется ProductionState")
    stock, pending = dict(state.stock), dict(state.pending)
    for pid, count in pending.items():
        _amount(count, f"pending.{pid}")
        _amount(stock.get(pid, 0), f"stock.{pid}")
        if stock.get(pid, 0) > MAX - count:
            raise EconomyError("STOCK_OVERFLOW", pid)
        stock[pid] = stock.get(pid, 0) + count
    return ProductionState(stock, {}, dict(state.completed))
