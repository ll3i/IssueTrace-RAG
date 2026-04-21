from __future__ import annotations

import csv
import json
import math
import pathlib
import statistics
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt


BASE_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "AI활용데이터"
OUTPUT_DIR = BASE_DIR / "proposal_visuals"

K_TITLE = "\uc758\uacb0\uc11c\uc81c\ubaa9"
K_DATE = "\uacf5\uac1c\uc77c\uc790"
K_INFOS = "\ud53c\uc2ec\uc778\uc815\ubcf4"
K_VIOLATION = "\uc704\ubc18\uc720\ud615"
K_DETAIL = "\uc138\ubd80\uc704\ubc18\uc720\ud615"
K_ACTION = "\uc870\uce58\uc720\ud615"
K_COMPANY = "\ud53c\uc2ec\uc778\uae30\uc5c5\uba85"


def configure_font() -> None:
    candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic", "DejaVu Sans"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def load_records() -> dict[str, object]:
    meta_files = sorted(DATA_DIR.glob("*_metadata.json"))
    hybrid_files = sorted(DATA_DIR.glob("*_hybrid.json"))

    years = Counter()
    violation = Counter()
    detail = Counter()
    action = Counter()
    chunk_type = Counter()
    section = Counter()
    chunk_counts: list[int] = []
    respondent_counts: list[int] = []
    longest_cases: list[tuple[str, int]] = []

    for path in meta_files:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        date = str(data.get(K_DATE, ""))
        if len(date) >= 4 and date[:4].isdigit():
            years[date[:4]] += 1

        infos = data.get(K_INFOS, []) or []
        respondent_counts.append(len(infos))
        for info in infos:
            violation[str(info.get(K_VIOLATION, "Unknown")).strip() or "Unknown"] += 1
            detail[str(info.get(K_DETAIL, "Unknown")).strip() or "Unknown"] += 1
            action[str(info.get(K_ACTION, "Unknown")).strip() or "Unknown"] += 1

    for path in hybrid_files:
        with path.open("r", encoding="utf-8") as f:
            items = json.load(f)

        title = path.name.replace("_hybrid.json", "")
        chunk_counts.append(len(items))
        longest_cases.append((title, len(items)))
        for item in items:
            meta = item.get("metadata", {})
            chunk_type[str(meta.get("chunk_type", "unknown"))] += 1
            section[str(meta.get("section", "Unknown")).strip() or "Unknown"] += 1

    longest_cases.sort(key=lambda x: x[1], reverse=True)

    return {
        "case_count": len(meta_files),
        "meta_files": meta_files,
        "hybrid_files": hybrid_files,
        "years": years,
        "violation": violation,
        "detail": detail,
        "action": action,
        "chunk_type": chunk_type,
        "section": section,
        "chunk_counts": chunk_counts,
        "respondent_counts": respondent_counts,
        "longest_cases": longest_cases[:10],
    }


def save_counter_csv(path: pathlib.Path, header: tuple[str, str], counter: Counter) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for key, value in counter.items():
            writer.writerow([key, value])


def annotate_bars(ax: plt.Axes, values: list[int], horizontal: bool = False) -> None:
    max_value = max(values) if values else 0
    for patch, value in zip(ax.patches, values):
        if horizontal:
            x = patch.get_width()
            y = patch.get_y() + patch.get_height() / 2
            ax.text(x + max_value * 0.01, y, f"{value:,}", va="center", fontsize=9)
        else:
            x = patch.get_x() + patch.get_width() / 2
            y = patch.get_height()
            ax.text(x, y + max_value * 0.01, f"{value:,}", ha="center", va="bottom", fontsize=9)


