import numpy as np
import pandas as pd
from scipy import stats
from utils.logger import logger

class QuantCalculator:
    """
    Core mathematical engine for risk metrics and financial statement analysis.
    """

    @staticmethod
    def calculate_hurst(price_series, max_lag=100):
        """
        Estimates the Hurst exponent H using a log-log regression on the standard deviation
        of lagged log-price differences.

        Interpretation:
        - H < 0.5: mean-reverting behavior
        - H ~ 0.5: random walk
        - H > 0.5: trending/persistent behavior
        """
        try:
            if price_series is None:
                return np.nan

            s = pd.Series(price_series).dropna()
            if len(s) < 100:
                return np.nan

            s = s.astype(float)
            s = s[s > 0]
            if len(s) < 100:
                return np.nan

            logp = np.log(s.values)
            max_lag = int(min(max_lag, len(logp) // 2))
            if max_lag < 10:
                return np.nan

            lags = np.arange(2, max_lag + 1)
            taus = []
            for lag in lags:
                diff = logp[lag:] - logp[:-lag]
                tau = np.std(diff)
                if np.isfinite(tau) and tau > 0:
                    taus.append(tau)
                else:
                    taus.append(np.nan)

            taus = np.array(taus, dtype=float)
            valid = np.isfinite(taus) & (taus > 0)
            if valid.sum() < 10:
                return np.nan

            x = np.log(lags[valid])
            y = np.log(taus[valid])
            slope, _ = np.polyfit(x, y, 1)
            return float(slope)
        except Exception as e:
            logger.warning(f"Failed to calculate Hurst exponent: {str(e)}")
            return np.nan

    @staticmethod
    def calculate_risk_metrics(asset_returns, benchmark_returns, rf_rate, annualization_factor=252):
        """
        Calculates Sharpe Ratio, Beta, and Jensen's Alpha.
        
        Formula:
        - Sharpe Ratio = (R_p - R_f) / sigma_p
        - Beta = Cov(R_p, R_m) / Var(R_m)
        - Alpha = R_p - [R_f + Beta * (R_m - R_f)]
        """
        # Align returns by dropping NaNs present in either series
        aligned_data = pd.concat([asset_returns, benchmark_returns], axis=1).dropna()
        if aligned_data.empty:
            logger.warning("No overlapping data for risk calculation.")
            return {"sharpe": np.nan, "beta": np.nan, "alpha": np.nan, "volatility": np.nan, "n_obs": 0}

        r_p = aligned_data.iloc[:, 0]
        r_m = aligned_data.iloc[:, 1]
        
        # 1. Volatility (Annualized)
        vol = r_p.std() * np.sqrt(annualization_factor)
        
        # 2. Sharpe Ratio (Annualized)
        # R_f is typically provided as an annual rate, so we convert it to match period returns
        rf_period = rf_rate / annualization_factor
        excess_return = r_p - rf_period
        sharpe = (excess_return.mean() / r_p.std()) * np.sqrt(annualization_factor) if r_p.std() != 0 else np.nan

        # 3. Beta (OLS Regression)
        # Beta = Cov(r_p, r_m) / Var(r_m)
        slope, intercept, r_value, p_value, std_err = stats.linregress(r_m, r_p)
        beta = slope

        # 4. Alpha (Jensen's Alpha - Annualized)
        # Alpha_annual = (R_p_annual - R_f_annual) - Beta * (R_m_annual - R_f_annual)
        r_p_annual = r_p.mean() * annualization_factor
        r_m_annual = r_m.mean() * annualization_factor
        alpha = (r_p_annual - rf_rate) - beta * (r_m_annual - rf_rate)

        return {
            "sharpe": round(sharpe, 4),
            "beta": round(beta, 4),
            "alpha": round(alpha, 4),
            "volatility": round(vol, 4),
            "n_obs": int(len(aligned_data))
        }

    @staticmethod
    def analyze_financials(statement_data):
        """
        Analyzes financial statement items and detects report types.
        Expects a DataFrame with columns: [ticker, period, net_income, total_assets, total_liabilities, fcf]
        """
        if statement_data.empty:
            return {"report_type": "Unknown", "metrics": {}, "anomalies": []}

        # Sort by period to ensure growth calculation is correct
        statement_data = statement_data.sort_values("period")
        latest = statement_data.iloc[-1]
        previous = statement_data.iloc[-2] if len(statement_data) > 1 else None

        # 1. Report Type Detection (Annual vs Quarterly)
        # Annual reports usually end on 12-31 and have specific naming
        period_str = str(latest['period'])
        is_annual = period_str.endswith("12-31") or "FY" in period_str or "Q4" in period_str
        report_type = "Annual (FY)" if is_annual else "Quarterly"

        # 2. Key Metrics
        net_income = latest.get('net_income', 0)
        assets = latest.get('total_assets', 1)
        liabilities = latest.get('total_liabilities', 0)
        fcf = latest.get('fcf', 0)

        metrics = {
            "net_income": net_income,
            "debt_to_equity": round(liabilities / (assets - liabilities), 4) if (assets - liabilities) != 0 else np.nan,
            "fcf": fcf
        }

        # 3. Growth and Anomaly Detection
        anomalies = []
        if previous is not None:
            # Net Income Growth
            prev_ni = previous.get('net_income', 0)
            if prev_ni != 0:
                growth = (net_income - prev_ni) / abs(prev_ni)
                metrics["net_income_growth"] = round(growth, 4)
                if abs(growth) > 0.20:
                    anomalies.append(f"Significant Net Income change: {growth:+.2%}")
            
            # FCF Change
            prev_fcf = previous.get('fcf', 0)
            if prev_fcf != 0:
                fcf_change = (fcf - prev_fcf) / abs(prev_fcf)
                if abs(fcf_change) > 0.20:
                    anomalies.append(f"Significant FCF change: {fcf_change:+.2%}")

        return {
            "report_type": report_type,
            "metrics": metrics,
            "anomalies": anomalies,
            "period": period_str
        }
