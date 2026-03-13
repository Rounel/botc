"""
smc_strategy.py
Smart Money Concepts (SMC) :
- Break of Structure (BOS) / Change of Character (CHOCH)
- Order Blocks (OB)
- Fair Value Gaps (FVG)
- Liquidity sweeps
- Premium / Discount zones
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List, Tuple
import logging

from market_analysis import MarketAnalyzer, MarketCondition

logger = logging.getLogger(__name__)


@dataclass
class OrderBlock:
    index: int
    high: float
    low: float
    direction: str      # "bullish" | "bearish"
    strength: float     # 0-1
    tested: bool = False


@dataclass
class FairValueGap:
    high: float
    low: float
    direction: str      # "bullish" | "bearish"
    index: int


@dataclass
class SMCSignal:
    valid: bool
    direction: str          # "buy" | "sell"
    entry: float
    stop_loss: float
    take_profit: float
    setup_type: str         # "OB_BOS" | "FVG_RETEST" | "LIQUIDITY_SWEEP"
    confluence: List[str]
    confidence: float       # 0-1
    reason: str = ""


class SMCStrategy:
    """Implémentation complète des Smart Money Concepts."""

    def __init__(self):
        self.analyzer = MarketAnalyzer()

    # ──────────────────────────────────────────
    # ORDER BLOCKS
    # ──────────────────────────────────────────

    def find_order_blocks(self, df: pd.DataFrame) -> List[OrderBlock]:
        """
        Détecte les Order Blocks institutionnels.
        Un OB bullish = dernière bougie baissière avant un fort mouvement haussier.
        Un OB bearish = dernière bougie haussière avant un fort mouvement baissier.
        """
        obs = []
        closes = df['close'].values
        opens  = df['open'].values
        highs  = df['high'].values
        lows   = df['low'].values

        for i in range(2, len(df) - 3):
            # Mouvement haussier fort (impulse)
            move_up = (closes[i+1] - opens[i+1]) / (highs[i+1] - lows[i+1] + 1e-10)
            move_up2 = closes[i+2] > closes[i+1]

            if move_up > 0.6 and move_up2:
                # Dernière bougie baissière = OB bullish
                if closes[i] < opens[i]:
                    strength = min(1.0, abs(closes[i+1] - opens[i+1]) / (highs[i+1] - lows[i+1] + 1e-10))
                    obs.append(OrderBlock(
                        index=i, high=highs[i], low=lows[i],
                        direction="bullish", strength=strength
                    ))

            # Mouvement baissier fort
            move_dn = (opens[i+1] - closes[i+1]) / (highs[i+1] - lows[i+1] + 1e-10)
            move_dn2 = closes[i+2] < closes[i+1]

            if move_dn > 0.6 and move_dn2:
                if closes[i] > opens[i]:
                    strength = min(1.0, abs(opens[i+1] - closes[i+1]) / (highs[i+1] - lows[i+1] + 1e-10))
                    obs.append(OrderBlock(
                        index=i, high=highs[i], low=lows[i],
                        direction="bearish", strength=strength
                    ))

        return obs

    # ──────────────────────────────────────────
    # FAIR VALUE GAPS
    # ──────────────────────────────────────────

    def find_fair_value_gaps(self, df: pd.DataFrame) -> List[FairValueGap]:
        """
        FVG = espace entre la bougie N-2 et N causé par un mouvement impulsif en N-1.
        Bullish FVG : high[i-2] < low[i]
        Bearish FVG : low[i-2] > high[i]
        """
        fvgs = []
        highs = df['high'].values
        lows  = df['low'].values

        for i in range(2, len(df)):
            # FVG haussier
            if highs[i-2] < lows[i]:
                fvgs.append(FairValueGap(
                    high=lows[i], low=highs[i-2],
                    direction="bullish", index=i
                ))
            # FVG baissier
            elif lows[i-2] > highs[i]:
                fvgs.append(FairValueGap(
                    high=lows[i-2], low=highs[i],
                    direction="bearish", index=i
                ))

        return fvgs[-10:]  # Garder les 10 plus récents

    # ──────────────────────────────────────────
    # PREMIUM / DISCOUNT ZONES (Fibonacci)
    # ──────────────────────────────────────────

    def get_premium_discount(
        self, swing_high: float, swing_low: float
    ) -> Tuple[float, float, float]:
        """
        Retourne les niveaux :
        - Equilibrium (0.5)
        - OTE zone bas (0.62)
        - OTE zone haut (0.79)
        """
        rng = swing_high - swing_low
        equilibrium = swing_low + rng * 0.5
        ote_low     = swing_low + rng * 0.62
        ote_high    = swing_low + rng * 0.79
        return equilibrium, ote_low, ote_high

    # ──────────────────────────────────────────
    # LIQUIDITY SWEEPS
    # ──────────────────────────────────────────

    def detect_liquidity_sweep(self, df: pd.DataFrame) -> Optional[Tuple[str, float]]:
        """
        Détecte un sweep de liquidité (stop hunt).
        Le prix dépasse un swing high/low et revient rapidement.
        """
        swing_highs = self.analyzer.find_swing_highs(df, lookback=3)
        swing_lows  = self.analyzer.find_swing_lows(df, lookback=3)
        close = df['close'].iloc[-1]
        high  = df['high'].iloc[-1]
        low   = df['low'].iloc[-1]

        if swing_highs:
            last_sh = swing_highs[-1][1]
            # Prix a dépassé le swing high et revenu en dessous → bearish sweep
            if high > last_sh and close < last_sh:
                return ("bearish_sweep", last_sh)

        if swing_lows:
            last_sl = swing_lows[-1][1]
            # Prix a cassé le swing low et revenu au-dessus → bullish sweep
            if low < last_sl and close > last_sl:
                return ("bullish_sweep", last_sl)

        return None

    # ──────────────────────────────────────────
    # SIGNAL PRINCIPAL
    # ──────────────────────────────────────────

    def generate_signal(self, df: pd.DataFrame, pair: str) -> SMCSignal:
        """
        Génère un signal SMC complet avec confluence multiple.
        """
        condition = self.analyzer.analyze(df)
        ind       = self.analyzer.get_indicators(df)
        bos_type, bos_level = self.analyzer.detect_bos_choch(df)
        obs  = self.find_order_blocks(df)
        fvgs = self.find_fair_value_gaps(df)
        sweep = self.detect_liquidity_sweep(df)

        close = df['close'].iloc[-1]
        atr   = ind.atr

        confluence = []
        direction  = None
        entry      = close
        setup_type = ""

        # ── Logique BOS/CHOCH + OB ──
        if bos_type in ("BOS_BULLISH", "CHOCH_BULLISH") and condition.bias in ("long", "none"):
            # Chercher un OB bullish en dessous du prix
            bullish_obs = [o for o in obs if o.direction == "bullish" and o.high < close]
            if bullish_obs:
                ob = max(bullish_obs, key=lambda x: x.high)  # OB le plus proche
                if close - ob.high < atr * 3:
                    direction = "buy"
                    entry = ob.high
                    setup_type = "OB_BOS"
                    confluence.append(f"BOS {bos_type}")
                    confluence.append(f"Order Block @ {ob.high:.5f}")

        elif bos_type in ("BOS_BEARISH", "CHOCH_BEARISH") and condition.bias in ("short", "none"):
            bearish_obs = [o for o in obs if o.direction == "bearish" and o.low > close]
            if bearish_obs:
                ob = min(bearish_obs, key=lambda x: x.low)
                if ob.low - close < atr * 3:
                    direction = "sell"
                    entry = ob.low
                    setup_type = "OB_BOS"
                    confluence.append(f"BOS {bos_type}")
                    confluence.append(f"Order Block @ {ob.low:.5f}")

        # ── Logique Liquidity Sweep ──
        if sweep and not direction:
            sweep_type, sweep_level = sweep
            if sweep_type == "bullish_sweep":
                direction  = "buy"
                entry      = close
                setup_type = "LIQUIDITY_SWEEP"
                confluence.append(f"Bullish sweep @ {sweep_level:.5f}")
            elif sweep_type == "bearish_sweep":
                direction  = "sell"
                entry      = close
                setup_type = "LIQUIDITY_SWEEP"
                confluence.append(f"Bearish sweep @ {sweep_level:.5f}")

        # ── Logique FVG Retest ──
        if fvgs and not direction:
            for fvg in reversed(fvgs):
                if fvg.direction == "bullish" and fvg.low < close < fvg.high:
                    direction  = "buy"
                    entry      = close
                    setup_type = "FVG_RETEST"
                    confluence.append(f"Bullish FVG retest {fvg.low:.5f}-{fvg.high:.5f}")
                    break
                elif fvg.direction == "bearish" and fvg.low < close < fvg.high:
                    direction  = "sell"
                    entry      = close
                    setup_type = "FVG_RETEST"
                    confluence.append(f"Bearish FVG retest {fvg.low:.5f}-{fvg.high:.5f}")
                    break

        if not direction:
            return SMCSignal(
                valid=False, direction="", entry=0, stop_loss=0, take_profit=0,
                setup_type="", confluence=[], confidence=0,
                reason=f"Pas de setup SMC (bias={condition.bias}, trend={condition.trend})"
            )

        # ── Confluence EMA ──
        if direction == "buy" and ind.above_ema200:
            confluence.append("Prix au-dessus EMA200")
        elif direction == "sell" and not ind.above_ema200:
            confluence.append("Prix en dessous EMA200")

        # ── Confluence RSI ──
        if direction == "buy" and 30 < ind.rsi < 60:
            confluence.append(f"RSI neutre-haussier ({ind.rsi:.1f})")
        elif direction == "sell" and 40 < ind.rsi < 70:
            confluence.append(f"RSI neutre-baissier ({ind.rsi:.1f})")

        # ── Stop Loss basé sur structure ──
        if direction == "buy":
            sl = entry - atr * 1.5
            # Trouver le swing low le plus proche comme SL
            swing_lows = self.analyzer.find_swing_lows(df)
            if swing_lows:
                nearest_sl = max([l for _, l in swing_lows if l < entry], default=sl)
                sl = min(nearest_sl - atr * 0.3, sl)
        else:
            sl = entry + atr * 1.5
            swing_highs = self.analyzer.find_swing_highs(df)
            if swing_highs:
                nearest_sh = min([h for _, h in swing_highs if h > entry], default=sl)
                sl = max(nearest_sh + atr * 0.3, sl)

        # ── Take Profit : liquidity target ──
        swing_highs = self.analyzer.find_swing_highs(df)
        swing_lows  = self.analyzer.find_swing_lows(df)
        sl_dist = abs(entry - sl)

        if direction == "buy":
            tp_candidates = [h for _, h in swing_highs if h > entry + sl_dist * 2]
            tp = min(tp_candidates) if tp_candidates else entry + sl_dist * 2.5
        else:
            tp_candidates = [l for _, l in swing_lows if l < entry - sl_dist * 2]
            tp = max(tp_candidates) if tp_candidates else entry - sl_dist * 2.5

        # Confiance selon nombre de confluences
        confidence = min(1.0, len(confluence) * 0.25)

        return SMCSignal(
            valid=True,
            direction=direction,
            entry=entry,
            stop_loss=round(sl, 5),
            take_profit=round(tp, 5),
            setup_type=setup_type,
            confluence=confluence,
            confidence=confidence,
            reason=f"Setup SMC : {setup_type} | {len(confluence)} confluences",
        )
