#!/usr/bin/env python3
"""Export a reviewed Markdown manuscript to a styled consulting DOCX.

Requires pandoc and python-docx. Supports embedded exhibit PNGs (relative
paths), a cover page, a TOC field and page-number footers; all layout chrome
is deterministic and inventoried. Conversion checks do not certify business
quality.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pandoc(*args: str) -> str:
    return subprocess.run(["pandoc", *args], check=True, capture_output=True,
                          text=True).stdout


def text_inventory(node) -> Counter:
    """Visible character inventory, independent of runs, wrapping and table widths.

    Intentionally not a semantic/order audit: independent review is still required.
    """
    if isinstance(node, list):
        result = Counter()
        for child in node:
            result.update(text_inventory(child))
        return result
    if isinstance(node, dict):
        kind, value = node.get("t"), node.get("c")
        if kind == "Str":
            return Counter(c for c in value if not c.isspace())
        if kind in {"Code", "CodeBlock", "Math"}:
            return Counter(c for c in value[-1] if not c.isspace())
        return text_inventory(value)
    return Counter()


def check_supported(node, source_dir: Path, images: dict[str, Path]) -> None:
    """Forbid raw HTML/TeX/math; allow only local relative exhibit PNG references."""
    if isinstance(node, list):
        for child in node:
            check_supported(child, source_dir, images)
    elif isinstance(node, dict):
        kind = node.get("t")
        if kind in {"RawBlock", "RawInline", "Math"}:
            raise ValueError("正文包含原始 HTML/TeX 或公式对象；请先使用普通文字公式和标准 Markdown，复杂对象交文档 skill 处理并单独验收")
        if kind == "Image":
            children = node.get("c") or []
            # pandoc 3.x: Image c = [Attr, [Inline], [url, title]] — target is last.
            url = ""
            if children and isinstance(children[-1], list) and children[-1] and isinstance(children[-1][0], str):
                url = children[-1][0]
            candidate = Path(url)
            if candidate.is_absolute() or candidate.drive or "://" in url:
                raise ValueError(f"图片必须为本地相对路径展项 PNG：{url}")
            if candidate.suffix.lower() != ".png":
                raise ValueError(f"仅支持 .png 展项图片：{url}")
            if not (source_dir / candidate).is_file():
                raise ValueError(f"展项图片不存在（需先运行 render_report_exhibits.py）：{url}")
            images[url] = source_dir / candidate
        check_supported(node.get("c"), source_dir, images)


def set_font(style, font: str, size: float) -> None:
    from docx.oxml.ns import qn
    from docx.shared import Pt
    style.font.name = "Calibri"
    style.font.size = Pt(size)
    style.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), font)


def make_reference(path: Path, font: str) -> None:
    from docx import Document
    from docx.shared import Mm, Pt, RGBColor
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin = section.bottom_margin = Mm(22)
    section.left_margin = section.right_margin = Mm(23)
    for name, size in (("Normal", 11), ("Title", 22), ("Heading 1", 17),
                       ("Heading 2", 14), ("Heading 3", 12)):
        style = doc.styles[name]
        set_font(style, font, size)
        style.paragraph_format.space_after = Pt(7)
        if name.startswith("Heading"):
            style.font.color.rgb = RGBColor.from_string("203C53")
            style.paragraph_format.keep_with_next = True
    doc.styles['Normal'].paragraph_format.line_spacing = 1.25
    for name in ("Caption", "Image Caption"):
        try:
            caption = doc.styles[name]
        except KeyError:
            from docx.enum.style import WD_STYLE_TYPE
            caption = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        set_font(caption, font, 9)
        caption.font.italic = True
        caption.font.color.rgb = RGBColor.from_string("6B7280")
        caption.paragraph_format.alignment = 1  # center
        caption.paragraph_format.space_before = Pt(4)
    doc.save(path)


def _field_paragraph(doc, instruction: str):
    """A paragraph holding a bare Word field (its content is invisible to readers)."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    paragraph = doc.add_paragraph()
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), instruction)
    run = OxmlElement("w:r")
    field.append(run)
    paragraph._p.append(field)
    return paragraph


