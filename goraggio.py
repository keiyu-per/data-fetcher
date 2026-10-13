#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""GORAGGIOの保存HTMLを解析するオフラインツール。

店舗は環境変数または対話選択で確定する。サイトへ自動アクセスせず、
利用権限のある保存HTMLまたは正規エクスポートだけを入力にする。

Examples:
    python goraggio.py --self-test
    GORAGGIO_SHOP_ID=100831 GORAGGIO_SHOP_NAME='ピーアーク北千住SSS' \
      python goraggio.py all --list-html all_list.html --csv all_machines.csv
    python goraggio.py 2002 --shop トリエス --detail-html 100831_2002.html
    python goraggio.py --show-shops
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse


SHOP_ID_ENV = "GORAGGIO_SHOP_ID"
SHOP_NAME_ENV = "GORAGGIO_SHOP_NAME"
EXPECTED_COUNT_ENV = "GORAGGIO_EXPECTED_COUNT"
VERSION = "2.1.1"

# GORAGGIO公式ページで2026-09-03に確認した候補値。
# 実データ取得前にはページ名を再照合し、変更されていれば環境変数を優先する。
KNOWN_SHOPS: tuple[dict[str, Any], ...] = (
    {
        "key": "p-ark-kitasenju-sss",
        "name": "ピーアーク北千住SSS",
        "shop_id": "100831",
        "aliases": ("ピーアーク北千住sss", "北千住sss", "トリエス", "triple s"),
        "verified_on": "2026-09-03",
    },
    {
        "key": "p-ark-takenotsuka-studio",
        "name": "ピーアーク竹ノ塚スタジオ",
        "shop_id": "100883",
        "aliases": ("ピーアーク竹ノ塚", "ピーアーク竹ノ塚スタジオ", "竹ノ塚スタジオ"),
        "verified_on": "2026-09-03",
    },
    {
        "key": "concert-hall-kitasenju",
        "name": "コンサートホール北千住",
        "shop_id": "100983",
        "aliases": ("コンサートホール北千住", "コンサ北千住", "コンサートホール"),
        "verified_on": "2026-09-03",
    },
)


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def label_key(value: Any) -> str:
    return re.sub(r"[\s:：/／・()（）_-]+", "", norm(value)).lower()


def to_int(value: Any) -> int | None:
    text = norm(value).translate(str.maketrans({"−": "-", "－": "-", "＋": "+"}))
    match = re.search(r"[-+]?\d[\d,]*", text)
    return int(match.group(0).replace(",", "")) if match else None


def to_float(value: Any) -> float | None:
    text = norm(value).translate(str.maketrans({"−": "-", "－": "-", "＋": "+"}))
    match = re.search(r"[-+]?(?:\d[\d,]*)?(?:\.\d+)|[-+]?\d[\d,]*", text)
    return float(match.group(0).replace(",", "")) if match else None


def parse_units(spec: str) -> list[str] | None:
    """台番号指定を解析する。allはNone（全件）を返す。"""
    spec = norm(spec)
    if not spec or spec.lower() in {"all", "*", "全台"}:
        return None
    match = re.fullmatch(r"(\d+)\s*[-~〜]\s*(\d+)", spec)
    if match:
        start, end = map(int, match.groups())
        if start > end:
            start, end = end, start
        return [str(unit) for unit in range(start, end + 1)]
    if re.fullmatch(r"\d+", spec):
        return [spec]
    parts = [part.strip() for part in re.split(r"[,、]", spec)]
    if parts and all(re.fullmatch(r"\d+", part) for part in parts):
        return list(dict.fromkeys(parts))
    raise ValueError("台番号は 2002 / 2001-2020 / 2001,2002 / all の形式で指定")


def shop_key(value: Any) -> str:
    return re.sub(r"[\s　・･_-]+", "", norm(value)).lower()


def find_known_shop(value: Any) -> dict[str, Any] | None:
    wanted = shop_key(value)
    if not wanted:
        return None
    for shop in KNOWN_SHOPS:
        candidates = (shop["key"], shop["name"], *shop["aliases"])
        if any(wanted == shop_key(candidate) for candidate in candidates):
            return shop
    return None


def find_known_shop_by_id(shop_id: Any) -> dict[str, Any] | None:
    wanted = norm(shop_id)
    return next((shop for shop in KNOWN_SHOPS if shop["shop_id"] == wanted), None)


def validate_shop_id(value: Any) -> str:
    shop_id = norm(value)
    if not re.fullmatch(r"\d{4,10}", shop_id):
        raise ValueError("店舗IDはGORAGGIO URL内の4〜10桁の数字で指定してください")
    return shop_id


