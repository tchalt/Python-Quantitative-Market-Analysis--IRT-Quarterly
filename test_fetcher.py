import os
import sys

# Ensure the root directory is in the Python path
sys.path.append(os.getcwd())

from config.settings import load_config
from data_layer.fetcher import DataFetcher
from utils.logger import logger
from utils.date_helper import get_current_quarter_info

def run_test():
    """
    Simple test script to verify data acquisition from multiple sources.
    """
    logger.info("Starting DataFetcher test...")
    
    try:
        # Load configuration
        config = load_config("config/config.yaml")
        fetcher = DataFetcher(config)
        
        # Current quarter dates
        current_info = get_current_quarter_info()
        start_date = current_info['start_date']
        end_date = current_info['end_date']
        
        # Test 1: Global Data (Stooq)
        ticker_stooq = config['global']['americas']['indices'][0] # ^SPX
        logger.info(f"Test 1: Fetching global index {ticker_stooq} via Stooq...")
        df_stooq = fetcher.get_data(ticker_stooq, start_date, end_date, source="stooq")
        if not df_stooq.empty:
            logger.info(f"Success! Fetched {len(df_stooq)} rows for {ticker_stooq}")
            logger.info(f"Columns: {df_stooq.columns.tolist()}")
            logger.info(f"Index order check (first 2 dates): {df_stooq.index[:2].tolist()}")
            print(df_stooq.head())
        else:
            logger.error(f"Failed to fetch {ticker_stooq}")
        
        # Test 2: Domestic Data (akshare)
        ticker_ak = config['domestic']['banks'][0] # sh601939 (CCB)
        logger.info(f"Test 2: Fetching domestic stock {ticker_ak} via akshare...")
        df_ak = fetcher.get_data(ticker_ak, start_date, end_date, source="akshare")
        if not df_ak.empty:
            logger.info(f"Success! Fetched {len(df_ak)} rows for {ticker_ak}")
            print(df_ak.head())
        else:
            logger.error(f"Failed to fetch {ticker_ak}")
            
    except Exception as e:
        logger.error(f"Test failed with exception: {str(e)}")

if __name__ == "__main__":
    run_test()
