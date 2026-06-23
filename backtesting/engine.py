"""
Sprint 3: Backtesting - Engine Module
Wrappers for vectorbt or backtrader for strategy validation
"""


class BacktestEngine:
    """
    Backtesting engine for validating trading strategies
    """
    
    def __init__(self, strategy, data, initial_capital=100000):
        """
        Initialize backtesting engine
        
        Args:
            strategy: Strategy instance to backtest
            data: Historical OHLCV data
            initial_capital: Starting capital for backtest
        """
        self.strategy = strategy
        self.data = data
        self.initial_capital = initial_capital
    
    def run(self):
        """
        Run the backtest
        
        Returns:
            Dictionary with backtest results
        """
        pass
    
    def get_results(self):
        """
        Get backtest results and metrics
        
        Returns:
            Dictionary with performance metrics
        """
        pass