@dataclass(frozen=True)
class ShopSelection:
    name: str
    shop_id: str
    source: str
    verified_on: str | None = None


def selection_from_known(shop: dict[str, Any], source: str) -> ShopSelection:
    return ShopSelection(
        name=shop["name"],
        shop_id=shop["shop_id"],
        source=source,
        verified_on=shop.get("verified_on"),
    )


def prompt_shop(input_fn=input, output=sys.stdout) -> ShopSelection:
    print("対象店舗を選択してください:", file=output)
    for index, shop in enumerate(KNOWN_SHOPS, start=1):
        print(f"  {index}. {shop['name']}", file=output)
    print(f"  {len(KNOWN_SHOPS) + 1}. その他", file=output)

    try:
        answer = norm(input_fn("番号: "))
    except EOFError as exc:
        raise ValueError(
            f"店舗を選択できません。{SHOP_ID_ENV}と{SHOP_NAME_ENV}を設定してください"
        ) from exc
    if answer.isdigit() and 1 <= int(answer) <= len(KNOWN_SHOPS):
        return selection_from_known(KNOWN_SHOPS[int(answer) - 1], "対話選択")
    if answer == str(len(KNOWN_SHOPS) + 1):
        name = norm(input_fn("公式ページと住所を照合した店舗名: "))
        shop_id = validate_shop_id(input_fn("GORAGGIO店舗ID: "))
        if not name:
            raise ValueError("店舗名を入力してください")
        return ShopSelection(name=name, shop_id=shop_id, source="対話入力")
    raise ValueError("店舗の選択番号が正しくありません")


def resolve_shop(
    shop_name: str | None = None,
    shop_id: str | None = None,
    *,
    allow_prompt: bool = True,
    environ: dict[str, str] | os._Environ[str] | None = None,
    input_fn=input,
    output=sys.stdout,
) -> ShopSelection:
    """明示指定→環境変数→対話入力の順で店舗を確定する。"""
    env = os.environ if environ is None else environ
    explicit_name = norm(shop_name)
    explicit_id = validate_shop_id(shop_id) if norm(shop_id) else None
    env_name = norm(env.get(SHOP_NAME_ENV))
    env_id = validate_shop_id(env.get(SHOP_ID_ENV)) if norm(env.get(SHOP_ID_ENV)) else None

    requested_name = explicit_name or env_name
    known_from_name = find_known_shop(requested_name)

    if explicit_id:
        known_from_id = find_known_shop_by_id(explicit_id)
        if known_from_name and known_from_id and known_from_name["key"] != known_from_id["key"]:
            raise ValueError(
                f"店舗名「{requested_name}」と店舗ID「{explicit_id}」が登録情報と一致しません"
            )
        if known_from_id:
            selection = selection_from_known(known_from_id, "--shop-id")
        else:
            selection = ShopSelection(
                known_from_name["name"] if known_from_name else requested_name or f"店舗ID {explicit_id}",
                explicit_id,
                "--shop-id（検索確認値）",
            )
    elif explicit_name:
        known_from_env_id = find_known_shop_by_id(env_id) if env_id else None
        if known_from_name and known_from_env_id and known_from_name["key"] != known_from_env_id["key"]:
            raise ValueError(
                f"店舗名「{explicit_name}」と{SHOP_ID_ENV}が異なる登録店舗を指しています"
            )
        if env_id:
            selection = ShopSelection(
                known_from_name["name"] if known_from_name else explicit_name,
                env_id,
                f"--shop + {SHOP_ID_ENV}",
                known_from_env_id.get("verified_on") if known_from_env_id else None,
            )
        elif known_from_name:
            selection = selection_from_known(known_from_name, "--shop（登録候補値）")
        else:
            raise ValueError(
                f"未登録店舗「{explicit_name}」です。公式ページと住所を検索で照合し、"
                f"{SHOP_ID_ENV}へ店舗IDを設定してください"
            )
    elif env_id:
        known_from_id = find_known_shop_by_id(env_id)
        if known_from_name and known_from_id and known_from_name["key"] != known_from_id["key"]:
            raise ValueError(
                f"{SHOP_NAME_ENV}と{SHOP_ID_ENV}が異なる店舗を指しています"
            )
        if known_from_id:
            selection = selection_from_known(known_from_id, SHOP_ID_ENV)
        else:
            selection = ShopSelection(
                known_from_name["name"] if known_from_name else env_name or f"店舗ID {env_id}",
                env_id,
                f"{SHOP_ID_ENV}（検索確認値）",
            )
    elif env_name and known_from_name:
        selection = selection_from_known(known_from_name, SHOP_NAME_ENV)
    elif env_name:
        raise ValueError(
            f"未登録店舗「{env_name}」です。公式ページと住所を検索で照合し、"
            f"{SHOP_ID_ENV}も設定してください"
        )
    elif allow_prompt:
        selection = prompt_shop(input_fn=input_fn, output=output)
    else:
        raise ValueError(
            f"店舗が未指定です。{SHOP_ID_ENV}と{SHOP_NAME_ENV}を設定してください"
        )

    # 子プロセス内で選択を固定する。親シェルの環境変数は変更しない。
    env[SHOP_ID_ENV] = selection.shop_id
    env[SHOP_NAME_ENV] = selection.name
    return selection


