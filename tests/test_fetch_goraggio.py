"""Tests use an in-memory fake response, not the live site."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import fetch_goraggio


class FakeHeaders:
    def get_content_type(self):
        return "text/html"


class FakeResponse:
    status = 200
    headers = FakeHeaders()

    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return "https://daidata.goraggio.com/100831/all_list?ps=S"

    def read(self, max_bytes):
        return self.content[:max_bytes]


class FetchTest(unittest.TestCase):
    def test_received_html_without_rows_is_not_success(self):
        with TemporaryDirectory() as d:
            with patch.object(fetch_goraggio, "urlopen", return_value=FakeResponse(b"<html><body>Sample</body></html>")):
                code = fetch_goraggio.fetch("p-ark-kitasenju-sss", Path(d))
            status = json.loads((Path(d) / "fetch_status.json").read_text())
            self.assertEqual(code, 2)
            self.assertEqual(status["result"], "html_received_but_no_machine_data")
            self.assertEqual(status["parsed_count"], 0)
            self.assertTrue((Path(d) / "all_list.html").exists())

    def test_blocked_request_has_diagnostic_not_html(self):
        from urllib.error import HTTPError
        with TemporaryDirectory() as d:
            with patch.object(fetch_goraggio, "urlopen", side_effect=HTTPError("http://example", 403, "Forbidden", {}, None)):
                code = fetch_goraggio.fetch("p-ark-kitasenju-sss", Path(d))
            status = json.loads((Path(d) / "fetch_status.json").read_text())
            self.assertEqual(code, 1)
            self.assertEqual(status["http_status"], 403)
            self.assertFalse((Path(d) / "all_list.html").exists())


if __name__ == "__main__":
    unittest.main()
