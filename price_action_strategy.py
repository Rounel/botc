"""
price_action_strategy.py
Price Action pur :
- Support / Résistance clés
- Breakout avec retest
- Continuation de tendance
- Patterns de bougies (Pin bar, Engulfing, Inside bar)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
import logging

from market_analysis import MarketAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class Level:
    price: float
    level_type: str     # "support" | "resistance"
    touches: int
    strength: float


@dataclass
class CandlePattern:
    name: str
    direction: str
    strength: float


@dataclass
class PASignal:
    valid: bool
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    setup_type: str
    pattern: Optional[CandlePattern]
    confluence: List[str]
    confidence: float
    reason: str = ""


class PriceActionStrategy:
    """Stratégie Price Action pure."""

    def __init__(self):
        self.analyzer = MarketAnalyzer()

    # ──────────────────────────────────────────
    # SUPPORT / RÉSISTANCE
    # ──────────────────────────────────────────

    def find_key_levels(self, df: pd.DataFrame, tolerance_pct: float = 0.001) -> List[Level]:
        """
        Trouve les niveaux S/R par clustering de prix.
        Un niveau fort = plusieurs touches sans cassure définitive.
        """
        highs = df['high'].values
        lows  = df['low'].values

        # Regrouper les prix proches
        all_prices = np.concatenate([highs, lows])
        levels = []
        used = set()

        for i, p in enumerate(all_prices):
            if i in used:
                continue
            cluster = [j for j, q in enumerate(all_prices) if abs(p - q) / p < tolerance_pct]
            for j in cluster:
                used.add(j)
            if len(cluster) >= 3:
                avg = np.mean(all_prices[cluster])
                # Résistance si prix principal est en-dessous, support si au-dessus
                close = df['close'].iloc[-1]
                ltype = "resistance" if avg > close else "support"
                strength = min(1.0, len(cluster) / 10)
                levels.append(Level(price=avg, level_type=ltype, touches=len(cluster), strength=strength))

        return sorted(levels, key=lambda l: -l.strength)[:10]

    # ──────────────────────────────────────────
    # PATTERNS DE BOUGIES
    # ──────────────────────────────────────────

    def detect_candle_pattern(self, df: pd.DataFrame) -> Optional[CandlePattern]:
        """Détecte les patterns de bougies sur les 3 dernières bougies."""
        o  = df['open'].values
        h  = df['high'].values
        l  = df['low'].values
        c  = df['close'].values

        if len(df) < 3:
            return None

        # Index des 3 dernières
        i = len(df) - 1

        body  = abs(c[i] - o[i])
        total = h[i] - l[i] + 1e-10
        upper_wick = h[i] - max(c[i], o[i])
        lower_wick = min(c[i], o[i]) - l[i]

        # Pin bar haussier (long lower wick)
        if lower_wick > body * 2.5 and lower_wick > upper_wick * 2:
            return CandlePattern(name="Pin Bar", direction="buy", strength=0.8)

        # Pin bar baissier (long upper wick)
        if upper_wick > body * 2.5 and upper_wick > lower_wick * 2:
            return CandlePattern(name="Pin Bar", direction="sell", strength=0.8)

        # Engulfing haussier
        if (c[i] > o[i] and c[i-1] < o[i-1] and
                c[i] > o[i-1] and o[i] < c[i-1]):
            return CandlePattern(name="Bullish Engulfing", direction="buy", strength=0.7)

        # Engulfing baissier
        if (c[i] < o[i] and c[i-1] > o[i-1] and
                c[i] < o[i-1] and o[i] > c[i-1]):
            return CandlePattern(name="Bearish Engulfing", direction="sell", strength=0.7)

        # Doji (indécision)
        if body / total < 0.1:
            return CandlePattern(name="Doji", direction="neutral", strength=0.3)

        # Marteau (Hammer)
        if lower_wick > body * 1.5 and c[i] > o[i] and upper_wick < body * 0.5:
            return CandlePattern(name="Hammer", direction="buy", strength=0.65)

        # Étoile filante (Shooting Star)
        if upper_wick > body * 1.5 and c[i] < o[i] and lower_wick < body * 0.5:
            return CandlePattern(name="Shooting Star", direction="sell", strength=0.65)

        # Inside bar
        if h[i] < h[i-1] and l[i] > l[i-1]:
            dir_ = "buy" if c[i-1] > o[i-1] else "sell"
            return CandlePattern(name="Inside Bar", direction=dir_, strength=0.5)

        return None

    # ──────────────────────────────────────────
    # BREAKOUT
    # ──────────────────────────────────────────

    def detect_breakout(self, df: pd.DataFrame, levels: List[Level]) -> Optional[tuple]:
        """
        Détecte un breakout avec retest d'un niveau clé.
        """
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]

        for level in levels:
            # Breakout haussier
            if level.level_type == "resistance":
                if prev_close < level.price and close > level.price:
                    return ("bullish_breakout", level)
                # Retest après breakout
                if close > level.price * 0.999 and abs(close - level.price) / level.price < 0.002:
                    return ("bullish_retest", level)

            # Breakout baissier
            elif level.level_type == "support":
                if prev_close > level.price and close < level.price:
                    return ("bearish_breakout", level)
                if close < level.price * 1.001 and abs(close - level.price) / level.price < 0.002:
                    return ("bearish_retest", level)

        return None

    # ──────────────────────────────────────────
    # SIGNAL PRICE ACTION
    # ──────────────────────────────────────────

    def generate_signal(self, df: pd.DataFrame, pair: str) -> PASignal:
        """Génère un signal Price Action complet."""
        condition = self.analyzer.analyze(df)
        ind = self.analyzer.get_indicators(df)
        close = df['close'].iloc[-1]
        atr = ind.atr

        levels  = self.find_key_levels(df)
        pattern = self.detect_candle_pattern(df)
        bo      = self.detect_breakout(df, levels)

        confluence = []
        direction  = None
        setup_type = ""
        entry = close
        sl = tp = 0.0
        hit_level = None

        # ── Pattern sur niveau clé ──
        if pattern and pattern.direction in ("buy", "sell"):
            # Vérifier si pattern près d'un niveau
            for level in levels:
                if abs(close - level.price) / level.price < 0.003:
                    if (pattern.direction == "buy" and level.level_type == "support") or \
                       (pattern.direction == "sell" and level.level_type == "resistance"):
                        direction  = pattern.direction
                        setup_type = f"PATTERN_{level.level_type.upper()}"
                        hit_level  = level
                        confluence.append(f"{pattern.name} sur {level.level_type} @ {level.price:.5f}")
                        confluence.append(f"Force niveau : {level.touches} touches")
                        break

        # ── Breakout / Retest ──
        if bo and not direction:
            bo_type, level = bo
            if "bullish" in bo_type:
                direction  = "buy"
                setup_type = bo_type.upper()
                hit_level  = level
                confluence.append(f"Breakout haussier @ {level.price:.5f}")
            elif "bearish" in bo_type:
                direction  = "sell"
                setup_type = bo_type.upper()
                hit_level  = level
                confluence.append(f"Breakout baissier @ {level.price:.5f}")

        # ── Continuation de tendance ──
        if not direction and condition.trend in ("bullish", "bearish"):
            if condition.trend == "bullish" and ind.rsi < 60 and ind.above_ema200:
                # Entrée sur pullback vers EMA
                if abs(close - ind.ema_fast) / ind.ema_fast < 0.002:
                    direction  = "buy"
                    setup_type = "TREND_CONTINUATION"
                    confluence.append("Pullback vers EMA50 en trend haussier")

            elif condition.trend == "bearish" and ind.rsi > 40 and not ind.above_ema200:
                if abs(close - ind.ema_fast) / ind.ema_fast < 0.002:
                    direction  = "sell"
                    setup_type = "TREND_CONTINUATION"
                    confluence.append("Pullback vers EMA50 en trend baissier")

        if not direction:
            return PASignal(
                valid=False, direction="", entry=0, stop_loss=0, take_profit=0,
                setup_type="", pattern=pattern, confluence=[], confidence=0,
                reason=f"Pas de setup PA (trend={condition.trend})"
            )

        # ── SL basé sur structure ──
        if direction == "buy":
            swing_lows = self.analyzer.find_swing_lows(df)
            sl_candidates = [l for _, l in swing_lows if l < entry]
            sl = max(sl_candidates) - atr * 0.3 if sl_candidates else entry - atr * 1.5
            tp = entry + abs(entry - sl) * 2.5
        else:
            swing_highs = self.analyzer.find_swing_highs(df)
            sl_candidates = [h for _, h in swing_highs if h > entry]
            sl = min(sl_candidates) + atr * 0.3 if sl_candidates else entry + atr * 1.5
            tp = entry - abs(sl - entry) * 2.5

        # Confluence EMA et RSI
        if direction == "buy" and ind.above_ema200:
            confluence.append("Au-dessus EMA200")
        elif direction == "sell" and not ind.above_ema200:
            confluence.append("En dessous EMA200")

        if pattern:
            confluence.append(f"Pattern : {pattern.name} (force={pattern.strength:.2f})")

        confidence = min(1.0, len(confluence) * 0.22 + (pattern.strength * 0.3 if pattern else 0))

        return PASignal(
            valid=True,
            direction=direction,
            entry=round(entry, 5),
            stop_loss=round(sl, 5),
            take_profit=round(tp, 5),
            setup_type=setup_type,
            pattern=pattern,
            confluence=confluence,
            confidence=round(confidence, 2),
            reason=f"Setup PA : {setup_type}",
        )