def expected_count_from_env(environ: dict[str, str] | os._Environ[str] | None = None) -> int | None:
    env = os.environ if environ is None else environ
    value = norm(env.get(EXPECTED_COUNT_ENV))
    if not value:
        return None
    count = to_int(value)
    if count is None or count <= 0:
        raise ValueError(f"{EXPECTED_COUNT_ENV}は1以上の整数で指定してください")
    return count


def print_known_shops(output=sys.stdout) -> None:
    print("店舗名\t店舗ID\t確認日", file=output)
    for shop in KNOWN_SHOPS:
        print(f"{shop['name']}\t{shop['shop_id']}\t{shop['verified_on']}", file=output)


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    parent: "Node | None" = None
    children: list["Node | str"] = field(default_factory=list)

    def text(self) -> str:
        chunks: list[str] = []

        def walk(node: "Node") -> None:
            for child in node.children:
                if isinstance(child, str):
                    chunks.append(child)
                else:
                    walk(child)

        walk(self)
        return norm(" ".join(chunks))

    def descendants(self, tags: set[str] | None = None) -> Iterable["Node"]:
        for child in self.children:
            if isinstance(child, Node):
                if tags is None or child.tag in tags:
                    yield child
                yield from child.descendants(tags)


class DOMParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag.lower(), {key.lower(): value or "" for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if node.tag not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag.lower():
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(data)


def parse_dom(html: str) -> Node:
    parser = DOMParser()
    parser.feed(html)
    parser.close()
    return parser.root


def direct_cells(row: Node) -> list[Node]:
    return [child for child in row.children if isinstance(child, Node) and child.tag in {"th", "td"}]


def extract_pairs(root: Node) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for row in root.descendants({"tr"}):
        cells = [cell.text() for cell in direct_cells(row)]
        for index in range(0, len(cells) - 1, 2):
            if cells[index] and cells[index + 1]:
                pairs.setdefault(cells[index], cells[index + 1])

