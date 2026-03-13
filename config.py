"""
Configuration centrale du bot de trading.
Modifiez ce fichier selon votre configuration.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict

# ─────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "VOTRE_TOKEN_TELEGRAM_ICI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "VOTRE_CHAT_ID_ICI")

# ─────────────────────────────────────────────
# BROKER API
# ─────────────────────────────────────────────
BROKER = os.getenv("BROKER", "demo")  # "demo", "mt5", "binance", "oanda"

# MetaTrader 5
MT5_LOGIN    = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER   = os.getenv("MT5_SERVER", "")

# Binance
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# OANDA
OANDA_API_KEY    = os.getenv("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")

# ─────────────────────────────────────────────
# GESTION DU RISQUE (valeurs par défaut)
# ─────────────────────────────────────────────
DEFAULT_RISK_PERCENT      = 0.5    # Risque par trade en %
MAX_RISK_PERCENT          = 2.0    # Risque maximum autorisé
MIN_RISK_REWARD           = 2.0    # RR minimum
MAX_CONSECUTIVE_LOSSES    = 3      # Arrêt après N pertes consécutives
MAX_DAILY_TRADES          = 5      # Maximum de trades par jour
MAX_DAILY_DRAWDOWN_PCT    = 3.0    # Drawdown journalier max en %
MAX_TOTAL_DRAWDOWN_PCT    = 10.0   # Drawdown total max en %

# ─────────────────────────────────────────────
# PAIRES ET ACTIFS
# ─────────────────────────────────────────────
DEFAULT_PAIRS = ["BTCUSD", "XAUUSD", "EURUSD", "GBPUSD", "XAGUSD"]
ACTIVE_PAIR   = "XAUUSD"

# Paramètres par actif
ASSET_CONFIG: Dict[str, dict] = {
    "BTCUSD":  {"pip_size": 1.0,    "contract_size": 1,      "min_lot": 0.001},
    "XAUUSD":  {"pip_size": 0.01,   "contract_size": 100,    "min_lot": 0.01},
    "XAGUSD":  {"pip_size": 0.001,  "contract_size": 5000,   "min_lot": 0.01},
    "EURUSD":  {"pip_size": 0.0001, "contract_size": 100000, "min_lot": 0.01},
    "GBPUSD":  {"pip_size": 0.0001, "contract_size": 100000, "min_lot": 0.01},
}

# ─────────────────────────────────────────────
# MODES DE TRADING
# ─────────────────────────────────────────────
TRADING_MODES = {
    "scalping":  {"timeframes": ["M1", "M5"],  "max_trades": 8, "min_rr": 1.5},
    "intraday":  {"timeframes": ["M15", "H1"], "max_trades": 4, "min_rr": 2.0},
    "swing":     {"timeframes": ["H4", "D1"],  "max_trades": 2, "min_rr": 3.0},
}
ACTIVE_MODE = "scalping"

# ─────────────────────────────────────────────
# STRATÉGIES
# ─────────────────────────────────────────────
ACTIVE_STRATEGY  = "smc"   # "smc", "ict", "supplydemand", "priceaction"
STRATEGIES_ENABLED = ["smc", "ict", "supplydemand", "priceaction"]

# ─────────────────────────────────────────────
# INDICATEURS
# ─────────────────────────────────────────────
EMA_FAST  = 50
EMA_SLOW  = 200
RSI_PERIOD = 14
RSI_OB    = 70
RSI_OS    = 30
ATR_PERIOD = 14

# ─────────────────────────────────────────────
# NEWS FILTER
# ─────────────────────────────────────────────
NEWS_FILTER_ENABLED = True
NEWS_PAUSE_MINUTES  = 30      # Pause avant/après annonce
NEWS_API_KEY        = os.getenv("NEWS_API_KEY", "")  # ForexFactory ou Twelve Data

# ─────────────────────────────────────────────
# BACKTESTING
# ─────────────────────────────────────────────
BACKTEST_START = "2024-01-01"
BACKTEST_END   = "2024-12-31"
INITIAL_BALANCE = 1000.0

# ─────────────────────────────────────────────
# LOGS
# ─────────────────────────────────────────────
LOG_FILE   = "trades_journal.csv"
LOG_LEVEL  = "INFO"
STATS_FILE = "performance_stats.json"
