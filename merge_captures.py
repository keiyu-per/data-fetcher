#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Combine locally captured GORAGGIO list + detail bundles without network access.

Do not treat list-only snapshots or missing detail fields as setting evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Any

from goraggio import parse_list_html, parse_detail_html, load_html, write_json, write_csv, detail_unit_from_root, parse_dom

FORMAT = "goraggio-detail-bundle/v1"
HOST = "daidata.goraggio.com"


def _check_source(url: str, shop_id: str, page: str, unit: str | None = None) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != HOST:
        raise ValueError("Unexpected GORAGGIO source host")
    if parsed.path.rstrip("/") != f"/{shop_id}/{page}":
        raise ValueError(f"Unexpected {page} source path")
    if unit is not None and parse_qs(parsed.query).get("unit", [None])[0] != unit:
        raise ValueError("Detail unit does not match its URL")


def _read_bundle(path: Path) -> dict[str, Any]:
    bundle = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict) or bundle.get("format") != FORMAT:
        raise ValueError(f"{path}: unsupported detail-bundle format")
    shop_id = str(bundle.get("shop_id", ""))
    if not shop_id.isdigit() or len(shop_id) > 10:
        raise ValueError(f"{path}: invalid shop ID")
    _check_source(str(bundle.get("source_url", "")), shop_id, "all_list")
    if not isinstance(bundle.get("list_html"), str) or "<html" not in bundle["list_html"].lower():
        raise ValueError(f"{path}: list HTML is missing")
    if not isinstance(bundle.get("details"), list):
        raise ValueError(f"{path}: details must be an array")
    if not isinstance(bundle.get("requested_units"), list):
        raise ValueError(f"{path}: requested_units must be an array")
    for detail in bundle["details"]:
        if not isinstance(detail, dict):
            raise ValueError(f"{path}: malformed detail entry")
        unit = str(detail.get("unit", ""))
        if not unit.isdigit():
            raise ValueError(f"{path}: invalid unit")
        _check_source(str(detail.get("url", "")), shop_id, "detail", unit)
        if not isinstance(detail.get("html"), str):
            raise ValueError(f"{path}: detail HTML is missing for {unit}")
    return bundle


def _merge_list_row_and_detail(list_row: dict, detail: dict | None) -> dict[str, Any]:
    """Distinguish list and detail fields; preserve null instead of guessing."""
    result = {
        "unit": list_row.get("unit"),
        "model": list_row.get("model"),
        "list_current_start": list_row.get("current_start"),
        "list_big": list_row.get("big"),
        "list_reg": list_row.get("reg"),
        "list_art_at": list_row.get("art_at"),
        "list_previous_final_start": list_row.get("previous_final_start"),
        "detail_present": detail is not None,
    }
    for key in (
        "date", "updated_at", "total_games", "current_start",
        "previous_final_start", "big", "reg", "art_at",
        "first_hits", "max_holdings", "difference", "payout_rate",
        "big_probability", "reg_probability", "combined_probability",
    ):
        result["detail_" + key] = detail.get(key) if detail else None
    result["hit_history_rows"] = len(detail.get("hit_history", [])) if detail else 0
    result["detail_page_state"] = detail.get("page_state") if detail else None
    return result


