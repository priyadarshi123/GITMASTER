"""Charts: equity curve with drawdown shading, profit-factor heatmap."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, RED, NEUTRAL = "#2a78d6", "#e34948", "#f0efec"


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def equity_chart(tr: pd.DataFrame, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.5), facecolor=SURFACE)
    _style(ax)
    if tr.empty:
        ax.text(0.5, 0.5, "No trades", ha="center", va="center", color=INK2, transform=ax.transAxes)
    else:
        x = np.r_[0, np.arange(1, len(tr) + 1)]
        eq = np.r_[0.0, tr["pnl"].cumsum().to_numpy()]
        peak = np.maximum.accumulate(eq)
        ax.fill_between(x, eq, peak, where=peak > eq, color=RED, alpha=0.18, lw=0, label="Drawdown")
        ax.plot(x, eq, color=BLUE, lw=2, label="Cumulative net P&L")
        ax.axhline(0, color=AXIS, lw=1)
        # date ticks on the trade-number axis (no empty overnight/weekend space)
        times = pd.DatetimeIndex(tr["exit_time"])
        ticks = np.linspace(1, len(tr), min(8, len(tr))).astype(int)
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{times[k - 1]:%d %b %y}" for k in ticks])
        ax.annotate(f"₹{eq[-1]:,.0f}", (x[-1], eq[-1]), xytext=(6, 0), textcoords="offset points",
                    color=INK, fontsize=9, va="center")
        ax.legend(frameon=False, loc="lower right", bbox_to_anchor=(1, 1.0), ncol=2, fontsize=9,
                  labelcolor=INK2)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.set_ylabel("₹ (1 lot, after costs)", color=INK2, fontsize=9)
    ax.set_xlabel("Trades (dated by exit)", color=INK2, fontsize=9)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=SURFACE)
    plt.close(fig)


def pf_heatmap(grid: pd.DataFrame, title: str, path: Path, pf_col: str = "pf") -> None:
    """Profit factor over a × c (filter on). Diverging at PF = 1: red loses, blue wins."""
    g = grid[grid["filter"]].pivot(index="c", columns="a", values=pf_col).sort_index(ascending=False)
    vals = g.to_numpy(float)
    finite = vals[np.isfinite(vals)]
    span = max(0.25, np.nanmax(np.abs(finite - 1))) if finite.size else 0.5
    norm = TwoSlopeNorm(vcenter=1.0, vmin=1 - span, vmax=1 + span)
    cmap = LinearSegmentedColormap.from_list("pf", [RED, NEUTRAL, BLUE])

    fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    im = ax.imshow(np.clip(vals, 1 - span, 1 + span), cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(g.shape[1]), [f"{v:g}" for v in g.columns])
    ax.set_yticks(range(g.shape[0]), [str(v) for v in g.index])
    ax.set_xlabel("Key Value a", color=INK2, fontsize=9)
    ax.set_ylabel("ATR period c", color=INK2, fontsize=9)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    # 2px surface gap between cells
    ax.set_xticks(np.arange(-0.5, g.shape[1]), minor=True)
    ax.set_yticks(np.arange(-0.5, g.shape[0]), minor=True)
    ax.grid(which="minor", color=SURFACE, lw=2)
    ax.tick_params(which="minor", length=0)
    for r in range(g.shape[0]):
        for c in range(g.shape[1]):
            v = vals[r, c]
            ax.text(c, r, "–" if not np.isfinite(v) else f"{v:.2f}", ha="center", va="center",
                    fontsize=9, color=INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("Profit factor (1.0 = break-even)", color=INK2, fontsize=9)
    cb.ax.tick_params(colors=MUTED, labelsize=8)
    cb.outline.set_visible(False)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=SURFACE)
    plt.close(fig)
