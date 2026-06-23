"""
Sprint 2: Strategies - Base Strategy Module
Parent class defining standard inputs/outputs
"""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies
    Defines standard inputs/outputs interface
    """
    
    def __init__(self, name, parameters=None):
        """
        Initialize strategy
        
        Args:
            name: Strategy name
            parameters: Dictionary of strategy parameters
        """
        self.name = name
        self.parameters = parameters or {}
    
    @abstractmethod
    def calculate_signals(self, data):
        """
        Calculate trading signals
        
        Args:
            data: DataFrame with OHLCV data
        
        Returns:
            Series with signals (1=buy, -1=sell, 0=hold)
        """
        pass
    
    @abstractmethod
    def validate(self):
        """
        Validate strategy parameters and logic
        
        Returns:
            Boolean indicating if strategy is valid
        """
        pass
