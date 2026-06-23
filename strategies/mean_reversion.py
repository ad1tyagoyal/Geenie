"""
Sprint 2: Strategies - Mean Reversion Module
Z-score based mean reversion strategy - "Hello World" of trading logic
"""

from base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using Z-score
    Buys when price is oversold (Z-score < -threshold)
    Sells when price is overbought (Z-score > threshold)
    """
    
    def __init__(self, period=20, threshold=2.0):
        """
        Initialize Mean Reversion strategy
        
        Args:
            period: Period for calculating Z-score
            threshold: Z-score threshold for signals
        """
        super().__init__(name="MeanReversion", parameters={
            "period": period,
            "threshold": threshold
        })
        self.period = period
        self.threshold = threshold
    
    def calculate_signals(self, data):
        """
        Calculate signals based on Z-score
        
        Args:
            data: DataFrame with price data
        
        Returns:
            Series with signals
        """
        pass
    
    def validate(self):
        """
        Validate strategy parameters
        
        Returns:
            Boolean indicating validity
        """
        if self.period < 1:
            return False
        if self.threshold <= 0:
            return False
        return True
