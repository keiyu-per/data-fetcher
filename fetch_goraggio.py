#!/usr/bin/env python3
"""Try to fetch one public GORAGGIO all-list page without bypassing access controls.

This is a proof of concept for GitHub Actions, not an automated browser.
It makes a single ordinary HTTP request per run. Authentication, terms
acceptance and CAPTCHA handling are intentionally out of scope.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from goraggio import KNOWN_SHOPS, load_html, parse_list_html

BASE_HOST = "daidata.goraggio.com"
MAX_HTML_BYTES = 5_000_000
SHOPS = {str(shop["key"]): shop for shop in KNOWN_SHOPS}


def write_status(path: Path, status: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch(shop_key: str, output_dir: Path, timeout: int = 25) -> int:
    shop = SHOPS[shop_key]
    shop_id = str(shop["shop_id"])
    url = f"https://{BASE_HOST}/{shop_id}/all_list?ps=S"
    output_dir.mkdir(parents=True, exist_ok=True)
    record: dict = {
        "shop": shop["name"],
        "shop_id": shop_id,
        "url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "result": "error",
    }
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "goraggio-data-fetcher/0.1 (personal data export test)",
                "Accept": "text/html,application/xhtml+xml",
            },
            method="GET",
        )
        with urlopen(request, timeout=timeout) as response:
            record["http_status"] = response.status
            final_url = response.geturl()
            if urlparse(final_url).hostname != BASE_HOST:
                raise ValueError("Redirected outside the expected GORAGGIO host")
            content_type = response.headers.get_content_type()
            record["content_type"] = content_type
            if content_type not in ("text/html", "application/xhtml+xml"):
                raise ValueError(f"Unexpected content type: {content_type}")
            raw = response.read(MAX_HTML_BYTES + 1)
            if len(raw) > MAX_HTML_BYTES:
                raise ValueError("HTML exceeds the 5 MB test limit")
        if not raw:
            raise ValueError("Empty response")
        html_path = output_dir / "all_list.html"
        html_path.write_bytes(raw)
        record["html_bytes"] = len(raw)
        parsed = parse_list_html(load_html(html_path), shop_id, source=str(html_path))
        record.update({
            "page_state": parsed.get("page_state"),
            "parsed_count": parsed["parsed_count"],
            "expected_count": parsed["expected_count"],
            "coverage_complete": parsed["coverage_complete"],
            "target_date": parsed["date"],
            "updated_at": parsed["updated_at"],
            "warnings": parsed["warnings"],
        })
        if parsed["parsed_count"] == 0:
            record["result"] = "html_received_but_no_machine_data"
            print("HTTP 200 HTML received, but no machine rows could be verified.", file=sys.stderr)
            return_code = 2
        else:
            record["result"] = "machine_data_found"
            print(f"HTTP {record['http_status']}: {parsed['parsed_count']} machine rows extracted")
            return_code = 0
    except HTTPError as exc:
        record["http_status"] = exc.code
        record["error"] = f"HTTP {exc.code}"
        print(f"Fetch blocked or failed: HTTP {exc.code}; no bypass attempted.", file=sys.stderr)
        return_code = 1
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        record["error"] = str(exc)
        print(f"Fetch failed: {exc}", file=sys.stderr)
        return_code = 1
    except Exception as exc:
        record["error"] = f"Unexpected parse error: {type(exc).__name__}: {exc}"
        print(record["error"], file=sys.stderr)
        return_code = 1
    finally:
        write_status(output_dir / "fetch_status.json", record)
    return return_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Test single-request GORAGGIO HTML retrieval")
    parser.add_argument("--shop", choices=tuple(SHOPS), required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--timeout", type=int, default=25)
    args = parser.parse_args()
    if args.timeout < 1 or args.timeout > 60:
        parser.error("--timeout must be between 1 and 60 seconds")
    return fetch(args.shop, args.output_dir, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
