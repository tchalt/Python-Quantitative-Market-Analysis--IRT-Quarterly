import pandas as pd
import pandas_datareader.data as web
import akshare as ak
import yfinance as yf
import time
import random
from utils.logger import logger
from utils.error_handlers import fetch_with_retry
from data_layer.persistence import CacheManager
from utils.date_helper import get_current_quarter_info

class DataFetcher:
    """
    Orchestrates data acquisition from multiple sources with caching and retries.
    Uses Stooq/yfinance for Global data and Akshare for Domestic data.
    """
    def __init__(self, config):
        self.config = config
        self.cache = CacheManager(self.config['analysis']['cache_dir'])
        self.stooq_retries = self.config['api'].get('yfinance', {}).get('retries', 3)
        self.akshare_timeout = self.config['api'].get('akshare', {}).get('timeout', 60)
        self.akshare_retries = self.config['api'].get('akshare', {}).get('retries', 5)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    @fetch_with_retry(retries=3, delay=2)
    def fetch_stooq_data(self, ticker, start_date, end_date):
        """
        Fetches historical price data using Stooq via pandas_datareader.
        """
        logger.info(f"Fetching Stooq data for {ticker} from {start_date} to {end_date}")
        try:
            df = web.DataReader(ticker, 'stooq', start=start_date, end=end_date)
            if df.empty:
                logger.warning(f"No data returned for {ticker} from Stooq")
                return pd.DataFrame()
            df = df.sort_index(ascending=True)
            df.index.name = 'Date'
            if 'Close' in df.columns and 'Adj Close' not in df.columns:
                df['Adj Close'] = df['Close']
            df = df.ffill()
            return df
        except Exception as e:
            logger.error(f"Stooq API error for {ticker}: {str(e)}")
            return pd.DataFrame()

    @fetch_with_retry(retries=3, delay=2)
    def fetch_yfinance_data(self, ticker, start_date, end_date):
        """
        Fetches historical price data using yfinance as fallback.
        """
        logger.info(f"Fetching yfinance data for {ticker} from {start_date} to {end_date}")
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if data.empty:
                return pd.DataFrame()
            # Handle MultiIndex if necessary
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return data
        except Exception as e:
            logger.error(f"yfinance error for {ticker}: {str(e)}")
            return pd.DataFrame()

    @fetch_with_retry(retries=5, delay=5)
    def fetch_akshare_data(self, ticker, start_date, end_date):
        """
        Fetches historical price data for A-shares with throttling and fallback.
        """
        logger.info(f"Fetching akshare data for {ticker} from {start_date} to {end_date}")
        time.sleep(random.uniform(1, 3)) # Throttling
        
        symbol = ticker.replace("sh", "").replace("sz", "")
        start_date_str = start_date.replace("-", "")
        end_date_str = end_date.replace("-", "")

        try:
            if ticker.startswith("sh") or ticker.startswith("sz"):
                if ticker in ["sh000001", "sz399001", "sh000300"]:
                    df = ak.index_zh_a_hist(symbol=ticker, period="daily", 
                                            start_date=start_date_str, 
                                            end_date=end_date_str)
                else:
                    # Try multiple interfaces for A-shares
                    try:
                        # Try EastMoney interface first (usually more stable)
                        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                                start_date=start_date_str, 
                                                end_date=end_date_str,
                                                adjust="hfq")
                    except Exception:
                        logger.warning(f"stock_zh_a_hist failed for {ticker}, trying fallback interfaces")
                        # Interface 1: Sina fallback
                        try:
                            df = ak.stock_zh_a_daily(symbol=ticker, start_date=start_date_str, end_date=end_date_str)
                        except: 
                            df = pd.DataFrame()
                        
                        if df.empty:
                            # Interface 2: Spot fallback
                            df = ak.stock_zh_a_spot_em()
                            df = df[df['代码'] == symbol]
                
                # --- Standardize AkShare Columns ---
                if not df.empty:
                    # Mapping Chinese columns to standard names
                    rename_map = {
                        '日期': 'Date', '开盘': 'Open', '最高': 'High', '最低': 'Low', '收盘': 'Close', '成交量': 'Volume',
                        'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
                    }
                    df = df.rename(columns=rename_map)
                    if 'Date' in df.columns:
                        df['Date'] = pd.to_datetime(df['Date'])
                        df = df.set_index('Date')
                    df = df.sort_index(ascending=True)
                    if 'Close' in df.columns and 'Adj Close' not in df.columns:
                        df['Adj Close'] = df['Close']
                    return df

            else:
                # Futures/Commodities
                if ticker in ["AU0", "AG0", "CU0", "SC0"]:
                    try:
                        df = ak.futures_zh_daily_sina(symbol=ticker)
                        if not df.empty:
                            rename_map = {
                                'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume',
                                '日期': 'Date', '开盘': 'Open', '最高': 'High', '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'
                            }
                            df = df.rename(columns=rename_map)
                            if 'Date' in df.columns:
                                df['Date'] = pd.to_datetime(df['Date'])
                                df = df.set_index('Date')
                            df = df.sort_index(ascending=True)
                            df = df.loc[start_date:end_date]
                            if 'Close' in df.columns and 'Adj Close' not in df.columns:
                                df['Adj Close'] = df['Close']
                            if not df.empty:
                                return df
                    except Exception as e:
                        logger.warning(f"AkShare futures_zh_daily_sina failed for {ticker}: {str(e)}")

                    mapping = {"AU0": "GC=F", "AG0": "SI=F", "CU0": "HG=F", "SC0": "SC=F"}
                    return self.fetch_yfinance_data(mapping[ticker], start_date, end_date)
                df = pd.DataFrame()
                
            if df.empty:
                logger.warning(f"No data returned for {ticker} from akshare")
                return pd.DataFrame()
            return df
        except Exception as e:
            logger.error(f"akshare error for {ticker}: {str(e)}")
            return pd.DataFrame()

    def get_data(self, ticker, start_date=None, end_date=None, source="stooq", force_refresh=False):
        """
        Main entry point for fetching data with caching and fallback.
        """
        current_info = get_current_quarter_info(self.config)
        period = f"{current_info['year']}Q{current_info['quarter']}"
        
        if start_date is None: start_date = current_info['start_date']
        if end_date is None: end_date = current_info['end_date']
        lookback_years = self.config.get("analysis", {}).get("lookback_years", 0)
        required_start = None
        requested_start = start_date
        requested_end = end_date
        try:
            if lookback_years and start_date and end_date:
                end_ts = pd.Timestamp(end_date)
                required_start = end_ts - pd.DateOffset(years=int(lookback_years))
                lookback_start = required_start.strftime("%Y-%m-%d")
                if lookback_start < start_date:
                    start_date = lookback_start
        except Exception:
            pass

        if not force_refresh:
            cached_df = self.cache.get(ticker, period)
            if cached_df is not None and not cached_df.empty:
                if required_start is None:
                    return cached_df

                try:
                    idx = cached_df.index
                    if not isinstance(idx, pd.DatetimeIndex):
                        idx = pd.to_datetime(idx)
                    if idx.tz is not None:
                        idx = idx.tz_convert(None)
                    cached_min = idx.min()
                    if cached_min <= (required_start + pd.Timedelta(days=30)):
                        return cached_df
                    logger.info(f"Cache for {ticker} does not cover lookback window; refetching.")
                except Exception:
                    logger.info(f"Cache coverage check failed for {ticker}; refetching.")

        try:
            df = pd.DataFrame()
            source_used = source
            fallback_used = False
            if source == "yfinance":
                df = self.fetch_yfinance_data(ticker, start_date, end_date)
                if df.empty or len(df) < 5:
                    logger.info(f"yfinance returned insufficient data for {ticker}, trying Stooq fallback")
                    fallback_used = True
                    source_used = "stooq"
                    df = self.fetch_stooq_data(ticker, start_date, end_date)
            elif source == "stooq":
                df = self.fetch_stooq_data(ticker, start_date, end_date)
                if df.empty or len(df) < 5:
                    logger.info(f"Stooq failed for {ticker}, trying yfinance fallback")
                    fallback_used = True
                    source_used = "yfinance"
                    df = self.fetch_yfinance_data(ticker, start_date, end_date)
            elif source == "akshare":
                df = self.fetch_akshare_data(ticker, start_date, end_date)
                source_used = "akshare"
            
            if not df.empty:
                try:
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    if df.index.tz is not None:
                        df.index = df.index.tz_convert(None)
                    df = df.sort_index(ascending=True)
                    df = df.ffill()
                    df.index.name = "Date"
                except Exception:
                    pass

                try:
                    actual_start = str(pd.to_datetime(df.index.min()).date())
                    actual_end = str(pd.to_datetime(df.index.max()).date())
                except Exception:
                    actual_start = None
                    actual_end = None

                meta = {
                    "ticker": ticker,
                    "source_requested": source,
                    "source_used": source_used,
                    "fallback_used": bool(fallback_used),
                    "requested_start": requested_start,
                    "requested_end": requested_end,
                    "lookback_years": lookback_years,
                    "lookback_start": str(required_start.date()) if required_start is not None else None,
                    "actual_start": actual_start,
                    "actual_end": actual_end,
                    "rows": int(len(df)),
                }
                df.attrs["fetch_meta"] = meta

                min_rows = 40
                if lookback_years:
                    min_rows = 200
                self.cache.save(ticker, period, df, meta=meta, min_rows=min_rows)
            return df
        except Exception as e:
            logger.error(f"Failed to get data for {ticker}: {str(e)}")
            return pd.DataFrame()
