# Global Quarterly Quantitative Analysis Model

Configuration-driven pipeline that fetches global (Stooq with yfinance fallback) and China A-share / BOC FX data (AkShare), computes quarterly risk metrics (Sharpe, Alpha, Beta), and produces a professional terminal + HTML report using the Asian-market convention **Red = Up** / **Green = Down**.

## Features
- Global data via Stooq (`pandas_datareader`) with automatic yfinance fallback when Stooq has gaps
- China A-shares and Bank of China FX via AkShare, with throttling and fallback interfaces
- Local Parquet cache per ticker per quarter to reduce redundant calls
- Quant engine: annualized Sharpe, OLS Beta, Jensen’s Alpha, plus basic anomaly flags
- Reporting: region tables (Americas, Europe, Asia, Commodities) + Currency Watch + Risk Alerts
- Historical-quarter support (e.g., 2025 Q4) driven by `config/config.yaml`

## Project Structure
```text
.
├── config/
│   ├── config.yaml
│   └── settings.py
├── data_layer/
│   ├── fetcher.py
│   └── persistence.py
├── engine/
│   ├── calculator.py
│   └── processor.py
├── reports/
│   ├── generator.py
│   ├── templates/
│   │   └── report_template.html
│   └── history/
├── utils/
│   ├── date_helper.py
│   ├── error_handlers.py
│   └── logger.py
├── cache/
├── logs/
├── main.py
└── requirements.txt
```

## Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.lock
```

## Configure the Quarter (Example: 2025 Q4)
Edit [config.yaml](file:///Users/tangtaowei/Desktop/MC%20PF/Model/config/config.yaml):
- `analysis.start_date: "2025-10-01"`
- `analysis.end_date: "2025-12-31"`
- `analysis.period_label: "2025 Q4 Analysis"`

Tickers for each region/asset class are also configured here (no hardcoding in the engine).

## Run
Generate the report using cached data when available:
```bash
python3 main.py
```

Force-refresh (bypass cache and refetch all assets for the configured quarter):
```bash
python3 main.py --force-refresh
```

## Outputs
- Terminal report:
  - Region tables (Americas / Europe / Asia / Commodities)
  - Currency Watch (BOC FX with yfinance historical fallback)
  - Risk Alerts (anomalies)
- HTML report:
  - `quarterly_analysis_report.html`
- History record:
  - `reports/history/Q4_2025_Analysis.txt` (name changes with quarter/year)
- Logs:
  - `logs/quant_system.log`

## Notes on Data Sources
- **Global indices & assets**: Stooq is attempted first; if the symbol is unavailable or returns insufficient rows, the system falls back to yfinance.
- **FX**:
  - For historical accuracy, the pipeline prioritizes yfinance FX symbols (e.g., `USDCNY=X`) when configured.
  - BOC spot rates are still shown and used as fallback when needed.
- **China A-shares**:
  - The AkShare fetcher includes throttling and uses fallback interfaces to reduce `RemoteDisconnected` / connection-aborted failures.

## Troubleshooting
- If an asset repeatedly fails:
  - Run with `--force-refresh` once to avoid stale cache.
  - Check `logs/quant_system.log` for the exact exception and which fallback path was used.
- If you see missing global tickers:
  - Some Stooq symbols differ from Yahoo symbols; adjust mappings in `config/config.yaml`.
