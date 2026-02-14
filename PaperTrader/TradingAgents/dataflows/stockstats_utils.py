import pandas as pd
import yfinance as yf
from stockstats import wrap
from typing import Annotated
import os
from .config import get_config, DATA_DIR


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
    ):
        # Get config and set up data directory path
        config = get_config()
        online = config["data_vendors"]["technical_indicators"] != "local"

        df = None
        data = None

        if not online:
            try:
                data = pd.read_csv(
                    os.path.join(
                        DATA_DIR,
                        f"{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
                    )
                )
                df = wrap(data)
            except FileNotFoundError:
                raise Exception("Stockstats fail: Yahoo Finance data not fetched yet!")
        else:
            # Get today's date as YYYY-mm-dd to add to cache
            today_date = pd.Timestamp.today()
            curr_date = pd.to_datetime(curr_date)

            end_date = today_date
            start_date = today_date - pd.DateOffset(years=15)
            start_date = start_date.strftime("%Y-%m-%d")
            end_date = end_date.strftime("%Y-%m-%d")

            # Get config and ensure cache directory exists
            os.makedirs(config["data_cache_dir"], exist_ok=True)

            data_file = os.path.join(
                config["data_cache_dir"],
                f"{symbol}-YFin-data-{start_date}-{end_date}.csv",
            )

            if os.path.exists(data_file):
                data = pd.read_csv(data_file)
                data["Date"] = pd.to_datetime(data["Date"])
            else:
                data = yf.download(
                    symbol,
                    start=start_date,
                    end=end_date,
                    multi_level_index=False,
                    progress=False,
                    auto_adjust=True,
                )
                data = data.reset_index()
                data.to_csv(data_file, index=False)

            data = data.set_index("Date")
            df = wrap(data)
            # Ensure curr_date matching works with DatetimeIndex
            curr_date_dt = pd.to_datetime(curr_date) # Ensure timestamp matching

        df[indicator]  # trigger calculation
        
        # Try to find the date in the index
        found = False
        val = None
        
        # Check against index directly if it matches string
        if curr_date in df.index:
             val = df.loc[curr_date][indicator]
             found = True
        else:
             # Try matching against datetime index
             try:
                 if curr_date_dt in df.index:
                     val = df.loc[curr_date_dt][indicator]
                     found = True
             except:
                 pass
                 
        if not found:
             # Fallback: check closest date or string column if index is not date
             # (Legacy logic relied on Date column, but wrap() usually makes it index)
             try:
                  # If index is datetime, we can format it to match
                  if isinstance(df.index, pd.DatetimeIndex):
                       # Find matching index
                       matches = df.index[df.index.strftime("%Y-%m-%d") == curr_date]
                       if not matches.empty:
                            val = df.loc[matches[0]][indicator]
                            found = True
             except:
                  pass

        if found:
            # If val is Series (duplicates), take first
            if isinstance(val, pd.Series):
                 val = val.iloc[0]
            return val
        else:
            return "N/A: Not a trading day (weekend or holiday)"
