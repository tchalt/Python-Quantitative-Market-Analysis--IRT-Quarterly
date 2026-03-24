import functools
import time
from utils.logger import logger

def fetch_with_retry(retries=3, delay=2, backoff=2):
    """
    Decorator for retrying API calls.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            m_retries = retries
            m_delay = delay
            while m_retries > 0:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    m_retries -= 1
                    if m_retries == 0:
                        logger.error(f"Failed to execute {func.__name__} after {retries} retries: {str(e)}")
                        raise e
                    logger.warning(f"Error in {func.__name__}: {str(e)}. Retrying in {m_delay}s... ({m_retries} left)")
                    time.sleep(m_delay)
                    m_delay *= backoff
            return None
        return wrapper
    return decorator
