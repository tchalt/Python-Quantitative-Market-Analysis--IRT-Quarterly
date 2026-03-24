import os
import pandas as pd
from utils.logger import logger

class CacheManager:
    """
    Manages local caching for dataframes using Parquet.
    """
    def __init__(self, cache_dir="cache"):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def _get_cache_path(self, ticker, period):
        """Generates a file path for caching."""
        # Sanitize ticker (remove ^, =, /, etc.)
        safe_ticker = ticker.replace("^", "").replace("=", "").replace("/", "_")
        return os.path.join(self.cache_dir, f"{safe_ticker}_{period}.parquet")

    def get(self, ticker, period):
        """Loads a dataframe from cache if it exists."""
        cache_path = self._get_cache_path(ticker, period)
        if os.path.exists(cache_path):
            logger.info(f"Loading {ticker} from cache: {cache_path}")
            return pd.read_parquet(cache_path)
        return None

    def save(self, ticker, period, df):
        """Saves a dataframe to cache."""
        if df is None or df.empty or len(df) < 1:
            logger.warning(f"Attempted to save empty/invalid dataframe for {ticker} at {period}")
            return
        
        # Ensure directory exists again (just in case)
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        cache_path = self._get_cache_path(ticker, period)
        try:
            df.to_parquet(cache_path)
            logger.info(f"Saved {ticker} to cache: {cache_path}")
        except Exception as e:
            logger.error(f"Failed to save {ticker} to cache: {str(e)}")
