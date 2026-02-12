import json
import logging
import yfinance as yf
from .alpha_vantage_common import _make_api_request


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """
    Retrieve comprehensive fundamental data for a given ticker symbol using Alpha Vantage.
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd. 
                         If provided, live ratios (P/E, Market Cap) are replaced with 
                         historically accurate calculations to prevent look-ahead bias.
    Returns:
        str: Company overview data including financial ratios and key metrics
    """
    params = {
        "symbol": ticker,
    }

    # First get the live OVERVIEW data
    data_str = _make_api_request("OVERVIEW", params)
    
    # If a simulation date is provided, isolation logic kicks in
    if curr_date:
        try:
            data = json.loads(data_str)
            if "Symbol" in data:
                # Reconstruct historical ratios to prevent look-ahead bias
                h_ratios = _calculate_historical_ratios(ticker, curr_date)
                if h_ratios:
                    logging.info(f"Overriding live fundamentals for {ticker} with historical math at {curr_date}")
                    data.update(h_ratios)
                    return json.dumps(data, indent=2)
        except Exception as e:
            logging.error(f"Error overriding historical fundamentals for {ticker}: {e}")
            
    return data_str

def _calculate_historical_ratios(ticker: str, end_date: str) -> dict:
    """
    Calculate simulation-accurate Market Cap, P/E, and EPS for a given date.
    Reconstructs metrics from historical price (yfinance) and historical statements.
    """
    try:
        # 1. Get Price at simulation date
        ticker_obj = yf.Ticker(ticker.upper())
        # We look back 5 days to handle weekends/holidays
        price_hist = ticker_obj.history(end=end_date, period="5d")
        if price_hist.empty:
            return None
            
        current_price = float(price_hist['Close'].iloc[-1])
        
        # 2. Get Historical Statements (already filtered to end_date by our internal tools)
        is_data = json.loads(get_income_statement(ticker, curr_date=end_date))
        bs_data = json.loads(get_balance_sheet(ticker, curr_date=end_date))
        
        # 3. Calculate Shares Outstanding from most recent Balance Sheet
        bs_reports = bs_data.get("quarterlyReports", [])
        if not bs_reports:
            return None
        shares = float(bs_reports[0].get("commonStockSharesOutstanding", 0))
        if shares <= 0:
            return None

        # 4. Calculate TTM Net Income (Sum of last 4 quarters)
        is_reports = is_data.get("quarterlyReports", [])
        if len(is_reports) < 4:
            # Fallback to annual if quarterly is sparse
            is_reports_annual = is_data.get("annualReports", [])
            ttm_net_income = float(is_reports_annual[0].get("netIncome", 0)) if is_reports_annual else 0.0
        else:
            ttm_net_income = sum(float(r.get("netIncome", 0)) for r in is_reports[:4])
            
        # 5. Compute Final Ratios
        mkt_cap = current_price * shares
        eps = ttm_net_income / shares if shares > 0 else 0.0
        pe_ratio = current_price / eps if eps > 0 else 0.0
        
        return {
            "MarketCapitalization": str(int(mkt_cap)),
            "PERatio": f"{pe_ratio:.2f}" if pe_ratio > 0 else "N/A",
            "EPS": f"{eps:.2f}",
            "AnalystTargetPrice": "N/A",  # Live targets are look-ahead bias
            "Note": f"Ratios reconstructed for {end_date} to prevent simulation bias."
        }
    except Exception as e:
        logging.error(f"Failed historical ratio math for {ticker}: {e}")
        return None


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """
    Retrieve balance sheet data for a given ticker symbol using Alpha Vantage.

    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly) - not used for Alpha Vantage
        curr_date (str): Current date you are trading at, yyyy-mm-dd (not used for Alpha Vantage)

    Returns:
        str: Balance sheet data with normalized fields
    """
    params = {
        "symbol": ticker,
    }

    data_str = _make_api_request("BALANCE_SHEET", params)
    
    if not curr_date:
        return data_str
        
    try:
        data = json.loads(data_str)
        filtered_data = _filter_reports_by_date(data, curr_date)
        return json.dumps(filtered_data, indent=2)
    except json.JSONDecodeError:
        return data_str


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """
    Retrieve cash flow statement data for a given ticker symbol using Alpha Vantage.

    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly) - not used for Alpha Vantage
        curr_date (str): Current date you are trading at, yyyy-mm-dd (not used for Alpha Vantage)

    Returns:
        str: Cash flow statement data with normalized fields
    """
    params = {
        "symbol": ticker,
    }

    data_str = _make_api_request("CASH_FLOW", params)

    if not curr_date:
        return data_str

    try:
        data = json.loads(data_str)
        filtered_data = _filter_reports_by_date(data, curr_date)
        return json.dumps(filtered_data, indent=2)
    except json.JSONDecodeError:
        return data_str


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """
    Retrieve income statement data for a given ticker symbol using Alpha Vantage.

    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly) - not used for Alpha Vantage
        curr_date (str): Current date you are trading at, yyyy-mm-dd (not used for Alpha Vantage)

    Returns:
        str: Income statement data with normalized fields
    """
    params = {
        "symbol": ticker,
    }

    data_str = _make_api_request("INCOME_STATEMENT", params)

    if not curr_date:
        return data_str

    try:
        data = json.loads(data_str)
        filtered_data = _filter_reports_by_date(data, curr_date)
        return json.dumps(filtered_data, indent=2)
    except json.JSONDecodeError:
        return data_str
        
def _filter_reports_by_date(data: dict, end_date: str) -> dict:
    """Filter quarterly and annual reports to strictly exclude future data."""
    if not end_date:
        return data

    filtered_data = data.copy()
    
    for report_type in ["annualReports", "quarterlyReports"]:
        if report_type in data:
            filtered_reports = []
            for report in data[report_type]:
                fiscal_date = report.get("fiscalDateEnding")
                if fiscal_date and fiscal_date <= end_date:
                    filtered_reports.append(report)
            filtered_data[report_type] = filtered_reports
            
    return filtered_data

