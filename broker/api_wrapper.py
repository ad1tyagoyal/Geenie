"""
Sprint 5: Broker Integration - API Wrapper Module
Connects to Zerodha Kite or Alpaca API
"""


class BrokerAPIWrapper:
    """
    Unified interface for broker APIs (Zerodha Kite, Alpaca, etc.)
    """
    
    def __init__(self, broker_type, api_key, api_secret):
        """
        Initialize broker API connection
        
        Args:
            broker_type: Type of broker ('zerodha', 'alpaca', etc.)
            api_key: API key from broker
            api_secret: API secret from broker
        """
        self.broker_type = broker_type
        self.api_key = api_key
        self.api_secret = api_secret
    
    def connect(self):
        """
        Establish connection to broker API
        
        Returns:
            Boolean indicating successful connection
        """
        pass
    
    def get_quote(self, symbol):
        """
        Get current price quote for symbol
        
        Args:
            symbol: Stock ticker symbol
        
        Returns:
            Dictionary with price data
        """
        pass
    
    def get_account_info(self):
        """
        Get account information and balance
        
        Returns:
            Dictionary with account details
        """
        pass
    
    def get_positions(self):
        """
        Get current open positions
        
        Returns:
            List of position dictionaries
        """
        pass
