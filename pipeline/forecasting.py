"""
Forecasting monthly spend using Exponential Smoothing or auto_arima (if available).
Falls back gracefully.
"""
from __future__ import annotations
import warnings
import pandas as pd
from typing import Tuple

def _prep_monthly_series(df: pd.DataFrame, value_col: str = "signed_amount") -> pd.Series:
    s = df.set_index("date")[value_col].resample("MS").sum()
    # We forecast spending magnitude (positive numbers). Convert debits to positive spend.
    s = (-s).clip(lower=0)
    return s

def forecast_monthly_spend(df: pd.DataFrame, periods: int = 3) -> Tuple[pd.Series, pd.Series]:
    """
    Returns (history, forecast) as positive monthly spend.
    """
    s = _prep_monthly_series(df)

    # Try pmdarima auto_arima first
    try:
        import pmdarima as pm  # type: ignore
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            model = pm.auto_arima(
                s, seasonal=True, m=12, stepwise=True, suppress_warnings=True, error_action="ignore"
            )
        fc = model.predict(n_periods=periods)
        idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=periods, freq="MS")
        forecast = pd.Series(fc, index=idx)
        return s, forecast
    except Exception:
        pass

    # Fallback: statsmodels ExponentialSmoothing
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            model = ExponentialSmoothing(
                s, trend="add", seasonal="add", seasonal_periods=12, initialization_method="estimated"
            )
            fit = model.fit(optimized=True)
            forecast = fit.forecast(periods)
        return s, pd.Series(forecast, index=pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=periods, freq="MS"))
    except Exception:
        pass

    # Final fallback: naive last value
    last = s.iloc[-1] if len(s) else 0.0
    idx = pd.date_range(pd.Timestamp.today().to_period("M").to_timestamp(), periods=periods, freq="MS")
    forecast = pd.Series([last]*periods, index=idx)
    return s, forecast
