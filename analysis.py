from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

SHEET_ID = "1tS6hI1AtNH6Br0kz_tDOivoIHo_NwWXNVkmR3A72MRY"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&headers=1&sheet=Data"
TESTS = ["IQR", "Z-score", "Moving average", "Grubbs"]


@dataclass
class Params:
    iqr_k: float = 1.5
    z_threshold: float = 3.0
    ma_window: int = 7
    ma_percent: float = 50.0
    grubbs_alpha: float = 0.05


def load_data(source=CSV_URL):
    df = pd.read_csv(source)
    df = df.loc[:, [c for c in df.columns if not c.startswith("Unnamed") and df[c].notna().any()]]
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.dropna(subset=["Date"]).set_index("Date").apply(pd.to_numeric, errors="coerce")
    df["Total"] = df.sum(axis=1)
    return df


def summary(df):
    q = df.quantile([0.25, 0.75])
    return pd.DataFrame({
        "Mean": df.mean(),
        "Std": df.std(),
        "Median": df.median(),
        "IQR": q.loc[0.75] - q.loc[0.25],
        "Min": df.min(),
        "Max": df.max(),
    }).round(2)


def iqr_outliers(s, k):
    q1, q3 = s.quantile([0.25, 0.75])
    return (s < q1 - k * (q3 - q1)) | (s > q3 + k * (q3 - q1))


def z_outliers(s, threshold):
    return ((s - s.mean()) / s.std()).abs() > threshold


def ma_outliers(s, window, percent):
    ma = s.rolling(window, center=True, min_periods=1).mean()
    return ((s - ma).abs() / ma * 100) > percent


def grubbs_outliers(s, alpha):
    flags = pd.Series(False, index=s.index)
    rest = s.dropna()
    while len(rest) > 2:
        n = len(rest)
        deviation = (rest - rest.mean()).abs()
        g = deviation.max() / rest.std()
        t = stats.t.ppf(1 - alpha / (2 * n), n - 2)
        g_crit = (n - 1) / np.sqrt(n) * np.sqrt(t ** 2 / (n - 2 + t ** 2))
        if g <= g_crit:
            break
        worst = deviation.idxmax()
        flags[worst] = True
        rest = rest.drop(worst)
    return flags


def detect(s, p):
    return pd.DataFrame({
        "IQR": iqr_outliers(s, p.iqr_k),
        "Z-score": z_outliers(s, p.z_threshold),
        "Moving average": ma_outliers(s, p.ma_window, p.ma_percent),
        "Grubbs": grubbs_outliers(s, p.grubbs_alpha),
    })


def anomalies(df, p, tests=TESTS):
    rows = []
    for mine in df.columns:
        s = df[mine]
        flags = detect(s, p)[tests]
        ma = s.rolling(p.ma_window, center=True, min_periods=1).mean()
        for date in flags.index[flags.any(axis=1)]:
            value = s[date]
            rows.append({
                "Date": date, "Mine": mine, "Value": round(value, 2),
                "Expected": round(ma[date], 2),
                "Type": "Spike" if value >= ma[date] else "Drop",
                "Deviation, %": round((value - ma[date]) / ma[date] * 100, 1) if ma[date] else None,
                "Tests": ", ".join(t for t in tests if flags.at[date, t]),
            })
    return pd.DataFrame(rows, columns=["Date", "Mine", "Value", "Expected", "Type", "Deviation, %", "Tests"])


def trend(s, degree):
    x = np.arange(len(s))
    mask = s.notna().to_numpy()
    coef = np.polyfit(x[mask], s.to_numpy()[mask], degree)
    return pd.Series(np.polyval(coef, x), index=s.index)


def anomaly_counts(df, p):
    return pd.DataFrame({mine: detect(df[mine], p).sum() for mine in df.columns}).T
