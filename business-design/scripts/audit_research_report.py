#!/usr/bin/env python3
"""Deterministically audit the effective length of a market research report."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


DEFAULT_MINIMUM = 10_000
DEFAULT_MAXIMUM = 15_000
COUNTING_METHOD = "CJK characters + Latin/alphanumeric word tokens in visible text"
MAX_DUPLICATE_CONTENT_RATIO = 0.25
MIN_UNIQUE_BODY_RATIO = 0.75
REFERENCE_HEADING_PATTERN = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*)?(?:参考文献|参考资料|来源清单|references?|bibliography)\s*:?[：]?\s*$",
    re.IGNORECASE,
)


class VisibleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def extract_html(path: Path) -> str:
    parser = VisibleHTMLParser()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parser.parts)


def extract_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            document = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"无法读取 DOCX: {exc}") from exc
    root = ElementTree.fromstring(document)
    paragraphs: list[str] = []
    for paragraph in root.iter():
        if not paragraph.tag.endswith("}p"):
            continue
        text = "".join(node.text or "" for node in paragraph.iter() if node.tag.endswith("}t"))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return extract_html(path)
    if suffix == ".docx":
        return extract_docx(path)
    if suffix in {".md", ".txt", ".json", ".csv"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(
        f"不支持 {suffix or '无扩展名'}；请使用 HTML、MD、TXT、JSON 或 DOCX。PDF 请先转换为可提取文本格式"
    )


def count_effective_length(text: str) -> dict[str, int]:
    cjk_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))
    latin_word_count = len(re.findall(r"[A-Za-z0-9]+(?:[._%+/-][A-Za-z0-9]+)*", text))
    return {
        "cjk_characters": cjk_count,
        "latin_alphanumeric_tokens": latin_word_count,
        "effective_count": cjk_count + latin_word_count,
    }


def split_body_references(text: str) -> tuple[str, str]:
    """Split at the first explicit reference-list heading, if present."""

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if REFERENCE_HEADING_PATTERN.match(line):
            return "\n".join(lines[:index]), "\n".join(lines[index + 1 :])
    return text, ""


def normalize_paragraph(paragraph: str) -> str:
    translations = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "％": "%"})
    return re.sub(r"\s+", "", paragraph.translate(translations)).strip()


def duplicate_metrics(body_text: str) -> dict[str, float | int]:
    paragraphs = [normalize_paragraph(part) for part in body_text.splitlines()]
    paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) >= 20]
    counts: dict[str, int] = {}
    for paragraph in paragraphs:
        counts[paragraph] = counts.get(paragraph, 0) + 1

    duplicate_paragraph_count = sum(count - 1 for count in counts.values() if count > 1)
    duplicate_effective_count = sum(
        (count - 1) * count_effective_length(paragraph)["effective_count"]
        for paragraph, count in counts.items()
        if count > 1
    )
    unique_effective_count = sum(
        count_effective_length(paragraph)["effective_count"] for paragraph in counts
    )
    body_effective_count = count_effective_length(body_text)["effective_count"]
    duplicate_ratio = (
        duplicate_effective_count / body_effective_count if body_effective_count else 0.0
    )
    unique_ratio = unique_effective_count / body_effective_count if body_effective_count else 1.0
    return {
        "duplicate_paragraph_count": duplicate_paragraph_count,
        "duplicate_content_ratio": round(duplicate_ratio, 4),
        "unique_body_ratio": round(unique_ratio, 4),
    }


def audit(path: Path, minimum: int = DEFAULT_MINIMUM, maximum: int = DEFAULT_MAXIMUM, *, advisory_length: bool = False) -> dict[str, Any]:
    text = extract_text(path)
    body_text, reference_text = split_body_references(text)
    body_counts = count_effective_length(body_text)
    reference_counts = count_effective_length(reference_text)
    length_passed = minimum <= body_counts["effective_count"] <= maximum
    metrics = duplicate_metrics(body_text)
    density_passed = (
        metrics["duplicate_content_ratio"] <= MAX_DUPLICATE_CONTENT_RATIO
        and metrics["unique_body_ratio"] >= MIN_UNIQUE_BODY_RATIO
    )
    return {
        "schema_version": "1.1",
        "report_path": str(path),
        "counting_method": COUNTING_METHOD,
        "cjk_characters": body_counts["cjk_characters"],
        "latin_alphanumeric_tokens": body_counts["latin_alphanumeric_tokens"],
        "effective_count": body_counts["effective_count"],
        "body_effective_count": body_counts["effective_count"],
        "reference_effective_count": reference_counts["effective_count"],
        "minimum": minimum,
        "maximum": maximum,
        **metrics,
        "thresholds": {
            "max_duplicate_content_ratio": MAX_DUPLICATE_CONTENT_RATIO,
            "min_unique_body_ratio": MIN_UNIQUE_BODY_RATIO,
        },
        "length_passed": length_passed,
        "density_passed": density_passed,
        "length_gate": not advisory_length,
        "passed": density_passed and (body_counts["effective_count"] > 0 if advisory_length else length_passed),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="审计市场洞察报告有效字数（默认 10000-15000）")
    parser.add_argument("report", type=Path, help="research_report.html/md/txt/json/docx")
    parser.add_argument("--output", type=Path, help="输出 research_report_audit.json")
    parser.add_argument("--minimum", type=int, default=DEFAULT_MINIMUM)
    parser.add_argument("--maximum", type=int, default=DEFAULT_MAXIMUM)
    parser.add_argument("--advisory-length", action="store_true", help="v3：字数仅诊断，保留非空正文与重复内容检查；充分性由独立评审判断")
    args = parser.parse_args()
    if args.minimum <= 0 or args.maximum < args.minimum:
        parser.error("minimum/maximum 范围无效")
    try:
        result = audit(args.report, args.minimum, args.maximum, advisory_length=args.advisory_length)
        if args.output:
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    except (OSError, ValueError) as exc:
        print(f"[FAIL] {exc}")
        return 1
    status = "PASS" if result["passed"] else "FAIL"
    print(
        f"[{status}] 有效正文 {result['body_effective_count']}，参考文献 {result['reference_effective_count']}，"
        f"要求 {result['minimum']}-{result['maximum']}；"
        f"重复占比 {result['duplicate_content_ratio']}，唯一正文占比 {result['unique_body_ratio']}"
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
