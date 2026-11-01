import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import bot


def fixture(shifted=False, cross_sheet=False):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("xl/workbook.xml", '''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Trending" sheetId="1" r:id="r1"/></sheets></workbook>''')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/_rels/sheet1.xml.rels", '<Relationships><Relationship Id="link" Target="https://item.kakobuy.com/item/details?url=https%3A%2F%2Fweidian.com%2Fitem.html%3FitemID%3D123&amp;affcode=abc"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheetData>
        <row r="14"><c r="B14" t="inlineStr"><is><t>PRODUCT</t></is></c><c r="D14" t="inlineStr"><is><t>KAKOBUY LINK</t></is></c><c r="G14" t="inlineStr"><is><t>IMAGE</t></is></c></row>
        <row r="15"><c r="B15" t="inlineStr"><is><t>Felpa &amp; cappuccio</t></is></c><c r="D15" t="inlineStr"><is><t>LINK</t></is></c><c r="F15"><f>E15/$D$10</f><v>30.76923077</v></c><c r="G15"><f>IMAGE("https://example.com/photo.jpg")</f></c></row>
        <row r="16"><c r="F16"><f>E15/$D$11</f><v>26.59574468</v></c></row>
        </sheetData><hyperlinks><hyperlink ref="D15" r:id="link"/></hyperlinks></worksheet>''')
    result = io.BytesIO()
    with zipfile.ZipFile(data) as original, zipfile.ZipFile(result, "w") as output:
        for name in original.namelist():
            text = original.read(name).decode()
            if name.endswith("sheet1.xml"):
                text = text.replace('<c r="G14"', '<c r="F14" t="inlineStr"><is><t>PRICE</t></is></c><c r="G14"')
                text = text.replace('<c r="D15"', '<c r="C15" t="inlineStr"><is><t>https://www.ninjabuy.com/r/ABC123</t></is></c><c r="D15"')
            if shifted:
                import re
                columns = {"B": "H", "C": "J", "D": "K", "F": "M", "G": "N"}
                text = re.sub(r'(r|ref)="([BCDFG])(\d+)"', lambda m: f'{m[1]}="{columns[m[2]]}{m[3]}"', text)
            if cross_sheet:
                text = text.replace('/$D$10', "/'Rates'!$D$17").replace('/$D$11', "/'Rates'!$D$18")
            output.writestr(name, text)
    return result.getvalue()


class BotTests(unittest.TestCase):
    def setUp(self):
        self.products = bot.parse_workbook(fixture(), ["Trending"])
        self.config = {"max_posts": 1, "button_text": "Apri", "footer": "Link affiliato."}
        self.state = {"version": 1, "items": {}}

    def test_real_layout_links_images_and_euro(self):
        p = self.products[0]
        self.assertEqual(p["price"], "€26.60 · $30.77")
        self.assertEqual(p["photo"], "https://example.com/photo.jpg")
        self.assertIn("affcode=abc", p["link"])
        self.assertEqual(p["source"], "Trending!B15")

    def test_missing_sheet_fails_closed(self):
        with self.assertRaises(RuntimeError):
            bot.parse_workbook(fixture(), ["Wrong"])

    def test_shifted_columns_and_cross_sheet_rates(self):
        p = bot.parse_workbook(fixture(shifted=True, cross_sheet=True), ["Trending"])[0]
        self.assertEqual(p["source"], "Trending!H15")
        self.assertEqual(p["price"], "€26.60 · $30.77")
        self.assertEqual(p["ninjabuy_link"], "https://www.ninjabuy.com/r/ABC123")

    def test_social_footer_and_safe_html(self):
        config = dict(self.config, haul_url="https://youtube.com/@niftyfk?si=NWKIVs70L5EDq0B8",
                      shorts_url="", register_url="https://ikako.vip/r/beqp5")
        text = bot.caption(self.products[0], config)
        self.assertIn("My social:", text)
        self.assertIn("Haul</a>", text)
        self.assertIn("Register Here", text)
        self.assertIn("https://ikako.vip/r/beqp5", text)
        self.assertIn("Felpa &amp; cappuccio", text)
        self.assertNotIn("Shorts", text)
        self.assertNotIn("135", text)

    def test_audit_tracks_all_candidates(self):
        audit = []
        bot.parse_workbook(fixture(), [], audit)
        self.assertEqual(audit[0]["candidates"], 1)
        self.assertEqual(audit[0]["missing_ninjabuy"], 0)

    def test_all_visible_sheets_deduplicated_with_sources(self):
        data = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(fixture())) as source, zipfile.ZipFile(data, "w") as target:
            for name in source.namelist():
                text = source.read(name).decode()
                if name == "xl/workbook.xml":
                    text = text.replace('</sheets>', '<sheet name="Shoes" sheetId="2" r:id="r2"/></sheets>')
                if name == "xl/_rels/workbook.xml.rels":
                    text = text.replace('</Relationships>', '<Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
                target.writestr(name, text)
                if "sheet1.xml" in name:
                    target.writestr(name.replace("sheet1.xml", "sheet2.xml"), text)
        audit = []
        products = bot.parse_workbook(data.getvalue(), [], audit)
        self.assertEqual(len(audit), 2)
        self.assertEqual(sum(a["valid"] for a in audit), 2)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["sources"], ["Trending!B15", "Shoes!B15"])

    def test_same_product_across_affiliate_links(self):
        first = self.products[0]["link"]
        second = first.replace("item.kakobuy", "item2.kakobuy").replace("affcode=abc", "affcode=xyz")
        self.assertEqual(bot.product_key(first), bot.product_key(second))
        self.assertNotEqual(bot.product_key(first), bot.product_key(first.replace("123", "124")))

    def test_success_is_not_sent_twice(self):
        with patch.object(bot, "save_state") as save, patch.object(bot, "telegram", return_value={"message_id": 42}) as send:
            bot.publish(self.products, self.config, self.state, "secret", "@test", True)
            bot.publish(self.products, self.config, self.state, "secret", "@test", True)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(save.call_count, 2)
        payload = send.call_args.args[2]
        self.assertEqual(payload["parse_mode"], "HTML")
        self.assertEqual(len(payload["reply_markup"]["inline_keyboard"][0]), 2)
        self.assertEqual(next(iter(self.state["items"].values()))["status"], "sent")

    def test_persistence_failure_prevents_send(self):
        with patch.object(bot, "save_state", side_effect=RuntimeError("push failed")), patch.object(bot, "telegram") as send:
            with self.assertRaises(RuntimeError):
                bot.publish(self.products, self.config, self.state, "secret", "@test", True)
        send.assert_not_called()

    def test_uncertain_delivery_blocks_retry(self):
        with patch.object(bot, "save_state"), patch.object(bot, "telegram", side_effect=RuntimeError("timeout")) as send:
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    bot.publish(self.products, self.config, self.state, "secret", "@test", True)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(next(iter(self.state["items"].values()))["status"], "pending")

    def test_pending_durable_before_telegram(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bot, "ROOT", Path(tmp)):
            def check(*args):
                on_disk = json.loads((Path(tmp) / "state.json").read_text())
                self.assertEqual(next(iter(on_disk["items"].values()))["status"], "pending")
                return {"message_id": 1}
            with patch.object(bot, "telegram", side_effect=check):
                bot.publish(self.products, self.config, self.state, "secret", "@test", False)
            self.assertEqual(next(iter(json.loads((Path(tmp) / "state.json").read_text())["items"].values()))["status"], "sent")


if __name__ == "__main__":
    unittest.main()