def _append_page_field(paragraph) -> None:
    """Append a PAGE field to an existing (footer) paragraph; footers are not inventoried."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), " PAGE ")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t"); text.text = "1"
    run.append(text)
    field.append(run)
    paragraph._p.append(field)


def build_cover(doc, meta: dict) -> list:
    """Cover paragraphs (appended at body end); caller moves them to the top."""
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_BREAK
    from docx.oxml.ns import qn
    paragraphs = []
    gray = RGBColor.from_string("6B7280")
    ink = RGBColor.from_string("1F3B57")

    def add(text: str, size: float, bold: bool = False, color=None, before=0, after=0):
        paragraph = doc.add_paragraph()
        paragraph.alignment = 1
        paragraph.paragraph_format.space_before = Pt(before)
        paragraph.paragraph_format.space_after = Pt(after)
        run = paragraph.add_run(text)
        run.font.size = Pt(size)
        run.bold = bold
        run.font.color.rgb = color or ink
        run.font.name = "Calibri"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), meta["font"])
        paragraphs.append(paragraph)
        return paragraph

    add("", 12, after=90)
    if meta.get("company"):
        add(meta["company"], 12, color=gray, after=6)
    add(meta["title"], 24, bold=True, after=10)
    if meta.get("subtitle"):
        add(meta["subtitle"], 14, color=gray, after=60)
    if meta.get("date"):
        add(meta["date"], 11, color=gray, after=6)
    if meta.get("confidential"):
        add(meta["confidential"], 10, color=gray, after=0)
    break_paragraph = doc.add_paragraph()
    break_paragraph.add_run().add_break(WD_BREAK.PAGE)
    paragraphs.append(break_paragraph)
    return paragraphs


def polish_docx(path: Path, digest: str, meta: dict) -> Counter:
    """Cover, TOC field, footer page numbers, image scaling, table and caption polish."""
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_BREAK
    doc = Document(path)
    doc.core_properties.subject = f"business-design-md-sha256:{digest}"
    decorations = Counter()

    body = doc.element.body
    first = body.find(qn("w:p"))
    cover = build_cover(doc, meta)
    for paragraph in cover:
        first.addprevious(paragraph._p)
        for run in paragraph.runs:
            decorations.update(c for c in run.text if not c.isspace())

    toc_heading = doc.add_paragraph()
    toc_run = toc_heading.add_run("目录")
    toc_run.bold = True
    toc_run.font.size = Pt(16)
    toc_run.font.color.rgb = RGBColor.from_string("203C53")
    decorations.update("目录")
    cover[-1]._p.addnext(toc_heading._p)
    toc_field = _field_paragraph(doc, r'TOC \o "1-2" \h \z \u')
    toc_heading._p.addnext(toc_field._p)
    toc_hint = doc.add_paragraph()
    toc_hint.alignment = 1
    hint_run = toc_hint.add_run("（在 Word 中右键“更新域”生成带页码目录）")
    hint_run.font.size = Pt(9)
    hint_run.font.color.rgb = RGBColor.from_string("6B7280")
    decorations.update(c for c in "（在 Word 中右键“更新域”生成带页码目录）" if not c.isspace())
    toc_field._p.addnext(toc_hint._p)
    page_break = doc.add_paragraph()
    page_break.add_run().add_break(WD_BREAK.PAGE)
    toc_hint._p.addnext(page_break._p)

    footer_paragraph = doc.sections[0].footer.paragraphs[0]
    footer_paragraph.alignment = 1
    _append_page_field(footer_paragraph)

    section = doc.sections[0]
    available = section.page_width - section.left_margin - section.right_margin
    for shape in doc.inline_shapes:
        if shape.width > available:
            ratio = available / shape.width
            shape.height = int(shape.height * ratio)
            shape.width = int(available)
    for paragraph in doc.paragraphs:
        if paragraph._p.findall(".//" + qn("wp:inline")):
            paragraph.alignment = 1

    for table in doc.tables:
        table.style = "Table Grid"
        if not table.rows:
            continue
        header_properties = table.rows[0]._tr.get_or_add_trPr()
        if header_properties.find(qn("w:tblHeader")) is None:
            header_properties.append(OxmlElement("w:tblHeader"))
        weights = [max(6, min(45, max(len(row.cells[j].text) for row in table.rows)))
                   for j in range(len(table.columns))]
        for j, column in enumerate(table.columns):
            column.width = int(available * weights[j] / sum(weights))
        table.autofit = False
        for i, row in enumerate(table.rows):
            for j, cell in enumerate(row.cells):
                cell.width = table.columns[j].width
                properties = cell._tc.get_or_add_tcPr()
                margins = OxmlElement("w:tcMar")
                for side in ("top", "bottom", "left", "right"):
                    element = OxmlElement("w:" + side)
                    element.set(qn("w:w"), "100")
                    element.set(qn("w:type"), "dxa")
                    margins.append(element)
                properties.append(margins)
                fill = "E7EEF4" if i == 0 else ("F7FAFC" if i % 2 == 0 else None)
                if fill:
                    shade = OxmlElement("w:shd")
                    shade.set(qn("w:fill"), fill)
                    properties.append(shade)
                for cell_paragraph in cell.paragraphs:
                    cell_paragraph.style = doc.styles["Normal"]
                    cell_paragraph.paragraph_format.keep_with_next = False
                    cell_paragraph.paragraph_format.space_after = Pt(4)
                    for run in cell_paragraph.runs:
                        run.font.size = Pt(10)
                        if i == 0:
                            run.bold = True
    doc.save(path)
    return decorations


def export(source: Path, output: Path, font: str, meta_extra: dict | None = None) -> dict:
    if not shutil.which("pandoc"):
        raise ValueError("缺少 pandoc；请使用宿主已有转换工具或配置 pandoc")
    if output.exists():
        raise ValueError("目标目录已存在；请使用新的交付目录，避免覆盖已有版本")
    raw = source.read_bytes()
    if not raw.decode("utf-8").strip():
        raise ValueError("MD 正文为空")
    reader = "markdown-yaml_metadata_block-smart"
    ast = json.loads(pandoc(str(source), "-f", reader, "-t", "json"))
    images: dict[str, Path] = {}
    check_supported(ast["blocks"], source.parent, images)
    expected = text_inventory(ast["blocks"])
    if not expected:
        raise ValueError("MD 没有可见正文")
    output.parent.mkdir(parents=True, exist_ok=True)
    meta = {"title": "业务设计报告", "company": "", "date": "", "font": font}
    meta.update(meta_extra or {})
    with tempfile.TemporaryDirectory(prefix=".content-report-", dir=output.parent) as temp:
        staging = Path(temp)
        reference = staging / "reference.docx"
        make_reference(reference, font)
        md = staging / "business_design.md"
        md.write_bytes(raw)
        for url, target in images.items():
            destination = staging / url
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, destination)
        docx = staging / "business_design.docx"
        pandoc(str(md), "-f", reader, "-o", str(docx), "--reference-doc", str(reference),
               f"--resource-path={staging}")
        decorations = polish_docx(docx, sha256(md), meta)
        from docx import Document
        embedded = len(Document(docx).inline_shapes)
        if embedded != len(images):
            raise ValueError(f"展项嵌入校验失败：MD 引用 {len(images)} 张，DOCX 实际嵌入 {embedded} 张；未发布")
        actual_ast = json.loads(pandoc(str(docx), "-f", "docx", "-t", "json"))
        actual = text_inventory(actual_ast["blocks"])
        decorated = expected + decorations
        missing, extra = decorated - actual, actual - decorated
        if missing or extra:
            raise ValueError(f"MD→DOCX 文本清单不一致，缺少 {sum(missing.values())} 字符，新增 {sum(extra.values())} 字符；未发布")
        manifest = {
            "schema_version": "3.1", "conversion_status": "PASS",
            "text_inventory": "PASS", "content_review": "PENDING",
            "docx_readability": "PENDING", "font": font,
            "cover": {k: meta.get(k, "") for k in ("title", "subtitle", "company", "date", "confidential")},
            "exhibits": [{"path": url, "sha256": sha256(images[url])} for url in sorted(images)],
            "source": str(source.resolve()),
            "artifacts": {p.name: {"sha256": sha256(p)} for p in (md, docx)},
            "limitations": ["字符清单校验不证明语义、顺序或版式正确；需要独立正文评审和 DOCX 渲染检查",
                            "目录域与页码域需在 Word/WPS 中更新一次后显示页码"],
        }
        (staging / "report_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        reference.unlink()
        # Publish the entire directory only after conversion and fidelity checks.
        staging.rename(output)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", default="PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC")
    parser.add_argument("--title", default="业务设计报告")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--company", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--confidential", default="机密 · 仅供内部决策使用")
    args = parser.parse_args()
    meta = {"title": args.title, "subtitle": args.subtitle, "company": args.company,
            "date": args.date, "confidential": args.confidential}
    try:
        manifest = export(args.source, args.output, args.font, meta)
    except (OSError, ValueError, ImportError, subprocess.CalledProcessError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"[PASS] MD + DOCX -> {args.output}；展项 {len(manifest['exhibits'])} 个；内容评审和 DOCX 可读性待人工验收")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
