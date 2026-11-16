"""Pure catalog validation and integer recipe planning; no database or clocks.

Quantities use integer base units chosen by each product (e.g. grams or pieces).
A recipe is one atomic batch. Production cannot consume partial batches.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
import re

_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX = 2**63 - 1

class CatalogError(ValueError):
    """User-readable deterministic validation error with stable code."""
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")

@dataclass(frozen=True)
class Product:
    id: str
    name: str
    unit: str
    tradable: bool = True

@dataclass(frozen=True)
class Ingredient:
    product_id: str
    quantity: int

@dataclass(frozen=True)
class Recipe:
    id: str
    enterprise_type_id: str
    inputs: tuple[Ingredient, ...]
    outputs: tuple[Ingredient, ...]
    equipment_type_id: str | None = None

@dataclass(frozen=True)
class EnterpriseType:
    id: str
    name: str

@dataclass(frozen=True)
class EquipmentType:
    id: str
    name: str

@dataclass(frozen=True)
class Catalog:
    version: int
    products: tuple[Product, ...]
    enterprises: tuple[EnterpriseType, ...]
    equipment: tuple[EquipmentType, ...]
    recipes: tuple[Recipe, ...]

@dataclass(frozen=True)
class ProductionPlan:
    batches: int
    consumed: tuple[Ingredient, ...]
    produced: tuple[Ingredient, ...]
    remaining: tuple[Ingredient, ...]


def _positive(value: int, field: str, allow_zero: bool = False) -> None:
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= _MAX:
        raise CatalogError("INVALID_QUANTITY", f"{field}: требуется целое число в диапазоне {0 if allow_zero else 1}..{_MAX}")


def _identifier(value: str, field: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise CatalogError("INVALID_ID", f"{field}: нужен идентификатор a-z, 0-9, _ (до 64 символов)")


def _unique(items, label: str) -> dict:
    result = {}
    for item in items:
        _identifier(item.id, label)
        if item.id in result:
            raise CatalogError("DUPLICATE_ID", f"{label}: повторяется {item.id}")
        result[item.id] = item
    return result


def validate_catalog(catalog: Catalog) -> None:
    _positive(catalog.version, "catalog.version")
    products = _unique(catalog.products, "product")
    enterprises = _unique(catalog.enterprises, "enterprise")
    equipment = _unique(catalog.equipment, "equipment")
    recipes = _unique(catalog.recipes, "recipe")
    for group in (catalog.products, catalog.enterprises, catalog.equipment):
        for item in group:
            if not isinstance(item.name, str) or not item.name.strip():
                raise CatalogError("EMPTY_NAME", f"{item.id}: пустое название")
    for p in catalog.products:
        if not isinstance(p.unit, str) or not p.unit.strip():
            raise CatalogError("EMPTY_UNIT", f"{p.id}: отсутствует базовая единица")
        if type(p.tradable) is not bool:
            raise CatalogError("INVALID_FLAG", f"{p.id}: tradable должен быть bool")
    for r in recipes.values():
        if r.enterprise_type_id not in enterprises:
            raise CatalogError("UNKNOWN_ENTERPRISE", f"{r.id}: {r.enterprise_type_id}")
        if r.equipment_type_id is not None and r.equipment_type_id not in equipment:
            raise CatalogError("UNKNOWN_EQUIPMENT", f"{r.id}: {r.equipment_type_id}")
        if not r.outputs:
            raise CatalogError("EMPTY_OUTPUT", f"{r.id}: рецепт без продукции")
        for side, ingredients in (("input", r.inputs), ("output", r.outputs)):
            seen = set()
            for item in ingredients:
                _identifier(item.product_id, f"{r.id}.{side}")
                _positive(item.quantity, f"{r.id}.{side}.{item.product_id}")
                if item.product_id not in products:
                    raise CatalogError("UNKNOWN_PRODUCT", f"{r.id}: {item.product_id}")
                if item.product_id in seen:
                    raise CatalogError("DUPLICATE_INGREDIENT", f"{r.id}.{side}: {item.product_id}")
                seen.add(item.product_id)


def plan_production(catalog: Catalog, recipe_id: str, stock: Mapping[str, int], requested_batches: int) -> ProductionPlan:
    """Compute a batch plan without mutating stock; outputs become available next tick."""
    validate_catalog(catalog)
    _positive(requested_batches, "requested_batches", allow_zero=True)
    recipes = {r.id: r for r in catalog.recipes}
    if recipe_id not in recipes:
        raise CatalogError("UNKNOWN_RECIPE", recipe_id)
    product_ids = {p.id for p in catalog.products}
    for product_id, quantity in stock.items():
        if product_id not in product_ids:
            raise CatalogError("UNKNOWN_STOCK_PRODUCT", product_id)
        _positive(quantity, f"stock.{product_id}", allow_zero=True)
    recipe = recipes[recipe_id]
    batches = requested_batches
    for i in recipe.inputs:
        batches = min(batches, stock.get(i.product_id, 0) // i.quantity)
    for i in (*recipe.inputs, *recipe.outputs):
        batches = min(batches, _MAX // i.quantity)
    consumed = tuple(Ingredient(i.product_id, i.quantity * batches) for i in recipe.inputs)
    produced = tuple(Ingredient(i.product_id, i.quantity * batches) for i in recipe.outputs)
    remaining = tuple(Ingredient(pid, stock[pid] - next((i.quantity for i in consumed if i.product_id == pid), 0)) for pid in sorted(stock))
    return ProductionPlan(batches, consumed, produced, remaining)
