import io
from datetime import datetime

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from analysis import anomalies, anomaly_counts, summary, trend

COLORS = ["#2a6fdb", "#e8590c", "#2b8a3e", "#ae3ec9", "#f59f00", "#0c8599", "#c92a2a", "#5c940d", "#364fc7", "#862e9c"]
styles = getSampleStyleSheet()
MAX_SECTIONS = 40


def table(df, col_widths=None):
    data = [list(df.columns)] + df.astype(str).values.tolist()
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    return t


def figure(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=17 * cm, height=17 * cm * fig.get_figheight() / fig.get_figwidth())


def overview_chart(df, mines, kind, degree, found):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = df.index
    if kind == "Stacked":
        ax.stackplot(x, [df[m] for m in mines], labels=mines, colors=COLORS, alpha=0.8)
        total = df[mines].sum(axis=1)
        ax.plot(x, trend(total, degree), "k--", lw=1.5, label=f"Trend (deg {degree})")
    else:
        width = 0.8 / len(mines)
        for i, m in enumerate(mines):
            c = COLORS[i % len(COLORS)]
            if kind == "Bar":
                offset = pd.Timedelta(days=(i - (len(mines) - 1) / 2) * width)
                ax.bar(x + offset, df[m], width=width, color=c, label=m)
            else:
                ax.plot(x, df[m], color=c, lw=1.2, label=m)
            ax.plot(x, trend(df[m], degree), "--", color=c, lw=1)
            pts = found[found["Mine"] == m]
            ax.scatter(pts["Date"], pts["Value"], color="red", s=22, zorder=5)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.set_ylabel("Output")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, ncol=4)
    fig.autofmt_xdate()
    return fig


def anomaly_chart(s, date, ma_window):
    window = s[(s.index >= date - pd.Timedelta(days=10)) & (s.index <= date + pd.Timedelta(days=10))]
    fig, ax = plt.subplots(figsize=(8, 2.6))
    ax.plot(window.index, window, color="#2a6fdb", lw=1.5, marker="o", ms=3)
    ax.plot(window.index, s.rolling(ma_window, center=True, min_periods=1).mean()[window.index],
            "--", color="gray", lw=1, label="Moving average")
    ax.scatter([date], [s[date]], color="red", s=60, zorder=5, label="Anomaly")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
    return fig


def build_pdf(df, mines, kind, degree, params, tests):
    found = anomalies(df[mines + ["Total"]], params, tests)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm, title="Mining Ops Report")
    h1, h2, h3, body = styles["Title"], styles["Heading2"], styles["Heading3"], styles["BodyText"]
    story = [
        Paragraph("Weyland-Yutani Corporation — Mining Ops Report", h1),
        Paragraph(f"Period: {df.index.min():%Y-%m-%d} — {df.index.max():%Y-%m-%d} ({len(df)} days). "
                  f"Mines: {', '.join(mines)}. Generated {datetime.now():%Y-%m-%d %H:%M}.", body),
        Paragraph(f"Tests: {', '.join(tests)}. IQR k = {params.iqr_k}, z-score threshold = {params.z_threshold}, "
                  f"moving average window = {params.ma_window} days / {params.ma_percent}%, "
                  f"Grubbs alpha = {params.grubbs_alpha}.", body),
        Spacer(1, 0.4 * cm),
        Paragraph("Summary statistics", h2),
        table(summary(df[mines + ["Total"]]).reset_index(names="Mine")),
        Spacer(1, 0.4 * cm),
        Paragraph("Anomalies per test", h2),
        table(anomaly_counts(df[mines + ["Total"]], params)[tests].reset_index(names="Mine")),
        Spacer(1, 0.4 * cm),
        Paragraph(f"Daily output ({kind.lower()} chart, polynomial trend of degree {degree})", h2),
        figure(overview_chart(df, mines, kind, degree, found)),
        PageBreak(),
        Paragraph(f"Anomalies ({len(found)})", h2),
    ]
    found = found.reindex(found["Deviation, %"].abs().sort_values(ascending=False).index)
    if len(found) > MAX_SECTIONS:
        story.append(Paragraph(f"The {MAX_SECTIONS} largest deviations are shown; the full list is in the dashboard.", body))
        found = found.head(MAX_SECTIONS)
    if found.empty:
        story.append(Paragraph("No anomalies detected with the current parameters.", body))
    for i, a in enumerate(found.to_dict("records"), 1):
        story += [
            Paragraph(f"{i}. {a['Type']} — {a['Mine']}, {a['Date']:%Y-%m-%d}", h3),
            Paragraph(f"Value <b>{a['Value']}</b>, moving average {a['Expected']} "
                      f"({a['Deviation, %']:+.1f}%). Detected by: {a['Tests']}.", body),
            figure(anomaly_chart(df[a['Mine']], a['Date'], params.ma_window)),
            Spacer(1, 0.3 * cm),
        ]
    doc.build(story)
    return buf.getvalue()
