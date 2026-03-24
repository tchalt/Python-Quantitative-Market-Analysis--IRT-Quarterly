import os
import sys
import pandas as pd
import numpy as np

# Root to Python path
sys.path.append(os.getcwd())

from config.settings import load_config
from data_layer.fetcher import DataFetcher
from engine.processor import AssetProcessor
from utils.logger import logger

def run_engine_test():
    """
    Test script for verifying quantitative calculations.
    """
    logger.info("Starting Engine test...")
    config = load_config("config/config.yaml")
    fetcher = DataFetcher(config)
    processor = AssetProcessor(config)

    # 1. Risk Metrics Test (Using cached S&P 500)
    # Note: Using ^SPX as both asset and benchmark for this simple test to verify Beta=1
    logger.info("Test 1: Risk Metrics Calculation (S&P 500)")
    asset_df = fetcher.get_data("^SPX")
    bench_df = fetcher.get_data("^SPX")
    rf_rate = 0.045 # 4.5% annual
    
    metrics = processor.process_asset(asset_df, bench_df, rf_rate, "S&P 500 Test")
    if metrics:
        logger.info(f"Asset: {metrics['name']}")
        logger.info(f"Total Return: {metrics['total_return']:.2%}")
        logger.info(f"Sharpe Ratio: {metrics['risk']['sharpe']}")
        logger.info(f"Beta (expected ~1.0): {metrics['risk']['beta']}")
        logger.info(f"Jensen's Alpha: {metrics['risk']['alpha']}")
    else:
        logger.error("Failed to process asset.")

    # 2. Financial Statement Analysis Test
    logger.info("Test 2: Financial Statement Analysis (Mock Data)")
    mock_financials = pd.DataFrame([
        {
            "ticker": "CCB",
            "period": "2024-09-30", # Q3
            "net_income": 1000,
            "total_assets": 10000,
            "total_liabilities": 6000,
            "fcf": 200
        },
        {
            "ticker": "CCB",
            "period": "2024-12-31", # Annual
            "net_income": 1500, # 50% growth
            "total_assets": 11000,
            "total_liabilities": 6200,
            "fcf": 300
        }
    ])
    
    fin_result = processor.process_financials(mock_financials, "CCB")
    if fin_result:
        logger.info(f"Report Type: {fin_result['report_type']}")
        logger.info(f"Net Income Growth: {fin_result['metrics'].get('net_income_growth', 'N/A'):.2%}")
        logger.info(f"Debt-to-Equity: {fin_result['metrics']['debt_to_equity']}")
        logger.info(f"Anomalies: {fin_result['anomalies']}")
        logger.info(f"Fundamental Health Score: {fin_result['health_score']}/4")

if __name__ == "__main__":
    run_engine_test()
