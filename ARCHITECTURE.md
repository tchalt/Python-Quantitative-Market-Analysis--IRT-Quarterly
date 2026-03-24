# Global Quarterly Quantitative Analysis Model - Architecture Blueprint

## 1. Directory Tree

```text
.
├── config/
│   ├── config.yaml          # Main configuration for tickers, benchmarks, risk-free rates
│   └── settings.py          # Configuration loader and environment variable manager
├── data_layer/
│   ├── __init__.py          # Data layer interface (Strategy Pattern)
│   ├── base_fetcher.py      # Abstract base class for data fetchers
│   ├── global_fetcher.py    # yfinance implementation for US/Europe/FX
│   ├── domestic_fetcher.py  # akshare implementation for A-shares
│   └── persistence.py       # SQLite/Parquet caching logic
├── engine/
│   ├── __init__.py          # Engine orchestrator
│   ├── math_heart.py        # Core calculations: Sharpe, Alpha, Beta, Volatility
│   ├── financial_parser.py  # Logic for parsing quarterly/annual financial statements
│   └── risk_models.py       # Risk-free rate adjustments and benchmark alignment
├── reports/
│   ├── __init__.py
│   ├── terminal_output.py   # Rich/Console output with color-coding
│   ├── html_generator.py    # Jinja2 templates for professional HTML reports
│   └── formatters.py        # "Red-Up/Green-Down" logic and currency formatting
├── utils/
│   ├── __init__.py
│   ├── logger.py            # Centralized logging configuration
│   ├── date_utils.py        # Quarterly date logic and timezone normalization
│   └── error_handlers.py    # Decorators for retry logic and flaky API management
├── cache/                   # (Auto-generated) Local storage for Parquet/SQLite
├── logs/                    # (Auto-generated) Execution logs
├── main.py                  # The pipeline orchestrator
└── requirements.txt         # Project dependencies
```

## 2. Summary of Responsibility

| Module | Responsibility |
| :--- | :--- |
| **config/** | Centralized source of truth. Manages all assets (Americas, Europe, Asia, FX) and benchmarks without code changes. |
| **data_layer/** | Implements the Strategy Pattern for multi-source data retrieval. Manages local caching to optimize API usage. |
| **engine/** | The mathematical core. Translates raw data into quantitative metrics (Sharpe, Alpha, etc.) and parses financial ratios. |
| **reports/** | Handles presentation. Implements localized color schemes (e.g., Red-Up for China/Asia, Green-Up for Global) and formatting. |
| **utils/** | Provides cross-cutting concerns like logging, date arithmetic, and error handling (retries for yfinance/akshare). |
| **main.py** | Orchestrates the end-to-end flow: Load Config -> Fetch Data -> Calculate -> Generate Report. |

## 3. Data Schema Definition

### 3.1. Cached Raw Data (Parquet/SQLite)
*   **Price Data**: `ticker`, `timestamp`, `open`, `high`, `low`, `close`, `volume`, `adj_close`.
*   **Financial Data**: `ticker`, `period` (e.g., "2023Q3"), `report_type` (Q1-Q4), `revenue`, `net_income`, `eps`, `assets`, `liabilities`.

### 3.2. Final Report Data (JSON/DataFrame)
*   **Quantitative Metrics**: `ticker`, `total_return`, `annualized_vol`, `sharpe_ratio`, `max_drawdown`, `alpha`, `beta`.
*   **Fundamental Metrics**: `pe_ratio`, `pb_ratio`, `roe`, `revenue_growth_yoy`, `net_income_growth_yoy`.
*   **Metadata**: `benchmark_name`, `risk_free_rate_used`, `last_updated_timestamp`.

## 4. Annual Report Detection Strategy

The system will use a **Multi-Level Heuristic** to distinguish between a regular Q3 report and a full Annual Report:

1.  **Date Window Matching**: Identify if the report period falls into the "FY" (Fiscal Year) or "Q4" window (typically ending Dec 31st for most global markets).
2.  **Schema Completeness**: Annual reports usually contain comprehensive "Cash Flow" and "Balance Sheet" items that may be condensed in Q1-Q3.
3.  **Audited Flag**: Detection of an "Audited" status in the financial statement metadata (provided by some APIs).
4.  **Period-Over-Period Logic**: If `period == '2023-12-31'` and the previous record was `2023-09-30`, the system treats the 12-31 data as the "Annual Summary" while calculating the delta for Q4-specific performance.
