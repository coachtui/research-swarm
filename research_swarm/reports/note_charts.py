"""
Chart generation for the research-note PDF.

All charts are built in-house with matplotlib (already a project dependency)
and rendered to SVG strings that WeasyPrint embeds natively — no chart
service, no licensing, milliseconds per report. Data comes from the same
feeds the analysis already uses: cached yfinance history plus the stored
run's own valuation anchors.

The signature chart is the Divergence Map: price history flowing into the
intrinsic fair-value band, the street consensus line, and the DVRG
bull/base/bear fan with the persistence weighting stated. It is a literal
picture of the computation that produces the rating — the one chart a
grades-based competitor cannot print.

Every builder returns None on missing data; the template renders nothing
rather than an empty frame, and a chart failure never blocks the report.
"""

from __future__ import annotations

import io
from datetime import timedelta
from typing import Any, Dict, Optional

from research_swarm.logger import logger

# ── Palette: must match pdf_styles.py ────────────────────────────────────────
INK = "#1A2233"
MUTED = "#8A93A0"
FAINT = "#C7CDD4"
ACCENT = "#0E6E5C"
FILL = "#E3EFEB"
GRID = "#EDF0F2"
AMBER = "#8A6410"
RED = "#9C3325"

_RC = {
    # Helvetica on mac, DejaVu on the Railway container — both read cleanly
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7.2,
    "text.color": INK,
    "axes.edgecolor": FAINT,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "svg.fonttype": "none",
}


def _fig_to_svg(fig) -> str:
    import matplotlib.pyplot as plt

    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    svg = buf.getvalue()
    # strip the XML prolog so the fragment inlines cleanly into HTML
    return svg[svg.index("<svg"):]


