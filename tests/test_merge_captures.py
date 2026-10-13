import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from merge_captures import parse_capture_files


SHOP = "100831"
SOURCE = "https://daidata.goraggio.com/100831/all_list?ps=S#df-export"

LIST = """<!doctype html><html><body>
<p>2026.10.13 11:14現在</p><p>スロット | 2台</p>
<table>
<thead><tr><th>台番号</th><th>機種名</th><th>スタート回数</th><th>BB回数</th><th>RB回数</th><th>ART回数</th></tr></thead>
<tbody>
<tr><td><a href="/100831/detail?unit=732">732</a></td><td>L東京喰種</td><td>25</td><td>2</td><td>1</td><td>4</td></tr>
<tr><td><a href="/100831/detail?unit=733">733</a></td><td>L東京喰種</td><td>92</td><td>1</td><td>0</td><td>2</td></tr>
</tbody></table></body></html>"""

def detail(unit, games):
    return (f'<!doctype html><html><body><p>台番号 {unit}</p><table>'
            f'<tr><th>累計スタート</th><td>{games}</td></tr>'
            '<tr><th>スタート回数</th><td>77</td></tr>'
            '<tr><th>BB</th><td>10</td></tr><tr><th>RB</th><td>8</td></tr>'
            '</table></body></html>')


def bundle(units=("732", "733")):
    return {
        "format": "goraggio-detail-bundle/v1",
        "shop_id": SHOP,
        "shop_name": "ピーアーク北千住SSS",
        "source_url": SOURCE,
        "target_date_label": "2026-10-13",
        "list_html": LIST,
        "requested_units": list(units),
        "details": [
            {"unit": u,
             "url": f"https://daidata.goraggio.com/100831/detail?unit={u}",
             "model": "L東京喰種",
             "html": detail(u, 1500 + int(u))}
            for u in units
        ],
        "errors": [],
    }


class CaptureBundleTests(unittest.TestCase):
    def test_full_detail_coverage(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "bundle.json"
            path.write_text(json.dumps(bundle(), ensure_ascii=False), encoding="utf-8")
            summary, rows = parse_capture_files([path])
            self.assertEqual(summary["observed_list_rows"], 2)
            self.assertEqual(summary["detail_units_captured"], 2)
            self.assertEqual(summary["detail_units_missing"], 0)
            self.assertEqual(summary["detail_total_games_present"], 2)
            self.assertEqual(rows[0]["unit"], "732")
            self.assertEqual(rows[0]["model"], "L東京喰種")
            self.assertEqual(rows[0]["detail_total_games"], 2232)
            self.assertTrue(rows[1]["detail_present"])

    def test_partial_coverage_is_explicit(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "partial.json"
            path.write_text(json.dumps(bundle(("732",)), ensure_ascii=False), encoding="utf-8")
            summary, rows = parse_capture_files([path])
            self.assertEqual(summary["detail_units_captured"], 1)
            self.assertEqual(summary["detail_units_missing"], 1)
            self.assertEqual(summary["detail_coverage_ratio"], 0.5)
            self.assertFalse(rows[1]["detail_present"])
            self.assertIsNone(rows[1]["detail_total_games"])

    def test_wrong_detail_url_is_rejected(self):
        with TemporaryDirectory() as temp:
            obj = bundle()
            obj["details"][0]["url"] = "https://example.com/other?unit=732"
            path = Path(temp) / "bad.json"
            path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source host"):
                parse_capture_files([path])

    def test_manual_detail_html_is_supported(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            list_path = base / "all_list.html"
            extra = base / "goraggio_100831_unit_732_2026.html"
            list_path.write_text(LIST, encoding="utf-8")
            extra.write_text(detail("732", 2500), encoding="utf-8")
            summary, rows = parse_capture_files([], list_path, [extra], SHOP)
            self.assertEqual(summary["detail_units_captured"], 1)
            self.assertEqual(rows[0]["detail_total_games"], 2500)


if __name__ == "__main__":
    unittest.main()
