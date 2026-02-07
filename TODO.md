Future Perspective

Geenie/
│
├── data/
│   ├── raw/                # Raw market data (API dumps, csv)
│   ├── processed/          # Cleaned, adjusted, resampled data
│   └── features/           # Engineered features (returns, ATR, etc.)
│
├── strategies/
│   ├── base.py             # Abstract Strategy interface
│   ├── breakout.py         # Breakout / momentum strategy
│   └── mean_reversion.py   # (Optional, later)
│
├── backtesting/
│   ├── engine.py           # Backtest loop
│   ├── execution.py        # Slippage & fee models
│   ├── risk.py             # Position sizing, drawdown limits
│   └── metrics.py          # Sharpe, CAGR, max DD
│
├── research/
│   ├── notebooks/          # Experiments & hypothesis testing
│   └── experiments.yaml    # Strategy parameters & runs
│
├── portfolio/
│   ├── allocation.py       # Capital allocation across strategies
│   └── correlation.py      # Correlation & diversification checks
│
├── paper_trading/
│   ├── broker_adapter.py   # Zerodha / IB / CCXT adapter
│   └── runner.py           # Live paper-trade loop
│
├── live_trading/
│   ├── order_manager.py    # Order lifecycle
│   ├── risk_guard.py       # Kill switch, limits
│   └── live_runner.py      # Production entry point
│
├── infra/
│   ├── ingestion.py        # Market data ingestion
│   ├── storage.py          # S3 / local FS abstraction
│   └── scheduler.py        # Cron / event-driven jobs
│
├── configs/
│   ├── markets.yaml        # Symbols, exchanges
│   ├── risk.yaml           # Risk limits
│   └── strategy.yaml       # Parameters
│
├── tests/
│   ├── test_backtest.py
│   ├── test_execution.py
│   └── test_strategies.py
│
├── reports/
│   ├── equity_curves/
│   └── performance_tables/
│
├── README.md               # Strategy logic & assumptions
└── requirements.txt




Geenie-v1/
│
├── data/
│   ├── raw/              # Downloaded OHLCV data
│   └── processed/        # Cleaned & resampled data
│
├── strategy/
│   └── breakout.py       # ONE strategy, ONE file
│
├── backtest/
│   ├── engine.py         # Loop + PnL calculation
│   ├── execution.py     # Fees + slippage
│   └── metrics.py       # Sharpe, CAGR, Max DD
│
├── research/
│   └── notebook.ipynb   # Hypothesis + plots
│
├── config.yaml           # Params, fees, timeframe
└── README.md
