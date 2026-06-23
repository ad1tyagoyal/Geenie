"""
Sprint 1: Data Pipeline - Fetchers Module
Scripts to pull yfinance (EOD) or WebSocket data
"""


def fetch_eod_data(symbol, start_date, end_date):
    """
    Fetch end-of-day data from yfinance
    
    Args:
        symbol: Stock ticker symbol
        start_date: Start date for data retrieval
        end_date: End date for data retrieval
    
    Returns:
        DataFrame with OHLCV data
    """
    pass


def fetch_websocket_data(symbol):
    """
    Fetch real-time data via WebSocket
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        Real-time price updates
    """
    pass
