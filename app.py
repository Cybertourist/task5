import plotly.graph_objects as go
import streamlit as st

from analysis import CSV_URL, TESTS, Params, anomalies, anomaly_counts, load_data, summary, trend
from report import COLORS, build_pdf

st.set_page_config(page_title="Mining Ops Dashboard", page_icon="⛏️", layout="wide")


@st.cache_data(ttl=60)
def get_data(url):
    return load_data(url)


st.sidebar.title("⛏️ Mining Ops")
url = st.sidebar.text_input("Data source (CSV)", CSV_URL)
if st.sidebar.button("🔄 Refresh data", use_container_width=True):
    get_data.clear()
df = get_data(url)
all_mines = [c for c in df.columns if c != "Total"]

mines = st.sidebar.multiselect("Mines", all_mines, default=all_mines) or all_mines
kind = st.sidebar.radio("Chart type", ["Line", "Bar", "Stacked"], horizontal=True)
degree = st.sidebar.select_slider("Trendline (polynomial degree)", [1, 2, 3, 4], value=2)

st.sidebar.subheader("Anomaly tests")
tests = st.sidebar.multiselect("Tests", TESTS, default=TESTS) or TESTS
p = Params(
    iqr_k=st.sidebar.slider("IQR rule: k", 0.5, 4.0, 1.5, 0.1),
    z_threshold=st.sidebar.slider("Z-score: threshold", 1.0, 5.0, 3.0, 0.1),
    ma_window=st.sidebar.slider("Moving average: window, days", 3, 31, 7, 2),
    ma_percent=st.sidebar.slider("Moving average: max distance, %", 5, 200, 50, 5),
    grubbs_alpha=st.sidebar.select_slider("Grubbs: alpha", [0.001, 0.01, 0.05, 0.1], value=0.05),
)

data = df[mines + ["Total"]]
found = anomalies(data, p, tests)

st.title("Weyland-Yutani · Mining Ops Dashboard")
st.caption(f"{df.index.min():%Y-%m-%d} — {df.index.max():%Y-%m-%d} · {len(df)} days · {len(mines)} mines")

stats = summary(data)
cols = st.columns(5)
cols[0].metric("Mean daily output (total)", f"{stats.at['Total', 'Mean']:,.1f}")
cols[1].metric("Std deviation", f"{stats.at['Total', 'Std']:,.1f}")
cols[2].metric("Median", f"{stats.at['Total', 'Median']:,.1f}")
cols[3].metric("Interquartile range", f"{stats.at['Total', 'IQR']:,.1f}")
cols[4].metric("Anomalies found", len(found))

chart_tab, stats_tab, anomalies_tab = st.tabs(["📈 Output", "📊 Statistics", "⚠️ Anomalies"])

with chart_tab:
    fig = go.Figure()
    x = data.index
    if kind == "Stacked":
        for i, m in enumerate(mines):
            fig.add_bar(x=x, y=data[m], name=m, marker_color=COLORS[i % len(COLORS)])
        fig.update_layout(barmode="stack")
        fig.add_scatter(x=x, y=trend(data["Total"], degree), name=f"Total trend (deg {degree})",
                        line=dict(color="black", dash="dash"))
        pts = found[found["Mine"] == "Total"]
        fig.add_scatter(x=pts["Date"], y=pts["Value"], mode="markers", name="Total anomalies",
                        marker=dict(color="red", size=11, symbol="x"))
    else:
        for i, m in enumerate(mines):
            color = COLORS[i % len(COLORS)]
            if kind == "Bar":
                fig.add_bar(x=x, y=data[m], name=m, marker_color=color)
            else:
                fig.add_scatter(x=x, y=data[m], name=m, mode="lines", line=dict(color=color))
            fig.add_scatter(x=x, y=trend(data[m], degree), name=f"{m} trend", showlegend=False,
                            line=dict(color=color, dash="dash", width=1.5))
            pts = found[found["Mine"] == m]
            fig.add_scatter(x=pts["Date"], y=pts["Value"], mode="markers", name=f"{m} anomalies",
                            marker=dict(color="red", size=9, line=dict(color=color, width=2)))
        fig.update_layout(barmode="group")
    fig.update_layout(height=520, hovermode="x unified", legend=dict(orientation="h", y=1.08),
                      margin=dict(l=10, r=10, t=40, b=10), yaxis_title="Output")
    st.plotly_chart(fig, use_container_width=True)

with stats_tab:
    st.subheader("Summary statistics")
    st.dataframe(stats, use_container_width=True)
    st.subheader("Anomalies per test")
    st.dataframe(anomaly_counts(data, p)[tests], use_container_width=True)

with anomalies_tab:
    st.dataframe(
        found.sort_values(["Date", "Mine"]),
        hide_index=True, use_container_width=True,
        column_config={"Date": st.column_config.DateColumn(format="YYYY-MM-DD")},
    )

st.divider()
if st.button("📄 Generate PDF report", type="primary"):
    with st.spinner("Building the report..."):
        st.session_state.pdf = build_pdf(df, mines, kind, degree, p, tests)
if "pdf" in st.session_state:
    st.download_button("⬇️ Download report.pdf", st.session_state.pdf, "mining_report.pdf", "application/pdf")