    for parent in [root, *root.descendants()]:
        children = [child for child in parent.children if isinstance(child, Node)]
        for index, child in enumerate(children):
            if child.tag != "dt":
                continue
            for sibling in children[index + 1:]:
                if sibling.tag == "dd":
                    key, value = child.text(), sibling.text()
                    if key and value:
                        pairs.setdefault(key, value)
                    break
                if sibling.tag == "dt":
                    break
    return pairs


def find_value(pairs: dict[str, str], labels: list[str]) -> str | None:
    keyed = [(label_key(key), value) for key, value in pairs.items()]
    for label in labels:
        wanted = label_key(label)
        for key, value in keyed:
            if key == wanted:
                return value
    return None


def regex_value(text: str, labels: list[str], decimal: bool = False) -> str | None:
    number = r"[-+＋－−]?(?:\d[\d,]*)(?:\.\d+)?" if decimal else r"[-+＋－−]?\d[\d,]*"
    pattern = rf"(?:{'|'.join(re.escape(label) for label in labels)})\s*[:：]?\s*({number})"
    match = re.search(pattern, norm(text), re.IGNORECASE)
    return match.group(1) if match else None


def first_nonempty(*values: Any) -> Any:
    return next((value for value in values if value not in (None, "")), None)


def detail_unit_from_root(root: Node) -> str | None:
    for node in root.descendants({"a"}):
        unit = unit_from_href(node.attrs.get("href", ""))
        if unit:
            return unit
    text = root.text()
    match = re.search(r"(?:台番号|台番)\s*[:：]?\s*(\d+)", text)
    return match.group(1) if match else None


def unit_from_href(href: str) -> str | None:
    if "detail" not in href:
        return None
    query = parse_qs(urlparse(href).query)
    unit = query.get("unit", [None])[0]
    return str(unit) if unit and str(unit).isdigit() else None


def find_meta_content(root: Node, keys: set[str]) -> str | None:
    for node in root.descendants({"meta"}):
        name = label_key(node.attrs.get("name") or node.attrs.get("property"))
        if name in keys and node.attrs.get("content"):
            return norm(node.attrs["content"])
    return None


def extract_history(root: Node) -> list[dict[str, str]]:
    histories: list[dict[str, str]] = []
    for table in root.descendants({"table"}):
        rows = list(table.descendants({"tr"}))
        headers: list[str] | None = None
        for row in rows:
            cells = direct_cells(row)
            values = [cell.text() for cell in cells]
            if not values:
                continue
            if any(cell.tag == "th" for cell in cells):
                if any(any(word in value for word in ("時刻", "時間", "種別", "当り", "大当")) for value in values):
                    headers = values
                continue
            if headers and len(values) == len(headers):
                histories.append({headers[index]: value for index, value in enumerate(values)})
    return histories


def page_state_without_data(text: str, has_data: bool) -> tuple[str, str | None]:
    """保存された表示内容を分類する。実際のHTTP状態や接続原因は推定しない。"""
    if has_data:
        return "data", None
    if re.search(r"\b502\s+Bad\s+Gateway\b", text, re.IGNORECASE):
        return "gateway_error_page", "502 Bad Gatewayの表示です。台データではありません。発生元・原因は未特定です"
    if re.search(r"(?:利用)?規約に同意する", text):
        return "consent_page", "規約画面のみで、台データは含まれていません"
    return "no_data", None


def current_timestamp(text: str) -> str | None:
    match = re.search(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}\s+\d{1,2}:\d{2})\s*現在", text)
    return match.group(1) if match else None


