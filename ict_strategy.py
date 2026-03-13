"""
ict_strategy.py
ICT (Inner Circle Trader) Concepts :
- OTE (Optimal Trade Entry) : zone Fibonacci 0.62-0.79
- Liquidity pools (BSL/SSL)
- Market manipulation zones (Judas Swing)
- Kill zones (sessions London/NY)
- Breaker blocks
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime, time
import logging

from market_analysis import MarketAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ICTSignal:
    valid: bool
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    setup_type: str     # "OTE" | "LIQUIDITY_POOL" | "JUDAS_SWING"
    confluence: List[str]
    confidence: float
    reason: str = ""


class ICTStrategy:
    """Stratégie basée sur les concepts ICT."""

    KILL_ZONES = {
        "london_open":  (time(7, 0),  time(10, 0)),
        "new_york_open": (time(13, 0), time(16, 0)),
        "london_close": (time(15, 0), time(17, 0)),
        "asian_range":  (time(0, 0),  time(3, 0)),
    }

    def __init__(self):
        self.analyzer = MarketAnalyzer()

    # ──────────────────────────────────────────
    # KILL ZONES
    # ──────────────────────────────────────────

    def is_kill_zone(self, dt: Optional[datetime] = None) -> Optional[str]:
        """Vérifie si on est dans une kill zone ICT (heure UTC)."""
        dt = dt or datetime.utcnow()
        t = dt.time()
        for name, (start, end) in self.KILL_ZONES.items():
            if start <= t <= end:
                return name
        return None

    # ──────────────────────────────────────────
    # OTE (Optimal Trade Entry)
    # ──────────────────────────────────────────

    def find_ote_zone(
        self, swing_high: float, swing_low: float, direction: str
    ) -> Tuple[float, float]:
        """
        Zone OTE = retracement Fibonacci 0.62 à 0.79.
        Direction buy : retracement depuis swing high vers swing low.
        Direction sell : retracement depuis swing low vers swing high.
        """
        rng = swing_high - swing_low
        if direction == "buy":
            ote_high = swing_high - rng * 0.62
            ote_low  = swing_high - rng * 0.79
        else:
            ote_low  = swing_low + rng * 0.62
            ote_high = swing_low + rng * 0.79
        return ote_low, ote_high

    # ──────────────────────────────────────────
    # LIQUIDITY POOLS
    # ──────────────────────────────────────────

    def find_liquidity_pools(self, df: pd.DataFrame) -> dict:
        """
        Buy-side liquidity (BSL) = swing highs avec clusters de stops.
        Sell-side liquidity (SSL) = swing lows avec clusters de stops.
        """
        swing_highs = self.analyzer.find_swing_highs(df)
        swing_lows  = self.analyzer.find_swing_lows(df)

        bsl = [h for _, h in swing_highs[-5:]] if swing_highs else []
        ssl = [l for _, l in swing_lows[-5:]]  if swing_lows  else []

        return {"BSL": bsl, "SSL": ssl}

    # ──────────────────────────────────────────
    # JUDAS SWING (faux mouvement avant reversal)
    # ──────────────────────────────────────────

    def detect_judas_swing(self, df: pd.DataFrame) -> Optional[str]:
        """
        Judas Swing = faux breakout pendant la session asiatique ou early Londres.
        Identifié quand le prix dépasse un niveau clé et revient rapidement.
        """
        close = df['close'].iloc[-1]
        high  = df['high'].iloc[-1]
        low   = df['low'].iloc[-1]
        prev_close = df['close'].iloc[-2]

        # Mouvement fort suivi d'un retournement
        body = abs(close - prev_close)
        upper_wick = high - max(close, prev_close)
        lower_wick = min(close, prev_close) - low

        if upper_wick > body * 2 and close < prev_close:
            return "bearish_judas"
        if lower_wick > body * 2 and close > prev_close:
            return "bullish_judas"
        return None

    # ──────────────────────────────────────────
    # BREAKER BLOCKS
    # ──────────────────────────────────────────

    def find_breaker_blocks(self, df: pd.DataFrame) -> List[dict]:
        """
        Breaker Block = Order block qui a été cassé et devient support/résistance.
        """
        obs = []
        closes = df['close'].values
        highs  = df['high'].values
        lows   = df['low'].values

        for i in range(5, len(df) - 5):
            # OB bullish cassé = Breaker baissier
            if closes[i] < opens_ if (opens_ := df['open'].values)[i] else True:
                # Chercher si ce niveau a été cassé ensuite
                ob_low = lows[i]
                broken = any(closes[j] < ob_low for j in range(i+1, min(i+10, len(df))))
                if broken:
                    obs.append({"type": "bearish_breaker", "high": highs[i], "low": lows[i], "index": i})

        return obs[-5:]

    # ──────────────────────────────────────────
    # SIGNAL ICT
    # ──────────────────────────────────────────

    def generate_signal(self, df: pd.DataFrame, pair: str) -> ICTSignal:
        """Génère un signal ICT complet."""
        condition = self.analyzer.analyze(df)
        ind = self.analyzer.get_indicators(df)
        close = df['close'].iloc[-1]
        atr = ind.atr

        confluence = []
        direction  = None
        setup_type = ""
        entry      = close

        # Kill zone check
        kz = self.is_kill_zone()
        if kz:
            confluence.append(f"Kill Zone : {kz}")
        else:
            # ICT fonctionne mieux dans les kill zones
            pass

        # Liquidity pools
        pools = self.find_liquidity_pools(df)
        swing_highs = self.analyzer.find_swing_highs(df)
        swing_lows  = self.analyzer.find_swing_lows(df)

        if not swing_highs or not swing_lows:
            return ICTSignal(
                valid=False, direction="", entry=0, stop_loss=0, take_profit=0,
                setup_type="", confluence=[], confidence=0,
                reason="Pas assez de données de structure"
            )

        last_sh = swing_highs[-1][1]
        last_sl = swing_lows[-1][1]
        prev_sh = swing_highs[-2][1] if len(swing_highs) > 1 else last_sh
        prev_sl = swing_lows[-2][1]  if len(swing_lows)  > 1 else last_sl

        # ── OTE Setup Bullish ──
        if condition.trend == "bullish" and close < last_sh:
            ote_low, ote_high = self.find_ote_zone(last_sh, last_sl, "buy")
            if ote_low <= close <= ote_high:
                direction  = "buy"
                setup_type = "OTE"
                confluence.append(f"OTE zone ({ote_low:.5f} - {ote_high:.5f})")
                confluence.append(f"Trend haussier confirmé")

        # ── OTE Setup Bearish ──
        elif condition.trend == "bearish" and close > last_sl:
            ote_low, ote_high = self.find_ote_zone(last_sh, last_sl, "sell")
            if ote_low <= close <= ote_high:
                direction  = "sell"
                setup_type = "OTE"
                confluence.append(f"OTE zone ({ote_low:.5f} - {ote_high:.5f})")
                confluence.append(f"Trend baissier confirmé")

        # ── Judas Swing ──
        judas = self.detect_judas_swing(df)
        if judas and not direction:
            if judas == "bullish_judas":
                direction  = "buy"
                setup_type = "JUDAS_SWING"
                confluence.append("Bullish Judas Swing")
            elif judas == "bearish_judas":
                direction  = "sell"
                setup_type = "JUDAS_SWING"
                confluence.append("Bearish Judas Swing")

        # ── Liquidity Pool Targets ──
        if pools["BSL"] and direction == "sell":
            nearest_bsl = max([l for l in pools["BSL"] if l < close], default=None)
            if nearest_bsl:
                confluence.append(f"BSL target @ {nearest_bsl:.5f}")

        if pools["SSL"] and direction == "buy":
            nearest_ssl = max([l for l in pools["SSL"] if l < close], default=None)
            if nearest_ssl:
                confluence.append(f"SSL swept @ {nearest_ssl:.5f}")

        # Confluence EMA
        if direction == "buy" and ind.above_ema200:
            confluence.append("Au-dessus EMA200")
        elif direction == "sell" and not ind.above_ema200:
            confluence.append("En dessous EMA200")

        if not direction:
            return ICTSignal(
                valid=False, direction="", entry=0, stop_loss=0, take_profit=0,
                setup_type="", confluence=[], confidence=0,
                reason=f"Pas de setup ICT (trend={condition.trend}, kz={kz})"
            )

        # ── Stop Loss et Take Profit ──
        sl_dist = atr * 1.5
        if direction == "buy":
            sl = entry - sl_dist
            tp = entry + sl_dist * 2.5
            # Target vers BSL
            bsl_targets = [h for h in pools["BSL"] if h > entry + sl_dist * 2]
            if bsl_targets:
                tp = min(bsl_targets)
                confluence.append(f"TP vers BSL @ {tp:.5f}")
        else:
            sl = entry + sl_dist
            tp = entry - sl_dist * 2.5
            ssl_targets = [l for l in pools["SSL"] if l < entry - sl_dist * 2]
            if ssl_targets:
                tp = max(ssl_targets)
                confluence.append(f"TP vers SSL @ {tp:.5f}")

        confidence = min(1.0, len(confluence) * 0.2)

        return ICTSignal(
            valid=True,
            direction=direction,
            entry=round(entry, 5),
            stop_loss=round(sl, 5),
            take_profit=round(tp, 5),
            setup_type=setup_type,
            confluence=confluence,
            confidence=confidence,
            reason=f"Setup ICT : {setup_type} | Kill Zone : {kz}",
        )
