"""生成两张径向有限体积离散示意图。

第一张图展示圆柱体、顶部径向层及其厚度 dr；第二张图把环形控制体与
相邻控制体的守恒通量平衡放在同一张图中。输出默认写入 submit/all/figures。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Rectangle, Wedge


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "submit" / "all" / "figures"


def _arrow(ax, start, end, *, color="#1f4e79", lw=1.6, mutation=12):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="<->",
            mutation_scale=mutation,
            linewidth=lw,
            color=color,
            shrinkA=0,
            shrinkB=0,
        )
    )


def _flow_arrow(ax, start, end, text, *, color="#c0392b", text_offset=(0.0, 0.12)):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=13,
            linewidth=1.8,
            color=color,
        )
    )
    ax.text(
        (start[0] + end[0]) / 2 + text_offset[0],
        (start[1] + end[1]) / 2 + text_offset[1],
        text,
        color=color,
        ha="center",
        va="center",
        fontsize=10,
    )


def _prepare_axis(ax):
    ax.set_facecolor("white")
    ax.axis("off")


def _draw_geometry(ax):
    """Draw the 3-D cylinder and the radial layer dr."""
    ax.set_title("(a) 圆柱体与顶部径向层", pad=12, fontsize=12, fontweight="bold")

    cx, rx = 1.85, 1.05
    top_y, bottom_y = 1.65, -1.75
    ry = 0.34

    # Bottom ellipse first, then the side wall and the top face.
    ax.add_patch(
        Ellipse(
            (cx, bottom_y),
            2 * rx,
            2 * ry,
            facecolor="#c9e3f0",
            edgecolor="#1f4e79",
            linewidth=2,
            zorder=1,
        )
    )
    ax.add_patch(
        Rectangle(
            (cx - rx, bottom_y),
            2 * rx,
            top_y - bottom_y,
            facecolor="#dceef8",
            edgecolor="none",
            zorder=2,
        )
    )
    ax.plot([cx - rx, cx - rx], [bottom_y, top_y], color="#1f4e79", linewidth=2, zorder=3)
    ax.plot([cx + rx, cx + rx], [bottom_y, top_y], color="#1f4e79", linewidth=2, zorder=3)

    # Orange ring = a radial layer; blue inner ellipse = the inner material.
    ax.add_patch(
        Ellipse(
            (cx, top_y),
            2 * rx,
            2 * ry,
            facecolor="#f9d7a7",
            edgecolor="#1f4e79",
            linewidth=2,
            alpha=0.95,
            zorder=4,
        )
    )
    r_inner = 0.72 * rx
    ax.add_patch(
        Ellipse(
            (cx, top_y),
            2 * r_inner,
            2 * ry * 0.72,
            facecolor="#e8f4fb",
            edgecolor="#d97706",
            linestyle="--",
            linewidth=1.6,
            zorder=5,
        )
    )
    ax.plot([cx, cx + rx], [top_y, top_y], color="#68737d", linestyle="--", linewidth=1.1, zorder=6)
    ax.text(cx - 0.56, top_y + 0.02, "轴线 $r=0$", color="#4b5563", fontsize=9, zorder=7)

    # The radial interval between the two concentric ellipses is dr.
    _arrow(ax, (cx + r_inner, top_y + 0.03), (cx + rx, top_y + 0.03), color="#d97706", mutation=11)
    ax.text(cx + 0.86 * rx, top_y + 0.23, "$dr$", color="#a85b00", ha="center", zorder=7)
    _arrow(ax, (cx, top_y - 0.01), (cx + r_inner, top_y - 0.01), color="#2563a6", mutation=10)
    ax.text(cx + 0.34, top_y - 0.19, "$r_i$", color="#2563a6", ha="center", zorder=7)
    ax.annotate(
        "$R$",
        xy=(cx + rx, top_y),
        xytext=(cx + rx + 0.18, top_y - 0.18),
        arrowprops={"arrowstyle": "->", "color": "#c0392b", "lw": 1.2},
        color="#c0392b",
        zorder=7,
    )

    _arrow(ax, (cx - rx - 0.48, bottom_y), (cx - rx - 0.48, top_y), color="#2563a6")
    ax.text(
        cx - rx - 0.70,
        (top_y + bottom_y) / 2,
        "$L$（轴向长度）",
        color="#2563a6",
        rotation=90,
        va="center",
        ha="center",
    )
    ax.text(
        cx + 0.08,
        (top_y + bottom_y) / 2,
        "圆柱体材料",
        color="#4b5563",
        rotation=90,
        va="center",
        ha="center",
        fontsize=9,
    )
    ax.annotate(
        "外表面 $r=R$",
        xy=(cx + rx, top_y - 0.02),
        xytext=(cx + 0.55, top_y + 0.66),
        arrowprops={"arrowstyle": "->", "color": "#c0392b", "lw": 1.2},
        color="#c0392b",
        ha="center",
    )
    ax.text(
        cx,
        bottom_y - 0.49,
        "纵向圆柱示意；顶部同心椭圆表示径向层厚 $dr$",
        ha="center",
        color="#4b5563",
        fontsize=9,
    )
    ax.text(
        cx,
        bottom_y - 0.82,
        r"轴对称模型只离散径向 $r$，公共因子 $2\pi L$ 可约去",
        ha="center",
        color="#4b5563",
        fontsize=9,
    )
    ax.set_xlim(-0.85, 3.75)
    ax.set_ylim(-2.85, 2.55)
    ax.set_aspect("equal")


def _draw_cell(ax):
    """Draw one annular finite-volume control volume."""
    ax.set_title("(b) 环形控制体与 $dr$", pad=12, fontsize=12, fontweight="bold")

    y_cell = 0.30
    R = 1.12
    r_left, r_center, r_right = 0.60, 0.80, 0.98
    ax.add_patch(Circle((0, y_cell), R, facecolor="#f4f8fb", edgecolor="#1f4e79", linewidth=2))
    ax.add_patch(
        Wedge(
            (0, y_cell),
            r_right,
            -34,
            34,
            width=r_right - r_left,
            facecolor="#f9d7a7",
            edgecolor="#d97706",
            linewidth=1.8,
        )
    )
    ax.plot([0, R], [y_cell, y_cell], color="#68737d", linestyle="--", linewidth=1.1)
    for x, label in [
        (r_left, "$r_{i-1/2}$"),
        (r_center, "$r_i$"),
        (r_right, "$r_{i+1/2}$"),
    ]:
        ax.plot([x, x], [y_cell - 0.055, y_cell + 0.055], color="#374151", linewidth=1.2)
        ax.text(x, y_cell - 0.16, label, ha="center", va="top", fontsize=9)
    ax.plot(r_center, y_cell, "o", color="#7c3aed", markersize=6)

    _arrow(ax, (r_left, y_cell - 0.55), (r_right, y_cell - 0.55), color="#d97706", mutation=11)
    ax.text(
        (r_left + r_right) / 2,
        y_cell - 0.69,
        "$dr_i=r_{i+1/2}-r_{i-1/2}$",
        color="#a85b00",
        ha="center",
    )
    _flow_arrow(
        ax,
        (r_left - 0.23, y_cell + 0.16),
        (r_left, y_cell + 0.16),
        "$F_{i-1/2}$",
        text_offset=(0, 0.10),
    )
    _flow_arrow(
        ax,
        (r_right, y_cell + 0.16),
        (r_right + 0.23, y_cell + 0.16),
        "$F_{i+1/2}$",
        text_offset=(0, 0.10),
    )
    ax.text(0.08, 0.96, r"$r=0:\ F_{1/2}=0$（中心对称）", transform=ax.transAxes, color="#166534", fontsize=9)
    ax.text(0.08, 0.89, "$r=R$：Robin 换热/传质边界", transform=ax.transAxes, color="#c0392b", fontsize=9)
    ax.text(
        0.50,
        -0.88,
        r"$V_i=\pi L(r_{i+1/2}^2-r_{i-1/2}^2)$",
        transform=ax.transData,
        ha="center",
        color="#374151",
        fontsize=9,
    )
    ax.text(
        0.50,
        -1.08,
        r"$w_i=(r_{i+1/2}^2-r_{i-1/2}^2)/2$",
        transform=ax.transData,
        ha="center",
        color="#374151",
        fontsize=9,
    )
    ax.set_aspect("equal")
    ax.set_xlim(-1.25, 1.65)
    ax.set_ylim(-1.24, 1.55)


def _draw_balance(ax):
    """Draw the conservative shared-interface balance."""
    ax.set_title("(c) 控制体守恒平衡", pad=12, fontsize=12, fontweight="bold")
    ax.set_xlim(0, 5.0)
    ax.set_ylim(0, 4.75)
    ax.plot([0.45, 4.55], [3.35, 3.35], color="#9ca3af", linewidth=1.4)
    for x, label in [(0.70, "$i-1$"), (2.50, "$i$"), (4.30, "$i+1$")]:
        ax.plot(x, 3.35, "o", color="#7c3aed" if label == "$i$" else "#64748b", markersize=7)
        ax.text(x, 3.62, label, ha="center", color="#374151")
    ax.axvspan(1.35, 3.65, ymin=0.64, ymax=0.78, color="#f9d7a7", alpha=0.9)
    ax.plot([1.35, 1.35], [3.06, 3.64], color="#d97706", linewidth=2)
    ax.plot([3.65, 3.65], [3.06, 3.64], color="#d97706", linewidth=2)
    ax.text(2.5, 3.17, "控制体 $i$", ha="center", va="center", color="#8a4b00")
    _flow_arrow(ax, (1.05, 3.35), (1.32, 3.35), "$F_{i-1/2}$", text_offset=(0, 0.34))
    _flow_arrow(ax, (3.68, 3.35), (3.95, 3.35), "$F_{i+1/2}$", text_offset=(0, 0.34))
    ax.text(
        0.18,
        2.48,
        r"$\rho c_p w_i\,\dot T_i=F^T_{i+1/2}-F^T_{i-1/2}$",
        fontsize=11,
        color="#1f4e79",
    )
    ax.text(
        0.18,
        1.91,
        r"$w_i\,\dot C_i=F^C_{i+1/2}-F^C_{i-1/2}$",
        fontsize=11,
        color="#1f4e79",
    )
    ax.text(
        0.18,
        1.18,
        "相邻控制体共享同一界面通量，\n"
        "全域求和时内部通量成对抵消。",
        fontsize=10,
        color="#374151",
        linespacing=1.6,
    )
    ax.text(
        0.18,
        0.36,
        "均匀网格：$dr_i=R/N$；\n"
        "加密网格：$dr_i$ 随 $r$ 变化；\n"
        "收缩模型：在 $\\xi=r/R(t)$ 中离散。",
        fontsize=9,
        color="#4b5563",
        linespacing=1.5,
    )


def _save_figure(fig, output_dir: Path, stem: str) -> tuple[Path, Path]:
    png_path = output_dir / f"{stem}.png"
    pdf_path = output_dir / f"{stem}.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png_path, pdf_path


def build_figure(output_dir: Path) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "mathtext.fontset": "stix",
            "font.size": 10,
        }
    )

    # First output: the cylinder and the radial thickness dr.
    fig_a, ax_a = plt.subplots(figsize=(6.0, 7.0), facecolor="white")
    _prepare_axis(ax_a)
    _draw_geometry(ax_a)
    fig_a.text(
        0.5,
        0.015,
        "圆柱体顶部的橙色环带表示一个径向有限体积层，层厚为 $dr$。",
        ha="center",
        fontsize=9.5,
        color="#4b5563",
    )
    fig_a.subplots_adjust(left=0.08, right=0.92, top=0.90, bottom=0.08)
    geom_paths = _save_figure(fig_a, output_dir, "圆柱体与dr示意图")

    # Second output: control volume and conservation balance side by side.
    fig_bc = plt.figure(figsize=(12.8, 6.8), facecolor="white")
    grid = fig_bc.add_gridspec(1, 2, width_ratios=[1.14, 1.18], wspace=0.22)
    ax_cell = fig_bc.add_subplot(grid[0, 0])
    ax_balance = fig_bc.add_subplot(grid[0, 1])
    _prepare_axis(ax_cell)
    _prepare_axis(ax_balance)
    _draw_cell(ax_cell)
    _draw_balance(ax_balance)
    fig_bc.suptitle("环形控制体与共享界面通量的守恒离散", fontsize=15, fontweight="bold", y=0.98)
    fig_bc.text(
        0.5,
        0.008,
        "左侧标出控制体厚度 $dr_i$；右侧说明相邻控制体共享界面通量后，内部通量在全域求和时抵消。",
        ha="center",
        fontsize=9.5,
        color="#4b5563",
    )
    fig_bc.subplots_adjust(left=0.04, right=0.98, top=0.88, bottom=0.08)
    control_paths = _save_figure(fig_bc, output_dir, "有限体积离散示意图")
    return geom_paths + control_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="生成圆柱体与有限体积离散示意图")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    for path in build_figure(args.output_dir):
        print(f"saved {path}")


if __name__ == "__main__":
    main()
