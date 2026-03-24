import pandas as pd
from engine.calculator import QuantCalculator
from utils.logger import logger

class AssetProcessor:
    """
    Orchestrates the workflow of transforming raw data into processed metrics.
    """
    def __init__(self, config):
        self.config = config
        self.calculator = QuantCalculator()

    def process_asset(self, asset_df, benchmark_df, rf_rate, asset_name):
        """
        Aligns asset and benchmark data, calculates risk metrics, and determines trends.
        """
        if asset_df.empty or benchmark_df.empty:
            logger.warning(f"Insufficient data to process {asset_name}")
            return None

        # --- Strict Date Filtering ---
        # Ensure we only use data within the requested quarter to avoid boundary spill
        analysis_config = self.config.get('analysis', {})
        start_date = analysis_config.get('start_date')
        end_date = analysis_config.get('end_date')
        
        if start_date and end_date:
            # Convert to DatetimeIndex if not already
            if not isinstance(asset_df.index, pd.DatetimeIndex):
                asset_df.index = pd.to_datetime(asset_df.index)
            if not isinstance(benchmark_df.index, pd.DatetimeIndex):
                benchmark_df.index = pd.to_datetime(benchmark_df.index)
            
            # Localize/Normalize to UTC to avoid timezone mismatches
            if asset_df.index.tz is not None: asset_df.index = asset_df.index.tz_convert(None)
            if benchmark_df.index.tz is not None: benchmark_df.index = benchmark_df.index.tz_convert(None)
            
            # --- LENIENT BOUNDARY ---
            # Use start_date and end_date as bounds, but allow for holiday shifts
            asset_df = asset_df[start_date:end_date]
            benchmark_df = benchmark_df[start_date:end_date]

        if asset_df.empty or benchmark_df.empty:
            logger.warning(f"Data empty after date filtering for {asset_name}")
            return None

        # 1. Align Data by Index (Timestamps)
        # Using Adj Close for return calculation
        # Handle MultiIndex columns from yfinance 1.2.0+
        def get_col(df, names):
            for name in names:
                if name in df.columns:
                    return df[name]
                # Try level 0 if MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    if name in df.columns.get_level_values(0):
                        return df[name]
            return pd.Series(dtype=float)

        asset_close = get_col(asset_df, ['Adj Close', 'Close', '收盘'])
        bench_close = get_col(benchmark_df, ['Adj Close', 'Close', '收盘'])

        # 2. Calculate Returns
        # Drop duplicates and ensure series is 1D (yfinance might return MultiIndex Series)
        if isinstance(asset_close, pd.DataFrame): asset_close = asset_close.iloc[:, 0]
        if isinstance(bench_close, pd.DataFrame): bench_close = bench_close.iloc[:, 0]

        asset_returns = asset_close.pct_change().dropna()
        bench_returns = bench_close.pct_change().dropna()

        # 3. Calculate Risk Metrics
        risk_stats = self.calculator.calculate_risk_metrics(asset_returns, bench_returns, rf_rate)

        # 4. Trend Determination (UP/DOWN for coloring)
        # Total return for the period
        total_return = float((asset_close.iloc[-1] / asset_close.iloc[0]) - 1)
        trend = "UP" if total_return >= 0 else "DOWN"

        # 5. Build Metric Object
        metric_object = {
            "name": asset_name,
            "total_return": round(total_return, 4),
            "trend": trend,
            "risk": risk_stats,
            "period_start": asset_df.index[0].strftime('%Y-%m-%d') if hasattr(asset_df.index[0], 'strftime') else str(asset_df.index[0]),
            "period_end": asset_df.index[-1].strftime('%Y-%m-%d') if hasattr(asset_df.index[-1], 'strftime') else str(asset_df.index[-1])
        }

        return metric_object

    def process_financials(self, financial_data, ticker):
        """
        Processes financial statements and extracts key insights.
        """
        if financial_data.empty:
            logger.warning(f"No financial data for {ticker}")
            return None
            
        analysis_result = self.calculator.analyze_financials(financial_data)
        
        # Add fundamental health score (dummy scoring logic for now)
        health_score = 0
        if "net_income_growth" in analysis_result["metrics"]:
            if analysis_result["metrics"]["net_income_growth"] > 0: health_score += 1
            if analysis_result["metrics"]["net_income_growth"] > 0.15: health_score += 1
        
        if analysis_result["metrics"]["debt_to_equity"] < 1: health_score += 1
        if analysis_result["metrics"]["fcf"] > 0: health_score += 1

        analysis_result["health_score"] = health_score
        return analysis_result