def parse_detail_html(
    html: str,
    unit: str | None = None,
    source: str = "",
    shop_id: str | None = None,
) -> dict[str, Any]:
    root = parse_dom(html)
    text = root.text()
    pairs = extract_pairs(root)
    unit = unit or detail_unit_from_root(root)

    title = next((node.text() for node in root.descendants({"title"}) if node.text()), None)
    description = find_meta_content(root, {"description", "ogdescription"})
    model = find_value(pairs, ["機種名", "機種"])
    if model is None:
        for candidate in (title, description):
            is_known_shop_title = candidate and any(
                shop_key(shop["name"]) in shop_key(candidate) for shop in KNOWN_SHOPS
            )
            if candidate and not is_known_shop_title and "台データオンライン" not in candidate:
                model = candidate.split("|")[0].strip()
                break

    def integer(labels: list[str]) -> int | None:
        return to_int(first_nonempty(find_value(pairs, labels), regex_value(text, labels)))

    date = find_value(pairs, ["対象日", "日付", "営業日"])
    if date is None:
        # Prefer visible page timestamps over arbitrary numbers in ad scripts.
        candidate = current_timestamp(text) or text
        match = re.search(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", candidate)
        date = match.group(0) if match else None
    updated_at = find_value(pairs, ["更新日時", "データ更新日時", "更新時刻"])
    if updated_at is None:
        match = re.search(r"(?:データ)?更新(?:日時|時刻)?\s*[:：]?\s*((?:20\d{2}[./-])?\d{1,2}[./-]\d{1,2}\s+\d{1,2}:\d{2}|\d{1,2}:\d{2})", text)
        updated_at = match.group(1) if match else current_timestamp(text)

    total_games = integer(["累計スタート", "総回転数", "総回転", "総ゲーム数", "ゲーム数"])
    big = integer(["BIG回数", "BIG", "BB回数", "BB"])
    reg = integer(["REG回数", "REG", "RB回数", "RB"])
    art = integer(["ART回数", "ART", "AT回数", "AT"])
    current_start = integer(["スタート回数", "現在スタート", "現在ゲーム数"])
    previous_final_start = integer(["前日最終スタート", "前日最終ゲーム数", "最終ゲーム数"])
    max_holdings = integer(["最大持ち玉", "最大持玉", "最大獲得", "最高獲得"])
    difference = integer(["差枚数", "差枚", "差玉数", "差玉"])
    first_hits = integer(["初当たり", "初当り", "初当たり回数"])
    payout_raw = first_nonempty(
        find_value(pairs, ["出玉率", "機械割"]),
        regex_value(text, ["出玉率", "機械割"], decimal=True),
    )
    payout_rate = to_float(payout_raw)

    warnings: list[str] = []
    page_state, page_warning = page_state_without_data(
        text, total_games is not None or current_start is not None
    )
    if page_warning:
        warnings.append(page_warning)
    if unit is None:
        warnings.append("台番号を特定できません")
    if total_games is None and current_start is None:
        warnings.append("回転数を特定できません")

    result: dict[str, Any] = {
        "shop_id": shop_id,
        "unit": unit,
        "source": source,
        "page_state": page_state,
        "model": model,
        "date": date,
        "updated_at": updated_at,
        "total_games": total_games,
        "current_start": current_start,
        "previous_final_start": previous_final_start,
        "big": big,
        "reg": reg,
        "art_at": art,
        "first_hits": first_hits,
        "max_holdings": max_holdings,
        "difference": difference,
        "payout_rate": payout_rate,
        "hit_history": extract_history(root),
        "warnings": warnings,
    }
    result["big_probability"] = total_games / big if total_games is not None and big and big > 0 else None
    result["reg_probability"] = total_games / reg if total_games is not None and reg and reg > 0 else None
    result["combined_probability"] = (
        total_games / (big + reg)
        if total_games is not None and big is not None and reg is not None and big + reg > 0
        else None
    )
    return result


LIST_LABELS = {
    "unit": ["台番号", "台番"],
    "model": ["機種名", "機種"],
    "current_start": ["スタート回数", "現在スタート", "現在ゲーム数", "スタート"],
    "big": ["BIG回数", "BIG", "BB回数", "BB"],
    "reg": ["REG回数", "REG", "RB回数", "RB"],
    "art_at": ["ART回数", "ART", "AT回数", "AT"],
    "previous_final_start": ["前日最終スタート", "前日最終ゲーム数"],
}


def header_field(header: str) -> str | None:
    key = label_key(header)
    for field_name, labels in LIST_LABELS.items():
        if any(key == label_key(label) for label in labels):
            return field_name
    return None


def record_from_table_row(headers: list[str], values: list[str], row: Node) -> dict[str, Any] | None:
    record: dict[str, Any] = {}
    for header, value in zip(headers, values):
        field_name = header_field(header)
        if field_name:
            record[field_name] = value if field_name == "model" else to_int(value)
    for link in row.descendants({"a"}):
        unit = unit_from_href(link.attrs.get("href", ""))
        if unit:
            record["unit"] = unit
            record["detail_href"] = link.attrs.get("href")
            break
    if record.get("unit") is None:
        return None
    record["unit"] = str(record["unit"])
    return record


def smallest_unit_context(link: Node, unit: str) -> Node:
    best = link
    node = link.parent
    while node is not None and node.tag != "document":
        text = node.text()
        if unit in text and any(label in text for label in ("スタート", "BB", "RB", "ART", "AT")):
            best = node
            if len(text) > 1200:
                break
        node = node.parent
    return best


def record_from_context(context: Node, unit: str, href: str) -> dict[str, Any]:
    text = context.text()
    pairs = extract_pairs(context)
    record: dict[str, Any] = {"unit": unit, "detail_href": href}
    for field_name, labels in LIST_LABELS.items():
        if field_name == "unit":
            continue
        value = first_nonempty(find_value(pairs, labels), regex_value(text, labels))
        record[field_name] = norm(value) if field_name == "model" and value else to_int(value)
    return record


def merge_record(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if merged.get(key) in (None, "") and value not in (None, ""):
            merged[key] = value
    return merged


def detect_slot_count(text: str) -> int | None:
    patterns = (
        r"(?:Slot\s*)?スロット\s*[|｜]?\s*(\d[\d,]*)\s*台",
        r"スロット(?:導入)?台数\s*[:：]?\s*(\d[\d,]*)\s*台?",
    )
    for pattern in patterns:
        match = re.search(pattern, norm(text), re.IGNORECASE)
        if match:
            return to_int(match.group(1))
    return None


def parse_list_html(
    html: str,
    shop_id: str,
    expected_count: int | None = None,
    source: str = "",
) -> dict[str, Any]:
    root = parse_dom(html)
    text = root.text()
    records: dict[str, dict[str, Any]] = {}

    for table in root.descendants({"table"}):
        headers: list[str] | None = None
        for row in table.descendants({"tr"}):
            cells = direct_cells(row)
            values = [cell.text() for cell in cells]
            if not values:
                continue
            if any(cell.tag == "th" for cell in cells) and any(header_field(value) for value in values):
                headers = values
                continue
            if headers and len(headers) == len(values):
                record = record_from_table_row(headers, values, row)
                if record:
                    unit = record["unit"]
                    records[unit] = merge_record(records.get(unit, {}), record)

    for link in root.descendants({"a"}):
        href = link.attrs.get("href", "")
        unit = unit_from_href(href)
        if not unit:
            continue
        context = smallest_unit_context(link, unit)
        record = record_from_context(context, unit, href)
        records[unit] = merge_record(records.get(unit, {}), record)

    # Prefer an explicit date selected in the list's "hist_num" dropdown.
    # Fallback to the on-page update timestamp, not arbitrary numbers in scripts.
    selected_date = None
    for select in root.descendants({"select"}):
        if select.attrs.get("name") != "hist_num":
            continue
        for option in select.descendants({"option"}):
            if "selected" in option.attrs:
                candidate = re.search(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", option.text())
                if candidate:
                    selected_date = candidate.group(0)
                    break
        if selected_date:
            break
    date_match = re.search(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}",
                           current_timestamp(text) or "")
    update_match = re.search(
        r"(?:データ)?更新(?:日時|時刻)?\s*[:：]?\s*((?:20\d{2}[./-])?\d{1,2}[./-]\d{1,2}\s+\d{1,2}:\d{2}|\d{1,2}:\d{2})",
        text,
    )
    rows = [records[unit] for unit in sorted(records, key=lambda value: int(value))]
    page_slot_count = detect_slot_count(text)
    resolved_expected_count = page_slot_count if page_slot_count is not None else expected_count
    count_source = "ページ表示" if page_slot_count is not None else "指定値" if expected_count is not None else None
    warnings: list[str] = []
    page_state, page_warning = page_state_without_data(text, bool(rows))
    if page_warning:
        warnings.append(page_warning)
    if resolved_expected_count is None:
        warnings.append("設置台数を特定できないため、全台取得を判定できません")
    else:
        if expected_count is not None and page_slot_count is not None and expected_count != page_slot_count:
            warnings.append(
                f"指定した設置台数{expected_count}台よりページ表示{page_slot_count}台を優先しました"
            )
        if len(rows) != resolved_expected_count:
            warnings.append(
                f"取得件数は{len(rows)}台で、期待値{resolved_expected_count}台と一致しません"
            )

    return {
        "shop_id": str(shop_id),
        "source": source,
        "page_state": page_state,
        "date": selected_date or (date_match.group(0) if date_match else None),
        "updated_at": update_match.group(1) if update_match else current_timestamp(text),
        "expected_count": resolved_expected_count,
        "expected_count_source": count_source,
        "page_slot_count": page_slot_count,
        "parsed_count": len(rows),
        "coverage_complete": (
            resolved_expected_count is not None and len(rows) == resolved_expected_count
        ),
        "rows": rows,
        "warnings": warnings,
    }


def load_html(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def detail_path_for(directory: Path, shop_id: str, unit: str) -> Path | None:
    candidates = [
        directory / f"{shop_id}_{unit}.html",
        directory / f"{unit}.html",
        directory / f"detail_{unit}.html",
    ]
    return next((path for path in candidates if path.is_file()), None)


def probability_text(value: Any) -> str:
    return f"1/{value:.1f}" if isinstance(value, (int, float)) and value > 0 else "取得不可"


def print_detail(row: dict[str, Any]) -> None:
    print("=" * 50)
    print("台番号:", row.get("unit") or "取得不可")
    print("機種:", row.get("model") or "取得不可")
    print("対象日:", row.get("date") or "取得不可")
    print("累計スタート:", row.get("total_games") if row.get("total_games") is not None else "取得不可")
    print("現在スタート:", row.get("current_start") if row.get("current_start") is not None else "取得不可")
    print("BIG:", row.get("big") if row.get("big") is not None else "取得不可")
    print("REG:", row.get("reg") if row.get("reg") is not None else "取得不可")
    print("ART/AT:", row.get("art_at") if row.get("art_at") is not None else "取得不可")
    print("BIG確率:", probability_text(row.get("big_probability")))
    print("REG確率:", probability_text(row.get("reg_probability")))
    print("合算:", probability_text(row.get("combined_probability")))
    for warning in row.get("warnings", []):
        print("警告:", warning)


def csv_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
        for key, value in row.items()
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("CSVへ出力できる台データがありません")
    flattened = [csv_safe_row(row) for row in rows]
    fieldnames = list(dict.fromkeys(key for row in flattened for key in row))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flattened)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_self_test() -> None:
    # 通信は行わない。実際に観測した表示形式を合成HTMLで再現する回帰テスト。
    for phrase in ("規約に同意する", "利用規約に同意する"):
        html = f"<button>{phrase}</button>"
        assert parse_list_html(html, "100983")["page_state"] == "consent_page"
        assert parse_detail_html(html, "638", shop_id="100983")["page_state"] == "consent_page"
    gateway = "<h1>502 Bad Gateway</h1><p>connection closed</p>"
    assert parse_list_html(gateway, "100983")["page_state"] == "gateway_error_page"
    assert parse_detail_html(gateway, "638", shop_id="100983")["page_state"] == "gateway_error_page"
    timestamp = "<p>2026.09.25 18:00現在</p>"
    assert parse_list_html(timestamp, "100983")["updated_at"] == "2026.09.25 18:00"
    assert parse_detail_html(timestamp, "638", shop_id="100983")["updated_at"] == "2026.09.25 18:00"
    assert page_state_without_data("規約に同意する", True) == ("data", None)
    assert parse_units("2002") == ["2002"]
    assert parse_units("2003-2001") == ["2001", "2002", "2003"]
    assert parse_units("2001、2002") == ["2001", "2002"]
    assert parse_units("all") is None
    assert to_int("−1,234枚") == -1234
    assert detect_slot_count("Slotスロット | 461台") == 461
    assert find_known_shop("トリエス")["shop_id"] == "100831"
    assert find_known_shop("ピーアーク竹ノ塚")["shop_id"] == "100883"
    assert find_known_shop("コンサ北千住")["shop_id"] == "100983"
    selected = resolve_shop(
        allow_prompt=False,
        environ={SHOP_ID_ENV: "100983", SHOP_NAME_ENV: "コンサートホール北千住"},
    )
    assert selected.shop_id == "100983"
    changed_id = resolve_shop(
        "トリエス",
        allow_prompt=False,
        environ={SHOP_ID_ENV: "999999"},
    )
    assert changed_id.name == "ピーアーク北千住SSS"
    assert changed_id.shop_id == "999999"

    detail = """
    <html><head><title>マイジャグラーV | 台データ</title></head><body>
      <table>
        <tr><th>台番号</th><td>2002</td></tr>
        <tr><th>累計スタート</th><td>6,000</td></tr>
        <tr><th>スタート回数</th><td>137</td></tr>
        <tr><th>BB</th><td>30</td></tr><tr><th>RB</th><td>25</td></tr>
        <tr><th>差枚</th><td>+1,234枚</td></tr>
      </table>
    </body></html>
    """
    parsed_detail = parse_detail_html(detail, "2002", "self-test", "100831")
    assert parsed_detail["shop_id"] == "100831"
    assert parsed_detail["total_games"] == 6000
    assert parsed_detail["current_start"] == 137
    assert parsed_detail["big"] == 30 and parsed_detail["reg"] == 25
    assert round(parsed_detail["combined_probability"], 2) == round(6000 / 55, 2)

    rows = []
    expected_count = 450
    for unit in range(1, expected_count + 1):
        rows.append(
            f'<tr><td><a href="/100831/detail?unit={unit}">{unit}</a></td>'
            f'<td>機種{unit}</td><td>{unit % 300}</td><td>{unit % 20}</td>'
            f'<td>{unit % 15}</td><td>{unit % 10}</td><td>{unit % 100}</td></tr>'
        )
    listing = (
        "<html><body><p>データ更新日時：2026/09/03 12:34</p>"
        "<p>Slotスロット | 450台</p><table>"
        "<tr><th>台番号</th><th>機種名</th><th>スタート回数</th><th>BB</th>"
        "<th>RB</th><th>ART</th><th>前日最終スタート</th></tr>"
        + "".join(rows)
        + "</table></body></html>"
    )
    parsed_list = parse_list_html(listing, shop_id="100831", source="self-test")
    assert parsed_list["parsed_count"] == expected_count
    assert parsed_list["expected_count"] == expected_count
    assert parsed_list["expected_count_source"] == "ページ表示"
    assert parsed_list["coverage_complete"] is True
    assert parsed_list["rows"][1]["unit"] == "2"
    assert parsed_list["rows"][1]["model"] == "機種2"
    page_wins = parse_list_html(
        listing,
        shop_id="100831",
        expected_count=999,
        source="self-test",
    )
    assert page_wins["expected_count"] == 450
    assert any("ページ表示450台を優先" in warning for warning in page_wins["warnings"])
    print("SELF-TEST OK (店舗選択・可変台数一覧・詳細・数値変換)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GORAGGIOの保存HTMLをオフライン解析します（ネットワークアクセスは行いません）"
    )
    parser.add_argument("units", nargs="?", default="all", help="2002 / 2001-2020 / 2001,2002 / all")
    parser.add_argument("--shop", help="店舗名または登録済みの別名。例: トリエス")
    parser.add_argument("--shop-id", help=f"明示指定。通常は{SHOP_ID_ENV}を使用")
    parser.add_argument("--no-shop-prompt", action="store_true", help="店舗未指定時に対話入力せず終了")
    parser.add_argument("--show-shops", action="store_true", help="登録済み3店舗を表示して終了")
    parser.add_argument("--list-html", type=Path, help="保存した全台一覧HTML")
    parser.add_argument("--detail-html", type=Path, help="保存した単台詳細HTML")
    parser.add_argument("--detail-dir", type=Path, help="複数の詳細HTMLを置いたディレクトリ")
    parser.add_argument(
        "--expected-count",
        type=int,
        help=f"設置台数。省略時はHTMLから検出し、{EXPECTED_COUNT_ENV}も利用可能",
    )
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--strict", action="store_true", help="欠損または全台不足を終了コード2にする")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.show_shops:
        print_known_shops()
        return 0
    if args.self_test:
        run_self_test()
        return 0
    try:
        shop = resolve_shop(
            args.shop,
            args.shop_id,
            allow_prompt=not args.no_shop_prompt,
        )
        expected_count = (
            args.expected_count
            if args.expected_count is not None
            else expected_count_from_env()
        )
    except ValueError as exc:
        parser.error(str(exc))
    if expected_count is not None and expected_count <= 0:
        parser.error("--expected-countは1以上の整数で指定してください")

    print(
        f"対象店舗: {shop.name} / GORAGGIO_SHOP_ID={shop.shop_id} / 選択元={shop.source}"
    )
    sources = [args.list_html, args.detail_html, args.detail_dir]
    if sum(source is not None for source in sources) != 1:
        parser.error("--list-html / --detail-html / --detail-dir のいずれか1つを指定してください")

    try:
        selected_units = parse_units(args.units)
    except ValueError as exc:
        parser.error(str(exc))

    strict_failure = False
    payload: Any
    rows: list[dict[str, Any]]

    if args.list_html:
        html = load_html(args.list_html)
        payload = parse_list_html(html, shop.shop_id, expected_count, str(args.list_html))
        rows = payload["rows"]
        if selected_units is not None:
            wanted = set(selected_units)
            rows = [row for row in rows if row.get("unit") in wanted]
        print(
            f"店舗ID={shop.shop_id} 解析={payload['parsed_count']}/{payload['expected_count'] or '?'}台 "
            f"全台確認={'済' if payload['coverage_complete'] else '未完了'}"
        )
        print("対象日:", payload.get("date") or "取得不可", "更新:", payload.get("updated_at") or "取得不可")
        for warning in payload["warnings"]:
            print("警告:", warning)
        strict_failure = not payload["coverage_complete"]
    elif args.detail_html:
        if selected_units is None or len(selected_units) != 1:
            parser.error("--detail-html では台番号を1台だけ指定してください")
        html = load_html(args.detail_html)
        row = parse_detail_html(html, selected_units[0], str(args.detail_html), shop.shop_id)
        rows = [row]
        payload = rows
        print_detail(row)
        strict_failure = bool(row["warnings"])
    else:
        if selected_units is None:
            parser.error("--detail-dir では対象台番号または範囲を指定してください")
        rows = []
        for unit in selected_units:
            path = detail_path_for(args.detail_dir, shop.shop_id, unit)
            if path is None:
                rows.append({
                    "shop_id": shop.shop_id,
                    "unit": unit,
                    "source": None,
                    "warnings": ["詳細HTMLが見つかりません"],
                })
                strict_failure = True
                continue
            row = parse_detail_html(load_html(path), unit, str(path), shop.shop_id)
            rows.append(row)
            if row["warnings"]:
                strict_failure = True
        payload = rows
        for row in rows:
            print_detail(row)

    if args.json:
        if args.list_html:
            output_payload = dict(payload)
            output_payload["rows"] = rows
        else:
            output_payload = payload
        write_json(args.json, output_payload)
    if args.csv:
        write_csv(args.csv, rows)

    return 2 if args.strict and strict_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())