"""Importer + RBAC unit tests. Standard library only:  python -m unittest discover tests"""

import io
import unittest
from decimal import Decimal

from openpyxl import Workbook

from app.core.enums import ContentStatus, UserRole
from app.core.permissions import Permission, has_permission
from app.importers import ImportFormatError, get_importer, list_importers
from app.importers.tabular import normalize_header, parse_decimal

ETSY_CSV = (
    "TITLE,DESCRIPTION,PRICE,CURRENCY_CODE,QUANTITY,TAGS,MATERIALS,IMAGE1,IMAGE2,"
    "VARIATION 1 TYPE,VARIATION 1 NAME,VARIATION 1 VALUES,VARIATION 2 TYPE,VARIATION 2 NAME,"
    "VARIATION 2 VALUES,SKU\n"
    '"Walnut Serving Board","Hand finished.\nFood safe.",45.00,USD,3,"kitchen,wood,gift",'
    '"walnut,mineral oil",https://i.etsystatic.com/a.jpg,https://i.etsystatic.com/b.jpg,'
    'Size,Size,"Small,Large",,,,WB-01\n'
    ',,,,,,,,,,,,,,,\n'
    '"Brass Candle Holder",,"$1,120.50",USD,1,,,,,,,,,,,\n'
)

AMAZON_FLAT = (
    "TemplateType=fptcustom\tVersion=2023.1\n"
    "SKU\tProduct Name\tPrice\n"
    "item_sku\titem_name\tstandard_price\tquantity\tmain_image_url\tparent_child\tparent_sku\t"
    "color_name\tbrand_name\tbullet_point1\n"
    "MUG-P\tCity Mug\t\t\thttps://m.media-amazon.com/p.jpg\tparent\t\t\tWCW\tDishwasher safe\n"
    "MUG-R\tCity Mug Red\t18.00\t5\t\tchild\tMUG-P\tRed\tWCW\t\n"
    "MUG-B\tCity Mug Blue\t16.00\t2\t\tchild\tMUG-P\tBlue\tWCW\t\n"
    "SOLO\tCoaster Set\t12\t9\t\t\t\t\t\t\n"
)

AMAZON_REPORT = (
    "item-name\titem-description\tlisting-id\tseller-sku\tprice\tquantity\topen-date\tasin1\n"
    "Lake Print\tA print\t123\tLP-1\t30.00\t4\t2024-01-01\tB00TEST\n"
)


def xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TabularTests(unittest.TestCase):
    def test_normalize_header(self):
        self.assertEqual(normalize_header("VARIATION 1 TYPE"), "variation_1_type")
        self.assertEqual(normalize_header("seller-sku"), "seller_sku")
        self.assertEqual(normalize_header("item_name[marketplace_id=ATVPDKIKX0DER]#1.value"), "item_name")

    def test_parse_decimal(self):
        self.assertEqual(parse_decimal("$1,234.50"), Decimal("1234.50"))
        self.assertEqual(parse_decimal("1.234,50"), Decimal("1234.50"))
        self.assertEqual(parse_decimal("12,50"), Decimal("12.50"))
        self.assertEqual(parse_decimal("20"), Decimal("20.00"))
        self.assertIsNone(parse_decimal(""))


class EtsyTests(unittest.TestCase):
    def test_parse(self):
        result = get_importer("etsy").parse(ETSY_CSV.encode(), "EtsyListingsDownload.csv")
        self.assertEqual(len(result.products), 2)
        board = result.products[0]
        self.assertEqual(board.title, "Walnut Serving Board")
        self.assertEqual(board.price, Decimal("45.00"))
        self.assertEqual(board.quantity, 3)
        self.assertEqual(board.sku, "WB-01")
        self.assertEqual(board.tags, ["kitchen", "wood", "gift"])
        self.assertEqual(board.attributes["Material"], ["walnut", "mineral oil"])
        self.assertEqual(board.attributes["Size"], ["Small", "Large"])
        self.assertEqual(len(board.images), 2)
        self.assertIn("Food safe.", board.description)
        holder = result.products[1]
        self.assertEqual(holder.price, Decimal("1120.50"))
        self.assertEqual(holder.source_ref, "brass-candle-holder")

    def test_rejects_wrong_file(self):
        with self.assertRaises(ImportFormatError):
            get_importer("etsy").parse(b"name,cost\nx,1\n", "x.csv")


