import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server.catalog import *


def fixture():
    return Catalog(1, (Product("grain", "Зерно", "g"), Product("flour", "Мука", "g")), (EnterpriseType("mill", "Мельница"),), (EquipmentType("millstone", "Жернова"),), (Recipe("grind", "mill", (Ingredient("grain", 3),), (Ingredient("flour", 2),), "millstone"),))

class CatalogTests(unittest.TestCase):
    def test_valid(self):
        self.assertIsNone(validate_catalog(fixture()))
    def test_plan(self):
        p=plan_production(fixture(),"grind",{"grain":10},4)
        self.assertEqual((p.batches,p.consumed[0].quantity,p.produced[0].quantity,p.remaining[0].quantity),(3,9,6,1))
    def test_zero(self):
        self.assertEqual(plan_production(fixture(),"grind",{},0).batches,0)
    def test_no_stock(self):
        self.assertEqual(plan_production(fixture(),"grind",{},10).batches,0)
    def test_repeat_is_pure(self):
        stock={"grain":9}
        self.assertEqual(plan_production(fixture(),"grind",stock,9),plan_production(fixture(),"grind",stock,9))
        self.assertEqual(stock,{"grain":9})
    def test_unknown_recipe(self):
        with self.assertRaisesRegex(CatalogError,"UNKNOWN_RECIPE"):plan_production(fixture(),"no",{},1)
    def test_unknown_stock(self):
        with self.assertRaisesRegex(CatalogError,"UNKNOWN_STOCK_PRODUCT"):plan_production(fixture(),"grind",{"fake":1},1)
    def test_negative_stock(self):
        with self.assertRaisesRegex(CatalogError,"INVALID_QUANTITY"):plan_production(fixture(),"grind",{"grain":-1},1)
    def test_bool_quantity(self):
        with self.assertRaisesRegex(CatalogError,"INVALID_QUANTITY"):plan_production(fixture(),"grind",{},True)
    def test_overflow_clamped(self):
        p=plan_production(fixture(),"grind",{"grain":2**63-1},2**63-1)
        self.assertLessEqual(p.produced[0].quantity,2**63-1)
    def test_duplicate_product(self):
        c=fixture(); c=Catalog(c.version,c.products+(c.products[0],),c.enterprises,c.equipment,c.recipes)
        with self.assertRaisesRegex(CatalogError,"DUPLICATE_ID"):validate_catalog(c)
    def test_unknown_input(self):
        c=fixture(); r=Recipe("x","mill",(Ingredient("unknown",1),),(Ingredient("flour",1),))
        with self.assertRaisesRegex(CatalogError,"UNKNOWN_PRODUCT"):validate_catalog(Catalog(c.version,c.products,c.enterprises,c.equipment,(r,)))
    def test_unknown_enterprise(self):
        c=fixture(); r=Recipe("x","unknown",(),(Ingredient("flour",1),))
        with self.assertRaisesRegex(CatalogError,"UNKNOWN_ENTERPRISE"):validate_catalog(Catalog(c.version,c.products,c.enterprises,c.equipment,(r,)))
    def test_duplicate_ingredient(self):
        c=fixture(); r=Recipe("x","mill",(Ingredient("grain",1),Ingredient("grain",2)),(Ingredient("flour",1),))
        with self.assertRaisesRegex(CatalogError,"DUPLICATE_INGREDIENT"):validate_catalog(Catalog(c.version,c.products,c.enterprises,c.equipment,(r,)))
    def test_empty_output(self):
        c=fixture(); r=Recipe("x","mill",(),())
        with self.assertRaisesRegex(CatalogError,"EMPTY_OUTPUT"):validate_catalog(Catalog(c.version,c.products,c.enterprises,c.equipment,(r,)))
    def test_extraction_no_inputs(self):
        c=fixture(); r=Recipe("extract","mill",(),(Ingredient("grain",5),))
        c=Catalog(c.version,c.products,c.enterprises,c.equipment,(r,))
        self.assertEqual(plan_production(c,"extract",{},3).produced[0].quantity,15)

if __name__=="__main__":unittest.main()