def _bare(ax, grid_axis="y"):
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "left", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def build_divergence_map(
    history,                      # DataFrame with Date index or column + Close
    fair_value: Dict[str, Any],   # fair_value_low/mid/high
    targets: Dict[str, Any],      # bull/base/bear_target, persistence_probability
    consensus_target: Optional[float],
    num_analysts: Optional[int],
) -> Optional[str]:
    """Price · intrinsic band · consensus · DVRG target fan, one canvas."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
        import pandas as pd

        close = _close_series(history)
        if close is None or len(close) < 60:
            return None

        bull = targets.get("bull_target")
        base = targets.get("base_target")
        bear = targets.get("bear_target")
        if not (bull and base and bear):
            return None

        fv_lo = fair_value.get("fair_value_low")
        fv_mid = fair_value.get("fair_value_mid")
        fv_hi = fair_value.get("fair_value_high")
        p = targets.get("persistence_probability")

        last_date = close.index[-1]
        last_px = float(close.iloc[-1])
        fwd = last_date + timedelta(days=250)
        note_x = last_date + timedelta(days=30)

        lo_bound = min(
            float(close.min()), bear, (fv_lo or bear)
        ) * 0.94
        hi_bound = max(
            float(close.max()), bull, (fv_hi or bull), consensus_target or 0
        ) * 1.10

        with plt.rc_context(_RC):
            fig, ax = plt.subplots(figsize=(4.9, 2.15), dpi=100)

            ax.plot(close.index, close.values, color=INK, linewidth=0.9, zorder=3)
            ax.fill_between(close.index, close.values, lo_bound, color=FILL,
                            linewidth=0, zorder=1)

            if fv_lo and fv_hi:
                ax.fill_between([last_date, fwd], fv_lo, fv_hi,
                                color="#F0F2F4", zorder=0)
                ax.annotate("Intrinsic value band", (note_x, fv_lo + (fv_hi - fv_lo) * 0.06),
                            fontsize=6.2, color=MUTED)
            if fv_mid:
                ax.hlines(fv_mid, last_date, fwd, color=MUTED, linewidth=0.7,
                          linestyle=(0, (4, 3)))
                ax.annotate(f"fair value ${fv_mid:,.2f}", (note_x, fv_mid),
                            textcoords="offset points", xytext=(0, 3),
                            fontsize=6.2, color=MUTED)

            if consensus_target:
                ax.hlines(consensus_target, last_date, fwd, color=AMBER,
                          linewidth=0.8, linestyle=(0, (1, 2)))
                label = f"Street consensus ${consensus_target:,.2f}"
                if num_analysts:
                    label += f" · {num_analysts} analysts"
                ax.annotate(label, (note_x, consensus_target),
                            textcoords="offset points", xytext=(0, 3),
                            fontsize=6.2, color=AMBER)

            for tgt, color, name in ((bull, ACCENT, "Bull"), (base, INK, "Base"),
                                     (bear, RED, "Bear")):
                ax.plot([last_date, fwd], [last_px, tgt], color=color,
                        linewidth=1.0 if name == "Base" else 0.8, zorder=4,
                        linestyle="-" if name == "Base" else (0, (5, 2)))
                ax.annotate(f"{name} ${tgt:,.2f}", (fwd, tgt),
                            textcoords="offset points", xytext=(4, -2),
                            fontsize=6.8, color=color,
                            fontweight="bold" if name == "Base" else "normal",
                            bbox=dict(boxstyle="square,pad=0.12",
                                      fc="white", ec="none"))

            ax.plot([last_date], [last_px], marker="o", markersize=3.4,
                    color=INK, zorder=5)
            ax.annotate(f"${last_px:,.2f}", (last_date, last_px),
                        textcoords="offset points", xytext=(-4, 7), ha="right",
                        fontsize=7.2, fontweight="bold", color=INK)

            if p is not None:
                ax.annotate(
                    f"DVRG base target weights street persistence {p:.0%} "
                    f"vs intrinsic reversion {1 - p:.0%}",
                    (0.012, 0.965), xycoords="axes fraction",
                    fontsize=6.4, color=INK, va="top")

            ax.set_xlim(close.index[0], fwd + timedelta(days=48))
            ax.set_ylim(lo_bound, hi_bound)
            ax.yaxis.tick_right()
            ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
            _bare(ax)
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

            return _fig_to_svg(fig)
    except Exception as e:
        logger.warning(f"Divergence map failed (non-fatal): {e}")
        return None


def build_price_volume(history) -> Optional[str]:
    """12-month price with 200-day MA and a muted volume lane."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt

        close = _close_series(history)
        volume = _column(history, "Volume")
        if close is None or len(close) < 60:
            return None
        ma200 = close.rolling(200, min_periods=60).mean()

        with plt.rc_context(_RC):
            if volume is not None:
                fig, (ax, axv) = plt.subplots(
                    2, 1, figsize=(4.9, 1.6), dpi=100, sharex=True,
                    gridspec_kw={"height_ratios": [4, 1], "hspace": 0.08})
            else:
                fig, ax = plt.subplots(figsize=(4.9, 1.35), dpi=100)
                axv = None

            ax.fill_between(close.index, close.values, float(close.min()) * 0.97,
                            color=FILL, linewidth=0)
            ax.plot(close.index, close.values, color=INK, linewidth=0.9)
            ax.plot(ma200.index, ma200.values, color=MUTED, linewidth=0.8,
                    linestyle=(0, (4, 3)))
            ax.plot([close.index[-1]], [close.iloc[-1]], marker="o",
                    markersize=3, color=ACCENT)
            ax.annotate(f"${close.iloc[-1]:,.2f}", (close.index[-1], close.iloc[-1]),
                        textcoords="offset points", xytext=(-2, 6), ha="right",
                        fontsize=7.2, fontweight="bold", color=INK)
            mid = len(close) * 2 // 3
            if ma200.iloc[mid] == ma200.iloc[mid]:  # not NaN
                ax.annotate("200-day", (close.index[mid], ma200.iloc[mid]),
                            textcoords="offset points", xytext=(0, -11),
                            fontsize=6.2, color=MUTED)
            ax.yaxis.tick_right()
            ax.set_ylim(float(close.min()) * 0.95, float(close.max()) * 1.06)
            _bare(ax)

            if axv is not None:
                axv.bar(volume.index, volume.values / 1e6, width=1.1,
                        color=FAINT, linewidth=0)
                axv.set_yticks([])
                axv.set_ylabel("Vol", rotation=0, fontsize=6.0,
                               labelpad=10, va="center")
                _bare(axv)
                axv.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
                axv.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            else:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

            return _fig_to_svg(fig)
    except Exception as e:
        logger.warning(f"Price/volume chart failed (non-fatal): {e}")
        return None