def plot_cases_by_year(years: Counter) -> None:
    ordered = sorted(years.items())
    labels = [k for k, _ in ordered]
    values = [v for _, v in ordered]
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#214E8A", "#5D8BF4", "#7FB3D5", "#F2B134", "#EC6B56", "#6C9A8B", "#8E7DBE"]
    ax.bar(labels, values, color=colors[: len(labels)])
    annotate_bars(ax, values)
    ax.set_title("\uacf5\uac1c \uc5f0\ub3c4\ubcc4 \uc758\uacb0\uc11c \uac74\uc218")
    ax.set_xlabel("\uacf5\uac1c \uc5f0\ub3c4")
    ax.set_ylabel("\uc758\uacb0\uc11c \uac74\uc218")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "01_cases_by_year.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_top_counter(counter: Counter, path_name: str, title: str, xlabel: str, top_n: int = 10) -> None:
    items = counter.most_common(top_n)
    labels = [k for k, _ in items][::-1]
    values = [v for _, v in items][::-1]
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(labels, values, color="#2F6690")
    annotate_bars(ax, values, horizontal=True)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / path_name, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_action_distribution(action: Counter) -> None:
    items = action.most_common(8)
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(labels, values, color="#EC6B56")
    annotate_bars(ax, values)
    ax.set_title("\uc8fc\uc694 \uc870\uce58\uc720\ud615 \ubd84\ud3ec")
    ax.set_ylabel("\uac74\uc218")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "03_action_type_distribution.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_chunk_composition(chunk_type: Counter, total_chunks: int) -> None:
    labels_map = {"text": "Text Chunk", "table": "Table Chunk", "unknown": "Unknown"}
    labels = [labels_map.get(k, k) for k in chunk_type.keys()]
    values = list(chunk_type.values())
    colors = ["#214E8A", "#F2B134", "#9AA5B1"]

    def autopct(pct: float) -> str:
        count = int(round(pct / 100.0 * total_chunks))
        return f"{pct:.1f}%\\n({count:,})"

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(values, labels=labels, autopct=autopct, startangle=90, colors=colors[: len(values)])
    ax.set_title("\uc804\uccb4 \uccad\ud06c \uad6c\uc131 \ube44\uc911")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "04_chunk_composition.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_chunk_histogram(chunk_counts: list[int]) -> None:
    avg = statistics.mean(chunk_counts)
    med = statistics.median(chunk_counts)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(chunk_counts, bins=20, color="#6C9A8B", edgecolor="white")
    ax.axvline(avg, color="#D1495B", linestyle="--", linewidth=2, label=f"Mean {avg:.1f}")
    ax.axvline(med, color="#214E8A", linestyle=":", linewidth=2, label=f"Median {med:.0f}")
    ax.set_title("\uc0ac\uac74\ubcc4 \uccad\ud06c \uc218 \ubd84\ud3ec")
    ax.set_xlabel("\uc0ac\uac74\ub2f9 \uccad\ud06c \uc218")
    ax.set_ylabel("\uc758\uacb0\uc11c \uac74\uc218")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "05_chunk_count_distribution.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_longest_cases(longest_cases: list[tuple[str, int]]) -> None:
    labels = [name if len(name) <= 34 else name[:34] + "..." for name, _ in longest_cases][::-1]
    values = [count for _, count in longest_cases][::-1]
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.barh(labels, values, color="#5D8BF4")
    annotate_bars(ax, values, horizontal=True)
    ax.set_title("\uccad\ud06c \uc218 \uae30\uc900 \uc0c1\uc704 10\uac1c \uc0ac\uac74")
    ax.set_xlabel("\uccad\ud06c \uc218")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "06_top10_longest_cases.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def build_summary(records: dict[str, object]) -> str:
    years: Counter = records["years"]  # type: ignore[assignment]
    violation: Counter = records["violation"]  # type: ignore[assignment]
    action: Counter = records["action"]  # type: ignore[assignment]
    chunk_type: Counter = records["chunk_type"]  # type: ignore[assignment]
    chunk_counts: list[int] = records["chunk_counts"]  # type: ignore[assignment]
    respondent_counts: list[int] = records["respondent_counts"]  # type: ignore[assignment]
    longest_cases: list[tuple[str, int]] = records["longest_cases"]  # type: ignore[assignment]

    total_chunks = sum(chunk_counts)
    text_chunks = chunk_type.get("text", 0)
    table_chunks = chunk_type.get("table", 0)
    text_ratio = text_chunks / total_chunks * 100 if total_chunks else 0
    table_ratio = table_chunks / total_chunks * 100 if total_chunks else 0
    years_text = ", ".join(f"{year}년 {count}건" for year, count in sorted(years.items()))
    top3_violations = violation.most_common(3)
    top2_actions = action.most_common(2)
    longest_text = ", ".join(f"{name[:18]}...({count}개)" for name, count in longest_cases[:3])

    lines = [
        "# IssueTrace RAG \uae30\ud68d\uc11c \uc2dc\uac01\ud654 \uc694\uc57d",
        "",
        "## \ud575\uc2ec \uc218\uce58",
        f"- \uc758\uacb0\uc11c \uc6d0\ucc9c \uac74\uc218: {records['case_count']:,}\uac74",
        f"- \uc804\uccb4 \uccad\ud06c \uc218: {total_chunks:,}\uac1c",
        f"- \uc0ac\uac74\ub2f9 \ud3c9\uade0 \uccad\ud06c \uc218: {statistics.mean(chunk_counts):.2f}\uac1c",
        f"- \uc0ac\uac74\ub2f9 \uc911\uc559 \uccad\ud06c \uc218: {statistics.median(chunk_counts):.0f}\uac1c",
        f"- \ud53c\uc2ec\uc778 \uc815\ubcf4 \ud3c9\uade0 \uac74\uc218: {statistics.mean(respondent_counts):.2f}\uba85",
        f"- \uccad\ud06c \uad6c\uc131: text {text_chunks:,}\uac1c ({text_ratio:.1f}%), table {table_chunks:,}\uac1c ({table_ratio:.1f}%)",
        "",
        "## \uad8c\uc7a5 \uc0bd\uc785 \uc2dc\uac01\ud654",
        "- `01_cases_by_year.png`: \uacf5\uac1c \uc5f0\ub3c4\ubcc4 \uc758\uacb0\uc11c \uac74\uc218. \ub370\uc774\ud130 \ucd95\uc801 \uaddc\ubaa8\ub97c \uac00\uc7a5 \uc9c1\uad00\uc801\uc73c\ub85c \ubcf4\uc5ec\uc90c.",
        "- `02_violation_type_top10.png`: \ud53c\uc2ec\uc778 \uae30\uc900 \uc8fc\uc694 \uc704\ubc18\uc720\ud615 Top 10. \uc11c\ube44\uc2a4\uac00 \uc5b4\ub5a4 \ubc95\ub960 \uc218\uc694\uc5d0 \uc9d1\uc911\ub418\ub294\uc9c0 \uc124\uba85\ud558\uae30 \uc88b\uc74c.",
        "- `03_action_type_distribution.png`: \uc8fc\uc694 \uc870\uce58\uc720\ud615 \ubd84\ud3ec. \uc2dc\uc815\uba85\ub839/\uacfc\uc9d5\uae08 \uc911\uc2ec\uc758 \ud65c\uc6a9 \uac00\uce58\ub97c \uac15\uc870\ud560 \uc218 \uc788\uc74c.",
        "- `04_chunk_composition.png`: text/table \uccad\ud06c \ube44\uc911. \uadfc\uac70 \uae30\ubc18 RAG\uc5d0\uc11c \ud14d\uc2a4\ud2b8\uc640 \ud45c \ub370\uc774\ud130\ub97c \ud568\uaed8 \uc0b4\ub9b0\ub2e4\ub294 \uc810\uc744 \uc124\uba85\ud558\uae30 \uc88b\uc74c.",
        "- `05_chunk_count_distribution.png`: \uc0ac\uac74\ubcc4 \uccad\ud06c \uc218 \ubd84\ud3ec. \ubb38\uc11c \uae38\uc774 \ud3b8\ucc28\uac00 \ud070 \ubc95\ub960 \ubb38\uc11c\uc5d0\uc11c\ub3c4 \uac80\uc0c9\uc774 \ub3d9\uc791\ud55c\ub2e4\ub294 \uc810\uc744 \ubcf4\uc5ec\uc90c.",
        "- `06_top10_longest_cases.png`: \uccad\ud06c \uc218 \uae30\uc900 \uc0c1\uc704 10\uac1c \uc0ac\uac74. \ub300\ud615 \uc758\uacb0\uc11c \ucc98\ub9ac \uc5ed\ub7c9\uc744 \uc5b4\ud544\ud560 \ub54c \uc0ac\uc6a9 \uac00\ub2a5.",
        "",
        "## \uc11c\uc220\uc6a9 \ud3ec\uc778\ud2b8",
        f"- \uacf5\uac1c \uc5f0\ub3c4\ubcc4\ub85c\ub294 {years_text}\ub85c \uad6c\uc131\ub418\uc5b4 \uc788\uc5b4, \ub2e8\ub144\ub3c4 \uc0d8\ud50c\uc774 \uc544\ub2cc \ub2e4\ub144\ub3c4 \ubc95\ub960 \ub370\uc774\ud130\uc14b\uc784\uc744 \uc124\uba85\ud560 \uc218 \uc788\uc74c.",
        f"- \uc704\ubc18\uc720\ud615\uc740 {top3_violations[0][0]}({top3_violations[0][1]:,}\uac74), {top3_violations[1][0]}({top3_violations[1][1]:,}\uac74), {top3_violations[2][0]}({top3_violations[2][1]:,}\uac74) \uc21c\uc73c\ub85c \ub098\ud0c0\ub098 \uacf5\uc815\uac70\ub798 \ud575\uc2ec \uc7c1\uc810\uc744 \ub113\uac8c \ud3ec\uad04\ud568.",
        f"- \uc870\uce58\uc720\ud615\uc740 {top2_actions[0][0]}({top2_actions[0][1]:,}\uac74)\uacfc {top2_actions[1][0]}({top2_actions[1][1]:,}\uac74)\uc774 \ub300\ub2e4\uc218\uc5ec\uc11c, \uc2e4\uc81c \uaddc\uc81c/\uc81c\uc7ac \ud310\ub2e8 \uc9c0\uc6d0 \uc0ac\ub840\ub97c \uac15\uc870\ud558\uae30 \uc88b\uc74c.",
        f"- \uc0ac\uac74\ub2f9 \uccad\ud06c \uc218\ub294 \ucd5c\uc18c {min(chunk_counts)}\uac1c, \ucd5c\ub300 {max(chunk_counts)}\uac1c\ub85c \ud3b8\ucc28\uac00 \ud06c\uba70, \uc0c1\uc704 \uc0ac\uac74\uc740 {longest_text}\ub85c \uc9d1\uacc4\ub428.",
        "",
        "## \uc0b0\ucd9c\ubb3c \ubaa9\ub85d",
        "- `proposal_visuals/01_cases_by_year.png`",
        "- `proposal_visuals/02_violation_type_top10.png`",
        "- `proposal_visuals/03_action_type_distribution.png`",
        "- `proposal_visuals/04_chunk_composition.png`",
        "- `proposal_visuals/05_chunk_count_distribution.png`",
        "- `proposal_visuals/06_top10_longest_cases.png`",
        "- `proposal_visuals/aggregate_metrics.json`",
        "- `proposal_visuals/cases_by_year.csv`",
        "- `proposal_visuals/violation_type_top10.csv`",
        "- `proposal_visuals/action_type_distribution.csv`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    configure_font()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = load_records()

    years: Counter = records["years"]  # type: ignore[assignment]
    violation: Counter = records["violation"]  # type: ignore[assignment]
    detail: Counter = records["detail"]  # type: ignore[assignment]
    action: Counter = records["action"]  # type: ignore[assignment]
    chunk_type: Counter = records["chunk_type"]  # type: ignore[assignment]
    chunk_counts: list[int] = records["chunk_counts"]  # type: ignore[assignment]
    longest_cases: list[tuple[str, int]] = records["longest_cases"]  # type: ignore[assignment]

    plot_cases_by_year(years)
    plot_top_counter(
        violation,
        "02_violation_type_top10.png",
        "\uc8fc\uc694 \uc704\ubc18\uc720\ud615 Top 10 (\ud53c\uc2ec\uc778 \uae30\uc900)",
        "\uc9d1\uacc4 \uac74\uc218",
    )
    plot_action_distribution(action)
    plot_chunk_composition(chunk_type, sum(chunk_counts))
    plot_chunk_histogram(chunk_counts)
    plot_longest_cases(longest_cases)

    aggregate = {
        "case_count": records["case_count"],
        "total_chunks": sum(chunk_counts),
        "chunk_type": dict(chunk_type),
        "cases_by_year": dict(years),
        "top_violation_types": violation.most_common(10),
        "top_detail_types": detail.most_common(10),
        "top_action_types": action.most_common(10),
        "chunk_count_summary": {
            "min": min(chunk_counts),
            "median": statistics.median(chunk_counts),
            "mean": round(statistics.mean(chunk_counts), 2),
            "max": max(chunk_counts),
        },
        "longest_cases": longest_cases,
    }
    with (OUTPUT_DIR / "aggregate_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(aggregate, f, ensure_ascii=False, indent=2)

    save_counter_csv(OUTPUT_DIR / "cases_by_year.csv", ("year", "case_count"), years)
    save_counter_csv(
        OUTPUT_DIR / "violation_type_top10.csv",
        ("violation_type", "count"),
        Counter(dict(violation.most_common(10))),
    )
    save_counter_csv(
        OUTPUT_DIR / "action_type_distribution.csv",
        ("action_type", "count"),
        Counter(dict(action.most_common(10))),
    )

    summary = build_summary(records)
    (OUTPUT_DIR / "proposal_visual_summary.md").write_text(summary, encoding="utf-8")


if __name__ == "__main__":
    main()
