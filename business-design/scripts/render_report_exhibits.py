#!/usr/bin/env python3
"""Deterministically render consulting-style exhibit PNGs for the Word report.

Reads an exhibit plan (JSON) written during step 04 and renders each exhibit as
a PNG with a unified house style: one action title, direct value labels, no
chartjunk, source line at the bottom. Chart data must come from the evidence
ledger or the business design draft; auto types read numbers straight from
business_design.json so nothing is retyped.

Usage:
  python3 render_report_exhibits.py <project>/exhibit_plan.json <project>/exhibits \
      --business <project>/business_design.json --market <project>/market_insight.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

INK = "#1F3B57"        # 标题与主结构色（与 DOCX 标题一致）
BLUE = "#2E6FA3"
LIGHT = "#A9C4DA"
ACCENT = "#C8A154"     # 高亮/辅助
GRAY = "#6B7280"
BG = "#F1F5F9"
CRITICAL = "#A63D2F"   # 生死项
PACE = "#C8A154"       # 节奏项

AUTO_TYPES = ("segment_scores", "contribution_stack")
INLINE_TYPES = ("bar_ranking", "funnel", "matrix2x2", "roadmap", "bridge",
                "risk_matrix", "migration_flow")
ALL_TYPES = AUTO_TYPES + INLINE_TYPES


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_font() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    candidates = ["PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC",
                  "Source Han Sans SC", "Microsoft YaHei", "Arial Unicode MS"]
    plt.rcParams.update({
        "font.sans-serif": candidates,
        "axes.unicode_minus": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.dpi": 200,
    })


def _finish(fig, exhibit: dict, source: str, out: Path) -> None:
    """Apply house style chrome: action title, footnote, source line; save."""
    fig.suptitle(exhibit.get("action_title", exhibit["id"]),
                 x=0.02, y=0.975, ha="left", va="top", fontsize=15,
                 fontweight="bold", color=INK, wrap=True)
    # Reserve bottom strip for the footnote/source line so they never collide with axis labels.
    fig.tight_layout(rect=(0, 0.075, 1, 0.92))
    fig.text(0.99, 0.028, "资料来源：" + source, fontsize=8, color=GRAY, ha="right")
    if exhibit.get("note"):
        fig.text(0.02, 0.012, "注：" + exhibit["note"], fontsize=8, color=GRAY, ha="left")
    fig.savefig(out, bbox_inches="tight", pad_inches=0.25)
    import matplotlib.pyplot as plt
    plt.close(fig)


def _bar_axes(figsize=(6.9, 3.4)):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=figsize)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#D3DCE6")
    ax.tick_params(colors=GRAY, labelsize=9)
    return fig, ax


# ---------------------------------------------------------------- auto types

def _segments(business: dict) -> list[dict]:
    sel = business["chapters"]["customer_selection"]
    return sorted(sel.get("segment_evaluation", []),
                  key=lambda s: s.get("weighted_score", 0), reverse=True)


def render_segment_scores(exhibit: dict, business: dict, out: Path) -> str:
    import matplotlib.pyplot as plt
    rows = _segments(business)
    if not rows:
        raise ValueError("business_design.json 缺少 segment_evaluation，无法渲染环节评分")
    labels = [r["segment"] for r in rows]
    values = [r["weighted_score"] for r in rows]
    fig, ax = _bar_axes((6.9, 0.75 + 0.52 * len(rows)))
    colors = [ACCENT if i == 0 else BLUE for i in range(len(rows))]
    bars = ax.barh(range(len(rows)), values, color=colors, height=0.62)
    ax.set_yticks(range(len(rows)), labels, fontsize=10, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 5.15)
    for bar, value in zip(bars, values):
        ax.text(bar.get_width() + 0.07, bar.get_y() + bar.get_height() / 2,
                f"{value:.2f}", va="center", fontsize=10, color=INK, fontweight="bold")
    ax.set_xlabel("六维加权总分（满分 5）", fontsize=9, color=GRAY)
    ax.xaxis.grid(True, color="#E8EEF4")
    ax.set_axisbelow(True)
    _finish(fig, exhibit, "底稿 business_design.json · segment_evaluation", out)
    return "business_design.json:chapters.customer_selection.segment_evaluation"


def render_contribution_stack(exhibit: dict, business: dict, out: Path) -> str:
    import matplotlib.pyplot as plt
    rows = list(reversed(_segments(business)))  # 最高分在顶部
    labels = [r["segment"] for r in rows]
    market = [r.get("market_attractiveness_contribution", 0) for r in rows]
    fit = [r.get("enterprise_fit_contribution", 0) for r in rows]
    fig, ax = _bar_axes((6.9, 0.8 + 0.55 * len(rows)))
    ax.barh(labels, market, color=BLUE, height=0.6, label="市场吸引力（55%，满分 2.75）")
    ax.barh(labels, fit, left=market, color=LIGHT, height=0.6, label="企业胜任权（45%，满分 2.25）")
    for i, row in enumerate(rows):
        total = market[i] + fit[i]
        ax.text(total + 0.06, i, f"{total:.2f}", va="center", fontsize=10,
                color=INK, fontweight="bold")
    ax.set_xlim(0, 5.15)
    ax.set_xlabel("加权贡献与总分", fontsize=9, color=GRAY)
    ax.xaxis.grid(True, color="#E8EEF4")
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", fontsize=8.5, frameon=False)
    _finish(fig, exhibit, "底稿 business_design.json · segment_evaluation", out)
    return "business_design.json:chapters.customer_selection.segment_evaluation"


# -------------------------------------------------------------- inline types

def render_bar_ranking(exhibit: dict, data: dict, out: Path) -> str:
    labels, values = data["labels"], data["values"]
    unit = data.get("unit", "")
    highlight = set(data.get("highlight", []))
    order = sorted(range(len(values)), key=lambda i: values[i])
    fig, ax = _bar_axes((6.9, 0.8 + 0.52 * len(values)))
    colors = [ACCENT if i in highlight else BLUE for i in order]
    bars = ax.barh(range(len(order)), [values[i] for i in order], color=colors, height=0.62)
    ax.set_yticks(range(len(order)), [labels[i] for i in order], fontsize=10, color=INK)
    vmax = max(values)
    for bar, i in zip(bars, order):
        ax.text(bar.get_width() + vmax * 0.015, bar.get_y() + bar.get_height() / 2,
                f"{values[i]:g}{unit}", va="center", fontsize=10, color=INK, fontweight="bold")
    ax.set_xlim(0, vmax * 1.14)
    ax.xaxis.grid(True, color="#E8EEF4")
    ax.set_axisbelow(True)
    _finish(fig, exhibit, "证据台账 " + "、".join(data.get("evidence", [])) or "见台账", out)
    return "、".join(data.get("evidence", []))


def render_funnel(exhibit: dict, data: dict, out: Path) -> str:
    import matplotlib.pyplot as plt
    layers = data["layers"]
    n = len(layers)
    fig, ax = plt.subplots(figsize=(6.9, 1.15 + 1.05 * n))
    ax.axis("off")
    top_w, shrink = 0.92, 0.92 / max(n, 1) * 0.78
    for i, layer in enumerate(layers):
        y0, y1 = n - i, n - i - 0.82
        w0 = top_w - shrink * i
        w1 = top_w - shrink * (i + 1)
        color = [BLUE, LIGHT, "#D7E3EE"][min(i, 2)]
        ax.fill([0.5 - w0 / 2, 0.5 + w0 / 2, 0.5 + w1 / 2, 0.5 - w1 / 2],
                [y0, y0, y1, y1], color=color, edgecolor="white", linewidth=1.5)
        ax.text(0.5, (y0 + y1) / 2 + 0.04, layer["label"], ha="center", va="center",
                fontsize=11, fontweight="bold", color="white" if i < 2 else INK)
        ax.text(0.5, (y0 + y1) / 2 - 0.14, layer.get("detail", ""), ha="center",
                va="center", fontsize=8.5, color="white" if i < 2 else GRAY)
    ax.set_xlim(0, 1)
    ax.set_ylim(0.05, n + 0.15)
    _finish(fig, exhibit, "、".join(data.get("evidence", [])) or "底稿客户分层", out)
    return "、".join(data.get("evidence", []))


def render_matrix2x2(exhibit: dict, data: dict, out: Path) -> str:
    import matplotlib.pyplot as plt
    fig, ax = _bar_axes((6.9, 4.6))
    tags = data.get("tag_colors", {})
    default = {"P0": ACCENT, "P1": BLUE, "P2": LIGHT}
    for point in data["points"]:
        color = tags.get(point.get("tag", ""), default.get(point.get("tag", ""), BLUE))
        size = 320 + 520 * point.get("size", 0.6)
        ax.scatter(point["x"], point["y"], s=size, color=color, alpha=0.85,
                   edgecolor="white", linewidth=1.2, zorder=3)
        ax.annotate(f"{point['label']}\n{point.get('tag', '')}", (point["x"], point["y"]),
                    textcoords="offset points", xytext=(0, 16), ha="center",
                    fontsize=9.5, color=INK, fontweight="bold")
    ax.axvline(2.5, color="#D3DCE6", linewidth=1)
    ax.axhline(2.5, color="#D3DCE6", linewidth=1)
    ax.set_xlim(0.3, 4.7)
    ax.set_ylim(0.3, 4.7)
    ax.set_xlabel(data.get("x_label", "横轴"), fontsize=10, color=INK)
    ax.set_ylabel(data.get("y_label", "纵轴"), fontsize=10, color=INK)
    ax.set_xticks([])
    ax.set_yticks([])
    _finish(fig, exhibit, "、".join(data.get("evidence", [])) or "见台账", out)
    return "、".join(data.get("evidence", []))


def render_roadmap(exhibit: dict, data: dict, out: Path) -> str:
    import matplotlib.pyplot as plt
    phases = data["phases"]
    fig, ax = plt.subplots(figsize=(6.9, 2.0 + 0.62 * len(phases)))
    ax.axis("off")
    y = len(phases)
    ax.annotate("", xy=(0.97, y), xytext=(0.03, y),
                arrowprops=dict(arrowstyle="-|>", color="#D3DCE6", linewidth=2))
    for i, phase in enumerate(phases):
        x = 0.03 + (0.94 / max(len(phases) - 1, 1)) * i
        ytop = y - 0.18
        ax.scatter([x], [ytop], s=140, color=BLUE if i else ACCENT, zorder=3)
        ax.text(x, ytop + 0.3, phase["name"], ha="center", fontsize=10.5,
                fontweight="bold", color=INK)
        ax.text(x, ytop - 0.32, phase.get("window", ""), ha="center", fontsize=8.5, color=GRAY)
        ax.text(x, ytop - 0.62, "\n".join(f"· {item}" for item in phase["items"][:4]),
                ha="center", va="top", fontsize=8.8, color=INK, linespacing=1.5)
    ax.set_xlim(0, 1)
    ax.set_ylim(y - 1.55, y + 0.75)
    _finish(fig, exhibit, "底稿实施顺序与验证计划", out)
    return "business_design.json 实施计划"


def render_bridge(exhibit: dict, data: dict, out: Path) -> str:
    import matplotlib.pyplot as plt
    items = data["items"]
    fig, ax = _bar_axes((6.9, 3.6))
    cumulative = 0.0
    positions, heights, bottoms, colors = [], [], [], []
    for item in items:
        value = item["value"]
        if item.get("total"):
            positions.append(item["label"])
            heights.append(cumulative if value == 0 else value)
            bottoms.append(0)
            colors.append(ACCENT)
            cumulative = value if value else cumulative
        else:
            positions.append(item["label"])
            bottoms.append(cumulative if value < 0 else cumulative)
            heights.append(abs(value))
            colors.append("#B3543F" if value < 0 else BLUE)
            cumulative += value
    bars = ax.bar(range(len(positions)), heights, bottom=[max(b, 0) for b in bottoms],
                  color=colors, width=0.62)
    ax.set_xticks(range(len(positions)), positions, fontsize=8.8, color=INK)
    for i, (bar, item) in enumerate(zip(bars, items)):
        label = f"{item['value']:+g}" if not item.get("total") else f"={item['value']:g}"
        ax.text(i, max(bar.get_y() + bar.get_height(), 0) + max(heights) * 0.03,
                label, ha="center", fontsize=9.5, color=INK, fontweight="bold")
    ax.yaxis.grid(True, color="#E8EEF4")
    ax.set_axisbelow(True)
    unit = data.get("unit", "")
    if unit:
        ax.set_ylabel(unit, fontsize=9, color=GRAY)
    _finish(fig, exhibit, "、".join(data.get("evidence", [])) or "底稿单位经济性（方向性）", out)
    return "、".join(data.get("evidence", []))


def render_risk_matrix(exhibit: dict, data: dict, out: Path) -> str:
    import matplotlib.pyplot as plt
    fig, ax = _bar_axes((6.9, 4.6))
    risks = data["risks"]
    ax.add_patch(plt.Rectangle((2.5, 2.5), 2.5, 2.5, color="#F6E8E4", zorder=1))
    ax.set_xlim(0.5, 5.1)
    ax.set_ylim(0.5, 5.1)
    ax.set_xticks(range(1, 6), ["很低", "低", "中", "高", "很高"], fontsize=9, color=GRAY)
    ax.set_yticks(range(1, 6), ["很低", "低", "中", "高", "很高"], fontsize=9, color=GRAY)
    ax.set_xlabel("发生可能性", fontsize=10, color=INK)
    ax.set_ylabel("对设计的影响", fontsize=10, color=INK)
    for i, risk in enumerate(risks):
        color = CRITICAL if risk.get("tier") == "生死" else PACE
        ax.scatter(risk["likelihood"], risk["impact"], s=430, color=color,
                   alpha=0.9, edgecolor="white", linewidth=1.2, zorder=3)
        ax.annotate(f"{risk['label']}\n（{risk.get('tier', '')}）",
                    (risk["likelihood"], risk["impact"]),
                    textcoords="offset points", xytext=(0, 15), ha="center",
                    fontsize=8.6, color=INK, fontweight="bold")
    ax.xaxis.grid(True, color="#F1F5F9")
    ax.yaxis.grid(True, color="#F1F5F9")
    ax.set_axisbelow(True)
    _finish(fig, exhibit, "底稿风险管理 + 证据台账", out)
    return "business_design.json 风险管理"


def render_migration_flow(exhibit: dict, data: dict, out: Path) -> str:
    import matplotlib.pyplot as plt
    from_boxes, to_boxes = data["from"], data["to"]
    rows = max(len(from_boxes), len(to_boxes))
    fig, ax = plt.subplots(figsize=(6.9, 1.4 + 0.95 * rows))
    ax.axis("off")
    for i, box in enumerate(from_boxes):
        ax.add_patch(plt.Rectangle((0.03, rows - i - 0.86), 0.36, 0.72,
                                   facecolor=BG, edgecolor="#D3DCE6"))
        ax.text(0.21, rows - i - 0.5, box["label"], ha="center", va="center",
                fontsize=9.5, color=GRAY)
    for i, box in enumerate(to_boxes):
        ax.add_patch(plt.Rectangle((0.61, rows - i - 0.86), 0.36, 0.72,
                                   facecolor="#EAF1F7", edgecolor=BLUE, linewidth=1.4))
        ax.text(0.79, rows - i - 0.5, box["label"], ha="center", va="center",
                fontsize=9.5, color=INK, fontweight="bold")
    for i in range(min(len(from_boxes), len(to_boxes))):
        ax.annotate("", xy=(0.61, rows - i - 0.5), xytext=(0.39, rows - i - 0.5),
                    arrowprops=dict(arrowstyle="-|>", color=ACCENT, linewidth=1.8))
    if data.get("center_note"):
        ax.text(0.5, rows + 0.06, data["center_note"], ha="center", fontsize=9.5,
                color=ACCENT, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0.05, rows + 0.35)
    _finish(fig, exhibit, "、".join(data.get("evidence", [])) or "见台账", out)
    return "、".join(data.get("evidence", []))


RENDERERS = {
    "bar_ranking": lambda ex, biz, data, out: render_bar_ranking(ex, data, out),
    "funnel": lambda ex, biz, data, out: render_funnel(ex, data, out),
    "matrix2x2": lambda ex, biz, data, out: render_matrix2x2(ex, data, out),
    "roadmap": lambda ex, biz, data, out: render_roadmap(ex, data, out),
    "bridge": lambda ex, biz, data, out: render_bridge(ex, data, out),
    "risk_matrix": lambda ex, biz, data, out: render_risk_matrix(ex, data, out),
    "migration_flow": lambda ex, biz, data, out: render_migration_flow(ex, data, out),
    "segment_scores": lambda ex, biz, data, out: render_segment_scores(ex, biz, out),
    "contribution_stack": lambda ex, biz, data, out: render_contribution_stack(ex, biz, out),
}


def render_plan(plan_path: Path, out_dir: Path, business: dict | None,
                market: dict | None) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    exhibits = plan.get("exhibits", [])
    if not exhibits:
        raise ValueError("exhibit_plan.json 没有 exhibits")
    out_dir.mkdir(parents=True, exist_ok=True)
    known = {e["id"] for e in market.get("evidence_registry", [])} if market else set()
    rendered, warnings = [], []
    for exhibit in exhibits:
        kind = exhibit.get("type")
        if kind not in ALL_TYPES:
            raise ValueError(f"{exhibit.get('id')}: 不支持的展项类型 {kind}；可选 {ALL_TYPES}")
        if not exhibit.get("action_title"):
            raise ValueError(f"{exhibit.get('id')}: 缺少观点式标题 action_title")
        refs = exhibit.get("source_refs", [])
        if market and refs:
            dangling = [r for r in refs if r not in known]
            if dangling:
                raise ValueError(f"{exhibit['id']}: source_refs 不在证据台账: {dangling}")
        elif not market and refs:
            warnings.append(f"{exhibit['id']}: 未提供 market_insight.json，source_refs 未校验")
        data = exhibit.get("data", {})
        if kind in AUTO_TYPES and business is None:
            raise ValueError(f"{exhibit['id']}: 自动类型需要 --business business_design.json")
        source = RENDERERS[kind](exhibit, business or {}, data, out_dir / f"{exhibit['id']}.png")
        rendered.append({"id": exhibit["id"], "type": kind, "png": f"{out_dir.name}/{exhibit['id']}.png",
                         "sha256": _sha256(out_dir / f"{exhibit['id']}.png"),
                         "action_title": exhibit["action_title"], "traced_source": source,
                         "source_refs": refs})
    manifest = {
        "schema_version": "1.0",
        "plan": str(plan_path), "exhibit_count": len(rendered),
        "evidence_refs_verified": bool(market), "warnings": warnings, "exhibits": rendered,
    }
    (out_dir / "exhibits_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--business", type=Path, default=None)
    parser.add_argument("--market", type=Path, default=None)
    args = parser.parse_args()
    try:
        _load_font()
        business = json.loads(args.business.read_text(encoding="utf-8")) if args.business else None
        market = json.loads(args.market.read_text(encoding="utf-8")) if args.market else None
        manifest = render_plan(args.plan, args.out_dir, business, market)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    for item in manifest["exhibits"]:
        print(f"[PASS] {item['id']} {item['type']} -> {item['png']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
