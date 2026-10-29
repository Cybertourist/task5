# Weyland-Yutani Mining Ops — dashboard

Reads the generator spreadsheet (Google Sheets, sheet `Data`, exported as CSV) and analyses daily output of every mine and the total.

* statistics: mean, standard deviation, median, interquartile range;
* anomaly tests with adjustable parameters: IQR rule, z-score, distance from moving average (%), Grubbs' test;
* line / bar / stacked charts with highlighted anomalies and polynomial trendlines (degree 1–4);
* PDF report with tables, charts and a section for every anomaly.

Run: `pip install -r requirements.txt` and `streamlit run app.py`.
