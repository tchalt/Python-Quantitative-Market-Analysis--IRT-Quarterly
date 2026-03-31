import argparse
import sys
import os
import pandas as pd
import datetime
import akshare as ak
from config.settings import load_config
from data_layer.fetcher import DataFetcher
from engine.processor import AssetProcessor
from reports.generator import ReportGenerator
from utils.logger import logger
from utils.date_helper import get_current_quarter_info

def main():
    """
    Main entry point for the Global Quarterly Quantitative Analysis Model.
    """
    parser = argparse.ArgumentParser(description="Global Quarterly Quantitative Analysis Model")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass cache and force-fetch data from APIs")
    args = parser.parse_args()

    # 1. Load Configuration
    config = load_config("config/config.yaml")
    logger.info("Configuration loaded successfully.")

    # 2. Initialize Components
    fetcher = DataFetcher(config)
    processor = AssetProcessor(config)
    generator = ReportGenerator(config)
    
    # 3. Currency Watch (FX Rates with Historical Fallback)
    logger.info("Fetching FX Rates (BOC with yfinance fallback)...")
    fx_rates = {}
    current_info = get_current_quarter_info(config)
    
    for pair in config['fx']['pairs']:
        try:
            # Check historical priority
            if config['fx'].get('historical_priority') == 'yfinance':
                # Map pair to yfinance symbol (e.g., USD/CNY -> USDCNY=X)
                mapping = {"USD/CNY": "USDCNY=X", "EUR/CNY": "EURCNY=X", "EUR/USD": "EURUSD=X"}
                yf_symbol = mapping.get(pair)
                if yf_symbol:
                    # Fetch history for the specific period to get average or end rate
                    yf_df = fetcher.get_data(yf_symbol, source="yfinance")
                    if not yf_df.empty:
                        # Use the last closing price of the quarter for the report
                        fx_rates[pair] = round(float(yf_df['Close'].iloc[-1]), 4)
                        continue

            # Fallback to AkShare BOC if yfinance failed or not prioritized
            boc_df = ak.currency_boc_sina()
            currency_map = {"USD/CNY": "美元", "EUR/CNY": "欧元", "EUR/USD": "欧元/美元"}
            target = currency_map.get(pair)
            if target:
                row = boc_df[boc_df['货币名称'] == target]
                if not row.empty:
                    fx_rates[pair] = row['现汇卖出价'].iloc[0]
                else:
                    fx_rates[pair] = "N/A"
        except Exception as e:
            logger.warning(f"Failed to fetch FX {pair}: {str(e)}")
            fx_rates[pair] = "N/A"

    # 4. Market Analysis (Americas, Europe, Asia)
    regional_data = {"americas": [], "europe": [], "asia": [], "commodities": [], "oil": []}
    anomalies = []
    
    # Common Benchmark for global analysis (Stooq)
    bench_ticker = config.get("global", {}).get("benchmark", {}).get("symbol") or "^GSPC"
    bench_df = fetcher.get_data(bench_ticker, force_refresh=args.force_refresh)
    rf_rate = config['global']['risk_free_rate']['default_value']

    # Process Regions
    for region in ["americas", "europe", "asia", "commodities", "oil"]:
        if region == "asia":
            tickers = config['domestic']['banks'] + config['domestic']['others']
            source = "akshare"
            sources_map = config.get("domestic", {}).get("sources", {})
            fallbacks_map = config.get("domestic", {}).get("fallbacks", {})
        elif region == "commodities":
            tickers = config['global']['americas']['commodities']
            fallbacks = config['global']['americas'].get('commodities_fallback', [])
            source = "stooq"
            sources_map = config.get("global", {}).get("americas", {}).get("sources", {})
            fallbacks_map = config.get("global", {}).get("americas", {}).get("fallbacks", {})
        elif region == "oil":
            tickers = config['global']['americas'].get('oil', []) + config['domestic'].get('oil', [])
            fallbacks = []
            source = None
            sources_map = {}
            sources_map.update(config.get("global", {}).get("americas", {}).get("sources", {}))
            sources_map.update(config.get("domestic", {}).get("sources", {}))
            fallbacks_map = {}
            fallbacks_map.update(config.get("global", {}).get("americas", {}).get("fallbacks", {}))
            fallbacks_map.update(config.get("domestic", {}).get("fallbacks", {}))
        else:
            tickers = config['global'][region]['indices']
            fallbacks = []
            source = "stooq"
            sources_map = config.get("global", {}).get(region, {}).get("sources", {})
            fallbacks_map = config.get("global", {}).get(region, {}).get("fallbacks", {})

        for i, ticker in enumerate(tickers):
            try:
                selected_source = sources_map.get(ticker, source)
                if selected_source is None:
                    selected_source = source or "stooq"

                asset_df = fetcher.get_data(ticker, source=selected_source, force_refresh=args.force_refresh)
                
                # Try fallback if primary fails
                if asset_df.empty:
                    if fallbacks and i < len(fallbacks):
                        fallback_ticker = fallbacks[i]
                        logger.info(f"Primary {ticker} failed, trying fallback {fallback_ticker}")
                        asset_df = fetcher.get_data(fallback_ticker, source="yfinance", force_refresh=args.force_refresh)
                    else:
                        for fb in (fallbacks_map.get(ticker) or []):
                            logger.info(f"Primary {ticker} failed, trying fallback {fb}")
                            asset_df = fetcher.get_data(fb, source="yfinance", force_refresh=args.force_refresh)
                            if not asset_df.empty:
                                ticker = fb
                                break

                if asset_df.empty:
                    continue
                
                metrics = processor.process_asset(asset_df, bench_df, rf_rate, ticker)
                if metrics:
                    # Add last price for the report
                    # Handle MultiIndex and Series
                    try:
                        last_price = asset_df['Close'].iloc[-1] if 'Close' in asset_df.columns else asset_df['收盘'].iloc[-1]
                        if isinstance(last_price, (pd.Series, pd.DataFrame)):
                            last_price = float(last_price.iloc[0])
                        else:
                            last_price = float(last_price)
                        metrics['last_price'] = round(last_price, 2)
                    except:
                        metrics['last_price'] = "N/A"
                    
                    metrics["region"] = region
                    regional_data[region].append(metrics)
                    
                    # --- Anomaly Detection ---
                    # 1. Beta Shift (Dummy check vs historical 1.0)
                    if abs(metrics['risk'].get('beta', 1) - 1.0) > 0.3:
                        anomalies.append({
                            "asset": ticker, 
                            "message": f"Significant Beta shift detected: {metrics['risk']['beta']:.2f}"
                        })
                    
                    # 2. Volatility Top 5% (3-year history) for Commodities and Oil
                    if region in ["commodities", "oil"]:
                        vol = metrics['risk'].get('volatility')
                        vol_p95 = metrics['risk'].get('vol_p95')
                        if isinstance(vol, (int, float)) and isinstance(vol_p95, (int, float)) and vol_p95 > 0 and vol > vol_p95:
                            anomalies.append({
                                "asset": ticker,
                                "message": f"Quarterly volatility is in the top 5% of its {config['analysis'].get('lookback_years', 3)}-year history (current={vol:.2%}, p95={vol_p95:.2%})"
                            })
            except Exception as e:
                logger.error(f"Failed to process {ticker}: {str(e)}")

    # 5. Generate and Save Reports
    # Get period info for reporting
    current_info = get_current_quarter_info(config)
    period_label = current_info['period_label']
    
    generator.generate_terminal_report(regional_data, fx_rates, anomalies, period_label=period_label)
    
    # Flatten regional_data for HTML report
    all_processed_assets = []
    for region_assets in regional_data.values():
        all_processed_assets.extend(region_assets)

    generator.generate_html_report(all_processed_assets, fx_rates, anomalies, 
                                   period_label=period_label, 
                                   filename="quarterly_analysis_report.html")

    generator.generate_pdf_report(
        all_processed_assets,
        fx_rates,
        anomalies,
        period_label=period_label,
        filename="quarterly_analysis_report.pdf"
    )
    
    # Save history record
    period_str = f"Q{current_info['quarter']}_{current_info['year']}"
    generator.save_history_report(regional_data, fx_rates, anomalies, period=period_str)
    
    print(f"\nPipeline execution completed. History saved in reports/history/{period_str}_Analysis.txt")

if __name__ == "__main__":
    main()
