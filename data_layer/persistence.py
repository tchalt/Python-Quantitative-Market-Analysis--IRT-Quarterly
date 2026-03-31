import os
import json
import datetime
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

    def _get_meta_path(self, ticker, period):
        safe_ticker = ticker.replace("^", "").replace("=", "").replace("/", "_")
        return os.path.join(self.cache_dir, f"{safe_ticker}_{period}.meta.json")

    def get(self, ticker, period):
        """Loads a dataframe from cache if it exists."""
        cache_path = self._get_cache_path(ticker, period)
        if os.path.exists(cache_path):
            logger.info(f"Loading {ticker} from cache: {cache_path}")
            df = pd.read_parquet(cache_path)
            meta_path = self._get_meta_path(ticker, period)
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        df.attrs["cache_meta"] = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read cache meta for {ticker}: {str(e)}")
            return df
        return None

    def validate_df(self, df, min_rows=None):
        if df is None or df.empty:
            return False, "empty"
        try:
            idx = df.index
            if not isinstance(idx, pd.DatetimeIndex):
                idx = pd.to_datetime(idx)
            if idx.tz is not None:
                idx = idx.tz_convert(None)
            if not idx.is_monotonic_increasing:
                return False, "index_not_sorted"
        except Exception:
            return False, "bad_index"

        cols = set(df.columns.astype(str))
        if not (("Close" in cols) or ("Adj Close" in cols) or ("收盘" in cols)):
            return False, "missing_close"

        if min_rows is not None and len(df) < int(min_rows):
            return False, "too_few_rows"

        return True, "ok"

    def save(self, ticker, period, df, meta=None, min_rows=None):
        """Saves a dataframe to cache."""
        ok, reason = self.validate_df(df, min_rows=min_rows)
        if not ok:
            logger.warning(f"Skip cache save for {ticker} at {period}: {reason}")
            return
        
        # Ensure directory exists again (just in case)
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        cache_path = self._get_cache_path(ticker, period)
        try:
            df.to_parquet(cache_path)
            logger.info(f"Saved {ticker} to cache: {cache_path}")
            if meta is not None:
                meta_path = self._get_meta_path(ticker, period)
                payload = dict(meta)
                payload["saved_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save {ticker} to cache: {str(e)}")
