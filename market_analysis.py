"""
market_analysis.py
Analyse des conditions de marché : tendance, range, volatilité, momentum.
Calcul des indicateurs techniques (EMA, RSI, ATR, Volume).
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, Tuple
import logging

import config

logger = logging.getLogger(__name__)


@dataclass
class MarketCondition:
    trend: str          # "bullish" | "bearish" | "neutral"
    structure: str      # "trending" | "ranging" | "volatile"
    momentum: str       # "strong" | "weak" | "neutral"
    volatility: float   # ATR value
    regime: str         # "trending" | "ranging"
    bias: str           # "long" | "short" | "none"


@dataclass
class Indicators:
    ema_fast: float
    ema_slow: float
    rsi: float
    atr: float
    volume_avg: float
    current_volume: float
    higher_highs: bool
    lower_lows: bool
    above_ema200: bool


class MarketAnalyzer:
    """Analyse complète du marché pour guider les stratégies."""

    def __init__(self):
        self.ema_fast  = config.EMA_FAST
        self.ema_slow  = config.EMA_SLOW
        self.rsi_period = config.RSI_PERIOD
        self.atr_period = config.ATR_PERIOD

    # ──────────────────────────────────────────
    # INDICATEURS
    # ──────────────────────────────────────────

    def calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    def calculate_rsi(self, series: pd.Series) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=self.rsi_period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=self.rsi_period - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        high, low, close = df['high'], df['low'], df['close']
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(span=self.atr_period, adjust=False).mean()

    def get_indicators(self, df: pd.DataFrame) -> Indicators:
        """Calcule tous les indicateurs sur un DataFrame OHLCV."""
        close = df['close']
        ema_fast = self.calculate_ema(close, self.ema_fast).iloc[-1]
        ema_slow = self.calculate_ema(close, self.ema_slow).iloc[-1]
        rsi      = self.calculate_rsi(close).iloc[-1]
        atr      = self.calculate_atr(df).iloc[-1]

        vol = df['volume'] if 'volume' in df.columns else pd.Series([1]*len(df))
        vol_avg = vol.rolling(20).mean().iloc[-1]
        cur_vol = vol.iloc[-1]

        # Structure
        highs = df['high'].values
        lows  = df['low'].values
        hh = highs[-1] > highs[-2] > highs[-3]
        ll = lows[-1] < lows[-2] < lows[-3]

        return Indicators(
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            atr=atr,
            volume_avg=vol_avg,
            current_volume=cur_vol,
            higher_highs=hh,
            lower_lows=ll,
            above_ema200=close.iloc[-1] > ema_slow,
        )

    # ──────────────────────────────────────────
    # CONDITION DE MARCHÉ
    # ──────────────────────────────────────────

    def analyze(self, df: pd.DataFrame) -> MarketCondition:
        """Analyse globale : tendance, range, volatilité, momentum, biais."""
        ind = self.get_indicators(df)
        close = df['close'].iloc[-1]

        # Tendance
        if ind.ema_fast > ind.ema_slow and ind.higher_highs:
            trend = "bullish"
        elif ind.ema_fast < ind.ema_slow and ind.lower_lows:
            trend = "bearish"
        else:
            trend = "neutral"

        # Structure
        atr_pct = ind.atr / close * 100
        if atr_pct > 0.8:
            structure = "volatile"
        elif abs(ind.ema_fast - ind.ema_slow) / ind.ema_slow * 100 < 0.1:
            structure = "ranging"
        else:
            structure = "trending"

        # Momentum RSI
        if ind.rsi > 60:
            momentum = "strong" if trend == "bullish" else "weak"
        elif ind.rsi < 40:
            momentum = "strong" if trend == "bearish" else "weak"
        else:
            momentum = "neutral"

        # Biais directionnel
        if trend == "bullish" and ind.rsi < config.RSI_OB:
            bias = "long"
        elif trend == "bearish" and ind.rsi > config.RSI_OS:
            bias = "short"
        else:
            bias = "none"

        regime = "ranging" if structure == "ranging" else "trending"

        return MarketCondition(
            trend=trend,
            structure=structure,
            momentum=momentum,
            volatility=ind.atr,
            regime=regime,
            bias=bias,
        )

    # ──────────────────────────────────────────
    # SWING HIGH / LOW (structure price action)
    # ──────────────────────────────────────────

    def find_swing_highs(self, df: pd.DataFrame, lookback: int = 5) -> list:
        highs = df['high'].values
        swing_highs = []
        for i in range(lookback, len(highs) - lookback):
            if all(highs[i] > highs[i-j] for j in range(1, lookback+1)) and \
               all(highs[i] > highs[i+j] for j in range(1, lookback+1)):
                swing_highs.append((i, highs[i]))
        return swing_highs

    def find_swing_lows(self, df: pd.DataFrame, lookback: int = 5) -> list:
        lows = df['low'].values
        swing_lows = []
        for i in range(lookback, len(lows) - lookback):
            if all(lows[i] < lows[i-j] for j in range(1, lookback+1)) and \
               all(lows[i] < lows[i+j] for j in range(1, lookback+1)):
                swing_lows.append((i, lows[i]))
        return swing_lows

    def detect_bos_choch(self, df: pd.DataFrame) -> Tuple[Optional[str], Optional[float]]:
        """
        Détecte Break of Structure (BOS) ou Change of Character (CHOCH).
        Retourne (type, niveau) ou (None, None).
        """
        swing_highs = self.find_swing_highs(df)
        swing_lows  = self.find_swing_lows(df)
        close = df['close'].values

        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            last_high = swing_highs[-1][1]
            prev_high = swing_highs[-2][1]
            last_low  = swing_lows[-1][1]
            prev_low  = swing_lows[-2][1]
            cur = close[-1]

            # BOS haussier
            if cur > last_high > prev_high:
                return ("BOS_BULLISH", last_high)
            # BOS baissier
            if cur < last_low < prev_low:
                return ("BOS_BEARISH", last_low)
            # CHOCH haussier (inversion)
            if last_low > prev_low and cur > last_high:
                return ("CHOCH_BULLISH", last_high)
            # CHOCH baissier
            if last_high < prev_high and cur < last_low:
                return ("CHOCH_BEARISH", last_low)

        return (None, None)
