from datetime import datetime, date
import pandas as pd

def get_quarter_dates(year=None, quarter=None):
    """
    Returns the start and end dates for a given year and quarter.
    If year and quarter are not provided, returns dates for the current quarter.
    """
    now = datetime.now()
    if year is None:
        year = now.year
    if quarter is None:
        quarter = (now.month - 1) // 3 + 1

    # Quarterly mappings
    quarter_map = {
        1: ("01-01", "03-31"),
        2: ("04-01", "06-30"),
        3: ("07-01", "09-30"),
        4: ("10-01", "12-31")
    }

    start_str, end_str = quarter_map[quarter]
    start_date = f"{year}-{start_str}"
    end_date = f"{year}-{end_str}"

    return start_date, end_date

def get_previous_quarter(year=None, quarter=None):
    """
    Returns the (year, quarter) for the previous quarter.
    """
    now = datetime.now()
    if year is None:
        year = now.year
    if quarter is None:
        quarter = (now.month - 1) // 3 + 1

    if quarter == 1:
        return year - 1, 4
    else:
        return year, quarter - 1

def get_current_quarter_info(config=None):
    """
    Returns year, quarter, start_date, and end_date.
    If config is provided, prioritizes dates from config.
    """
    if config and 'analysis' in config:
        analysis_config = config['analysis']
        if 'start_date' in analysis_config and 'end_date' in analysis_config:
            # Parse period from start_date if possible
            start_dt = datetime.strptime(analysis_config['start_date'], "%Y-%m-%d")
            year = start_dt.year
            quarter = (start_dt.month - 1) // 3 + 1
            return {
                "year": year,
                "quarter": quarter,
                "start_date": analysis_config['start_date'],
                "end_date": analysis_config['end_date'],
                "period_label": analysis_config.get('period_label', f"{year} Q{quarter} Analysis")
            }

    now = datetime.now()
    year = now.year
    quarter = (now.month - 1) // 3 + 1
    start_date, end_date = get_quarter_dates(year, quarter)
    return {
        "year": year,
        "quarter": quarter,
        "start_date": start_date,
        "end_date": end_date,
        "period_label": f"{year} Q{quarter} Analysis"
    }

def format_date_to_str(dt, fmt="%Y-%m-%d"):
    """Formats a datetime or date object to string."""
    if isinstance(dt, (datetime, date)):
        return dt.strftime(fmt)
    return str(dt)
