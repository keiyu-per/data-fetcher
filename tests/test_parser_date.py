import unittest

from goraggio import parse_list_html, parse_detail_html


class PageDateTests(unittest.TestCase):
    def test_selected_day_beats_ad_script_noise(self):
        html = """<html><head><script>
            var adRatio = '54/18';
        </script></head><body>
          <p>2026.10.13 11:14現在</p>
          <select name="hist_num">
            <option value="0">2026-10-13</option>
            <option value="1" selected>2026-10-12</option>
          </select>
          <table><tr><th>台番号</th><th>機種名</th><th>スタート回数</th></tr>
          <tr><td><a href="/100831/detail?unit=732">732</a></td>
          <td>L東京喰種</td><td>123</td></tr></table>
        </body></html>"""
        p = parse_list_html(html, "100831")
        self.assertEqual(p["date"], "2026-10-12")
        self.assertEqual(p["updated_at"], "2026.10.13 11:14")
        self.assertEqual(p["parsed_count"], 1)

    def test_visible_timestamp_is_fallback(self):
        html = """<html><head><script>var fake = '54/18';</script></head>
        <body><time>2026.10.13 11:14現在</time>
          <table><tr><th>台番号</th><th>機種名</th></tr>
          <tr><td><a href="/100831/detail?unit=732">732</a></td>
          <td>L東京喰種</td></tr></table>
        </body></html>"""
        p = parse_list_html(html, "100831")
        self.assertEqual(p["date"], "2026.10.13")

    def test_detail_fallback_is_four_digit_year(self):
        html = """<html><head><script>var ratio = '54/18';</script></head>
        <body><time>2026.10.13 11:14現在</time>
        <table><tr><th>累計スタート</th><td>2000</td></tr></table></body></html>"""
        p = parse_detail_html(html, "732", shop_id="100831")
        self.assertEqual(p["date"], "2026.10.13")


if __name__ == "__main__":
    unittest.main()