def build_quarterly_bars(labels, values, estimate_last: bool = False,
                         fmt: str = "{:,.2f}") -> Optional[str]:
    """Small quarterly bar chart (revenue in $B, or EPS)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        pairs = [(l, v) for l, v in zip(labels, values) if v is not None]
        if len(pairs) < 3:
            return None
        labels = [p[0] for p in pairs]
        values = [float(p[1]) for p in pairs]

        with plt.rc_context(_RC):
            fig, ax = plt.subplots(figsize=(2.35, 1.1), dpi=100)
            colors = [INK] * len(values)
            bars = ax.bar(labels, values, width=0.62, color=colors, linewidth=0)
            if estimate_last:
                bars[-1].set_color(FAINT)
                bars[-1].set_hatch("////")
                bars[-1].set_edgecolor(MUTED)
            for b, v in zip(bars, values):
                ax.annotate(fmt.format(v),
                            (b.get_x() + b.get_width() / 2, v),
                            textcoords="offset points", xytext=(0, 2),
                            ha="center", fontsize=6.0, color=INK)
            top = max(values)
            bottom = min(0.0, min(values))
            ax.set_ylim(bottom * 1.25 if bottom < 0 else 0, top * 1.22)
            if bottom < 0:
                ax.axhline(0, color=FAINT, linewidth=0.7)
            ax.set_yticks([])
            for side in ("top", "left", "right"):
                ax.spines[side].set_visible(False)
            ax.tick_params(length=0, labelsize=6.0)
            return _fig_to_svg(fig)
    except Exception as e:
        logger.warning(f"Quarterly bar chart failed (non-fatal): {e}")
        return None


# ── Data access helpers ──────────────────────────────────────────────────────

def _dt_index(df):
    """Normalize to a tz-naive DatetimeIndex. Cached history stores Date as
    strings whose UTC offsets straddle a DST change, so parse with utc=True."""
    import pandas as pd

    if "Date" in df.columns:
        idx = pd.to_datetime(df["Date"], utc=True)
    elif isinstance(df.index, pd.DatetimeIndex):
        idx = df.index
    else:
        idx = pd.to_datetime(df.index, utc=True)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(None) if hasattr(idx, "tz_convert") else idx.tz_localize(None)
    return idx


def _close_series(history):
    import pandas as pd

    if history is None:
        return None
    df = history
    if not isinstance(df, pd.DataFrame) or df.empty or "Close" not in df:
        return None
    try:
        idx = _dt_index(df)
    except Exception:
        return None
    return pd.Series(df["Close"].values, index=idx).dropna()


def _column(history, name):
    import pandas as pd

    if history is None or not isinstance(history, pd.DataFrame) or name not in history:
        return None
    try:
        idx = _dt_index(history)
    except Exception:
        return None
    return pd.Series(history[name].values, index=idx).dropna()


def build_note_charts(stock, ticker: str) -> Dict[str, str]:
    """Assemble every chart for one stock. Missing data → missing key."""
    from research_swarm.data.market_data_client import market_data_client

    charts: Dict[str, str] = {}

    history = None
    try:
        history = market_data_client.get_historical_data(ticker, period="1y")
    except Exception as e:
        logger.warning(f"History fetch for charts failed ({ticker}): {e}")

    # Divergence Map — the signature
    pt = stock.price_targets or {}
    consensus = None
    n_analysts = None
    ac = stock.analyst_consensus or {}
    if isinstance(ac, dict):
        consensus = ac.get("avg_price_target")
        n_analysts = sum(
            ac.get(k, 0) or 0
            for k in ("strong_buy", "buy", "hold", "sell", "strong_sell")
        ) or None
    if history is not None and pt:
        svg = build_divergence_map(history, pt, pt, consensus, n_analysts)
        if svg:
            charts["divergence_map"] = svg

    if history is not None:
        svg = build_price_volume(history)
        if svg:
            charts["price_volume"] = svg

    # Quarterly bars from the filing-extracted metrics (values in $ millions)
    qm = stock.quarterly_metrics or []
    if qm:
        labels, revenue, net_income = [], [], []
        for row in qm[-5:]:
            get = row.get if isinstance(row, dict) else lambda k, d=None: getattr(row, k, d)
            # "Q3_2025" → "Q3'25"
            raw = str(get("quarter") or "")
            parts = raw.replace("-", "_").split("_")
            labels.append(f"{parts[0]}'{parts[1][-2:]}" if len(parts) == 2 else raw)
            rev = get("revenue")
            revenue.append(rev / 1000 if rev else None)
            net_income.append(get("net_income"))
        svg = build_quarterly_bars(labels, revenue, fmt="{:,.2f}")
        if svg:
            charts["quarterly_revenue"] = svg
        svg = build_quarterly_bars(labels, net_income, fmt="{:,.0f}")
        if svg:
            charts["quarterly_net_income"] = svg

    logger.info(f"Note charts for {ticker}: {sorted(charts.keys()) or 'none'}")
    return charts
