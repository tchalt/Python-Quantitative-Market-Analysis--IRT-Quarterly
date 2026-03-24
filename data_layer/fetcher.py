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
                if ticker in ["AU0", "AG0", "CU0"]:
                    mapping = {"AU0": "GC=F", "AG0": "SI=F", "CU0": "HG=F"}
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

        if not force_refresh:
            cached_df = self.cache.get(ticker, period)
            if cached_df is not None and not cached_df.empty:
                return cached_df

        df = pd.DataFrame()
        try:
            if source in ["stooq", "yfinance"]:
                # Try Stooq first
                df = self.fetch_stooq_data(ticker, start_date, end_date)
                # Fallback to yfinance if Stooq failed or returned too little data
                if df.empty or len(df) < 5:
                    logger.info(f"Stooq failed for {ticker}, trying yfinance fallback")
                    df = self.fetch_yfinance_data(ticker, start_date, end_date)
            elif source == "akshare":
                df = self.fetch_akshare_data(ticker, start_date, end_date)
            
            if not df.empty:
                # Extra validation before saving to cache
                if len(df) > 0:
                    self.cache.save(ticker, period, df)
            return df
        except Exception as e:
            logger.error(f"Failed to get data for {ticker}: {str(e)}")
            return pd.DataFrame()
