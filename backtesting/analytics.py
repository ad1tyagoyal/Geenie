"""
Sprint 3: Backtesting - Analytics Module
Calculates Sharpe ratio, Sortino ratio, and Maximum Drawdown
"""


class PerformanceAnalytics:
    """
    Calculate performance metrics for strategy evaluation
    """
    
    def __init__(self, returns, risk_free_rate=0.02):
        """
        Initialize analytics
        
        Args:
            returns: Series of strategy returns
            risk_free_rate: Annual risk-free rate
        """
        self.returns = returns
        self.risk_free_rate = risk_free_rate
    
    def calculate_sharpe_ratio(self):
        """
        Calculate Sharpe ratio
        
        Returns:
            Sharpe ratio (annualized)
        """
        pass
    
    def calculate_sortino_ratio(self):
        """
        Calculate Sortino ratio (downside deviation focus)
        
        Returns:
            Sortino ratio (annualized)
        """
        pass
    
    def calculate_max_drawdown(self):
        """
        Calculate Maximum Drawdown
        
        Returns:
            Maximum drawdown percentage
        """
        pass
    
    def get_all_metrics(self):
        """
        Get all performance metrics
        
        Returns:
            Dictionary with all metrics
        """
        pass