def parse_capture_files(
    bundle_paths: list[Path],
    list_html_path: Path | None = None,
    extra_detail_paths: list[Path] | None = None,
    shop_id: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bundles = [_read_bundle(path) for path in bundle_paths]
    if not bundles and list_html_path is None:
        raise ValueError("At least one bundle or a list HTML file is required")
    all_shop_ids = {str(bundle["shop_id"]) for bundle in bundles}
    if shop_id:
        all_shop_ids.add(str(shop_id))
    if len(all_shop_ids) != 1:
        raise ValueError("Do not merge captures from different shops")
    resolved_id = next(iter(all_shop_ids))
    _check_source("https://" + HOST + "/" + resolved_id + "/all_list", resolved_id, "all_list")
    if bundles:
        list_html = bundles[0]["list_html"]
        if list_html_path is not None:
            raise ValueError("Do not provide --list-html together with --bundle")
    else:
        list_html = load_html(list_html_path)
    listing = parse_list_html(list_html, resolved_id, source="Safari HTML snapshot")
    if listing["parsed_count"] == 0:
        raise ValueError("The list HTML contains zero parseable machine rows")

    warnings: list[str] = []
    warnings.extend(listing.get("warnings", []))
    dates = {x.get("target_date_label", "").strip() for x in bundles if x.get("target_date_label")}
    if len(dates) > 1:
        raise ValueError("Captures use inconsistent target dates; do not merge")
    if len({x.get("list_html", "") for x in bundles}) > 1:
        warnings.append("List HTML snapshots differ between bundles; machine counts may have changed")
    if listing.get("expected_count") is None:
        warnings.append("Official total machine count is not available in this snapshot")
    list_units = {str(row["unit"]) for row in listing["rows"]}
    details: dict[str, dict] = {}
    ignored_units: list[str] = []
    errors: list[Any] = []
    for bundle in bundles:
        if str(bundle["shop_id"]) != resolved_id:
            raise ValueError("Do not merge different shops")
        errors.extend(bundle.get("errors", []))
        for detail in bundle["details"]:
            unit = str(detail["unit"])
            if unit not in list_units:
                ignored_units.append(unit)
                continue
            parsed = parse_detail_html(detail["html"], unit=unit, shop_id=resolved_id,
                                       source=detail["url"])
            if parsed.get("page_state") != "data":
                warnings.append(f"Detail unit {unit} does not contain recognized data")
            elif unit in details:
                warnings.append(f"Duplicate detail unit {unit}; using last record")
            details[unit] = parsed

    for path in extra_detail_paths or []:
        content = load_html(path)
        root = parse_dom(content)
        # The page may contain links to *other* units. Prefer the exported filename.
        import re
        matched = re.search(r"(?:unit_|detail_)(\d+)", path.stem)
        unit = matched.group(1) if matched else detail_unit_from_root(root)
        if not unit or unit not in list_units:
            warnings.append(f"Skipped detail HTML with unknown unit: {path.name}")
            continue
        parsed = parse_detail_html(content, unit=unit, shop_id=resolved_id, source=str(path))
        if parsed.get("page_state") != "data":
            warnings.append(f"Manual detail HTML for unit {unit} has no recognized data")
        details[unit] = parsed

    usable_details = {unit: value for unit, value in details.items()
                      if value.get("page_state") == "data"}
    merged = [_merge_list_row_and_detail(row, usable_details.get(str(row["unit"])))
              for row in listing["rows"]]
    summary = {
        "shop_id": resolved_id,
        "shop_name": bundles[0].get("shop_name") if bundles else None,
        "list_target_date": listing.get("date"),
        "detail_target_date_labels": sorted(dates),
        "list_updated_at": listing.get("updated_at"),
        "observed_list_rows": len(listing["rows"]),
        "official_expected_count": listing.get("expected_count"),
        "list_official_coverage_confirmed": bool(listing.get("coverage_complete")),
        "detail_units_captured": len(usable_details),
        "detail_units_missing": len(list_units - usable_details.keys()),
        "detail_coverage_ratio": round(len(usable_details) / len(list_units), 5),
        "detail_total_games_present": sum(x.get("total_games") is not None for x in usable_details.values()),
        "detail_hit_history_present": sum(bool(x.get("hit_history")) for x in usable_details.values()),
        "ignored_unknown_units": ignored_units,
        "reported_retrieval_errors": errors,
        "warnings": warnings,
        "interpretation": "Data completeness report only; no setting inference.",
    }
    return summary, merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline GORAGGIO Safari HTML capture parser")
    parser.add_argument("--bundle", type=Path, action="append", default=[],
                        help="Download JSON from Safari; repeat for multiple batches")
    parser.add_argument("--list-html", type=Path, help="Separate all_list HTML instead of --bundle")
    parser.add_argument("--detail-html", type=Path, action="append", default=[],
                        help="Individual detail HTML, may be repeated")
    parser.add_argument("--shop-id", help="Required with --list-html; must match actual shop")
    parser.add_argument("--out-dir", type=Path, default=Path("output-merged"))
    args = parser.parse_args(argv)
    if args.list_html and not args.shop_id:
        parser.error("--shop-id is required with --list-html")
    try:
        summary, rows = parse_capture_files(args.bundle, args.list_html, args.detail_html, args.shop_id)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "coverage.json", summary)
    write_json(args.out_dir / "machines.json", rows)
    write_csv(args.out_dir / "machines.csv", rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["detail_units_captured"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