class AmazonTests(unittest.TestCase):
    def test_flat_file_with_variants(self):
        result = get_importer("amazon").parse(AMAZON_FLAT.encode(), "flat.txt")
        self.assertEqual([p.sku for p in result.products], ["MUG-P", "SOLO"])
        mug = result.products[0]
        self.assertEqual(len(mug.variants), 2)
        self.assertEqual(mug.price, Decimal("16.00"))  # lowest variant price
        self.assertEqual(mug.attributes["Color"], ["Red", "Blue"])
        self.assertEqual(mug.attributes["Brand"], "WCW")
        self.assertIn("• Dishwasher safe", mug.description)
        self.assertEqual(mug.variants[0].attributes, {"Color": "Red"})

    def test_listings_report(self):
        result = get_importer("amazon").parse(AMAZON_REPORT.encode(), "All+Listings+Report.txt")
        p = result.products[0]
        self.assertEqual((p.sku, p.price, p.quantity, p.source_ref), ("LP-1", Decimal("30.00"), 4, "B00TEST"))


class SpreadsheetTests(unittest.TestCase):
    def test_xlsx_round_trip_format(self):
        content = xlsx(
            [
                ["sku", "title", "price", "quantity", "category", "images", "status", "attr:Material", "parent_sku"],
                ["V-1", "Glass Vase", 25, 4, "Home > Decor > Vases", "https://x/a.jpg|https://x/b.jpg", "Published", "Glass", None],
                ["V-1-L", "Glass Vase Large", 35, 1, None, None, None, "Glass", "V-1"],
                ["T-9", "Throw", "40.5", None, "Home/Textiles", None, "bogus", "Wool|Cotton", None],
                ["X-1", "Orphan Variant", 5, None, None, None, None, None, "EXISTING-SKU"],
            ]
        )
        result = get_importer("spreadsheet").parse(content, "catalog.xlsx")
        self.assertEqual([p.sku for p in result.products], ["V-1", "T-9", "X-1"])
        vase, throw, orphan = result.products
        self.assertEqual(vase.category_path, ["Home", "Decor", "Vases"])
        self.assertEqual(vase.status, ContentStatus.PUBLISHED)
        self.assertEqual(len(vase.images), 2)
        self.assertEqual(vase.variants[0].sku, "V-1-L")
        self.assertEqual(vase.attributes, {"Material": "Glass"})
        self.assertEqual(throw.attributes, {"Material": ["Wool", "Cotton"]})
        self.assertEqual(throw.category_path, ["Home", "Textiles"])
        self.assertIsNone(throw.status)
        self.assertTrue(any("bogus" in w for w in result.warnings))
        self.assertEqual(orphan.parent_sku, "EXISTING-SKU")

    def test_registry(self):
        self.assertEqual({i.key for i in list_importers()}, {"etsy", "amazon", "spreadsheet"})
        self.assertIsNone(get_importer("nope"))


class PermissionTests(unittest.TestCase):
    def test_roles(self):
        self.assertTrue(has_permission(UserRole.ADMIN, Permission.USERS_MANAGE))
        self.assertFalse(has_permission(UserRole.PUBLISHER, Permission.USERS_MANAGE))
        self.assertFalse(has_permission(UserRole.PUBLISHER, Permission.SETTINGS_MANAGE))
        self.assertTrue(has_permission(UserRole.PUBLISHER, Permission.CATALOG_PUBLISH))
        self.assertTrue(has_permission(UserRole.AUTHOR, Permission.CATALOG_CREATE))
        self.assertFalse(has_permission(UserRole.AUTHOR, Permission.CATALOG_PUBLISH))
        self.assertFalse(has_permission(UserRole.CUSTOMER, Permission.CATALOG_CREATE))


if __name__ == "__main__":
    unittest.main()
