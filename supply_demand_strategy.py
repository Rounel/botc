"""
supply_demand_strategy.py
Zones d'offre et de demande institutionnelles :
- Identification des bases (Rally-Base-Drop, Drop-Base-Rally)
- Zones fraîches vs testées
- Confirmation d'entrée
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
import logging

from market_analysis import MarketAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class Zone:
    top: float
    bottom: float
    zone_type: str      # "demand" | "supply"
    pattern: str        # "DBR" | "RBD" | "DBD" | "RBR"
    fresh: bool         # Zone non encore testée
    strength: float
    index: int


@dataclass
class SDSignal:
    valid: bool
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    zone: Optional[Zone]
    confluence: List[str]
    confidence: float
    reason: str = ""


class SupplyDemandStrategy:
    """Zones d'offre et de demande institutionnelles."""

    def __init__(self):
        self.analyzer = MarketAnalyzer()

    # ──────────────────────────────────────────
    # DÉTECTION DES ZONES
    # ──────────────────────────────────────────

    def find_demand_zones(self, df: pd.DataFrame) -> List[Zone]:
        """
        Demand zone = Drop-Base-Rally (DBR).
        Le prix chute, consolide (base), puis monte fortement.
        """
        zones = []
        closes = df['close'].values
        opens  = df['open'].values
        highs  = df['high'].values
        lows   = df['low'].values
        n = len(df)

        for i in range(3, n - 4):
            # Chute avant la base
            drop = closes[i-1] < opens[i-1] and \
                   (opens[i-1] - closes[i-1]) / (highs[i-1] - lows[i-1] + 1e-10) > 0.5

            # Base (faible mouvement)
            base = abs(closes[i] - opens[i]) / (highs[i] - lows[i] + 1e-10) < 0.4

            # Rally fort après
            rally = closes[i+1] > opens[i+1] and \
                    (closes[i+1] - opens[i+1]) / (highs[i+1] - lows[i+1] + 1e-10) > 0.6

            if drop and base and rally:
                # Vérifier que la zone est encore fraîche
                zone_top = highs[i]
                zone_bot = lows[i]

                # Zone testée si le prix est revenu dedans
                retested = any(
                    lows[j] < zone_top and closes[j] > zone_bot
                    for j in range(i+2, min(i+20, n))
                )

                strength = (closes[i+1] - opens[i+1]) / (highs[i-1] - lows[i-1] + 1e-10)
                zones.append(Zone(
                    top=zone_top, bottom=zone_bot,
                    zone_type="demand", pattern="DBR",
                    fresh=not retested,
                    strength=min(1.0, strength),
                    index=i,
                ))

        return zones

    def find_supply_zones(self, df: pd.DataFrame) -> List[Zone]:
        """
        Supply zone = Rally-Base-Drop (RBD).
        Le prix monte, consolide, puis chute fortement.
        """
        zones = []
        closes = df['close'].values
        opens  = df['open'].values
        highs  = df['high'].values
        lows   = df['low'].values
        n = len(df)

        for i in range(3, n - 4):
            rally = closes[i-1] > opens[i-1] and \
                    (closes[i-1] - opens[i-1]) / (highs[i-1] - lows[i-1] + 1e-10) > 0.5
            base  = abs(closes[i] - opens[i]) / (highs[i] - lows[i] + 1e-10) < 0.4
            drop  = closes[i+1] < opens[i+1] and \
                    (opens[i+1] - closes[i+1]) / (highs[i+1] - lows[i+1] + 1e-10) > 0.6

            if rally and base and drop:
                zone_top = highs[i]
                zone_bot = lows[i]
                retested = any(
                    highs[j] > zone_bot and closes[j] < zone_top
                    for j in range(i+2, min(i+20, n))
                )
                strength = (opens[i+1] - closes[i+1]) / (highs[i-1] - lows[i-1] + 1e-10)
                zones.append(Zone(
                    top=zone_top, bottom=zone_bot,
                    zone_type="supply", pattern="RBD",
                    fresh=not retested,
                    strength=min(1.0, strength),
                    index=i,
                ))

        return zones

    # ──────────────────────────────────────────
    # SIGNAL S&D
    # ──────────────────────────────────────────

    def generate_signal(self, df: pd.DataFrame, pair: str) -> SDSignal:
        """Signal basé sur retest de zone fraîche."""
        condition = self.analyzer.analyze(df)
        ind = self.analyzer.get_indicators(df)
        close = df['close'].iloc[-1]
        atr = ind.atr

        demand_zones = self.find_demand_zones(df)
        supply_zones = self.find_supply_zones(df)

        # Garder uniquement les zones fraîches
        fresh_demand = [z for z in demand_zones if z.fresh and z.top > df['low'].min()]
        fresh_supply = [z for z in supply_zones if z.fresh and z.bottom < df['high'].max()]

        confluence = []
        direction  = None
        entry      = close
        zone_hit   = None
        sl = tp    = 0.0

        # ── Retest zone de demande ──
        for zone in sorted(fresh_demand, key=lambda z: -z.strength):
            if zone.bottom <= close <= zone.top:
                if condition.trend in ("bullish", "neutral"):
                    direction = "buy"
                    entry     = close
                    zone_hit  = zone
                    sl = zone.bottom - atr * 0.5
                    tp = close + abs(close - sl) * 2.5
                    confluence.append(f"Demand zone fraîche [{zone.bottom:.5f} - {zone.top:.5f}]")
                    confluence.append(f"Pattern : {zone.pattern} (force={zone.strength:.2f})")
                    break

        # ── Retest zone d'offre ──
        if not direction:
            for zone in sorted(fresh_supply, key=lambda z: -z.strength):
                if zone.bottom <= close <= zone.top:
                    if condition.trend in ("bearish", "neutral"):
                        direction = "sell"
                        entry     = close
                        zone_hit  = zone
                        sl = zone.top + atr * 0.5
                        tp = close - abs(sl - close) * 2.5
                        confluence.append(f"Supply zone fraîche [{zone.bottom:.5f} - {zone.top:.5f}]")
                        confluence.append(f"Pattern : {zone.pattern} (force={zone.strength:.2f})")
                        break

        if not direction:
            return SDSignal(
                valid=False, direction="", entry=0, stop_loss=0, take_profit=0,
                zone=None, confluence=[], confidence=0,
                reason=f"Pas de retest zone fraîche (trend={condition.trend})"
            )

        # Confluence EMA
        if direction == "buy" and ind.above_ema200:
            confluence.append("EMA200 support")
        elif direction == "sell" and not ind.above_ema200:
            confluence.append("EMA200 résistance")

        # Confluence RSI
        if direction == "buy" and ind.rsi < 50:
            confluence.append(f"RSI en zone achat ({ind.rsi:.1f})")
        elif direction == "sell" and ind.rsi > 50:
            confluence.append(f"RSI en zone vente ({ind.rsi:.1f})")

        confidence = min(1.0, len(confluence) * 0.25 + (zone_hit.strength * 0.3 if zone_hit else 0))

        return SDSignal(
            valid=True,
            direction=direction,
            entry=round(entry, 5),
            stop_loss=round(sl, 5),
            take_profit=round(tp, 5),
            zone=zone_hit,
            confluence=confluence,
            confidence=round(confidence, 2),
            reason=f"Retest zone {'demande' if direction=='buy' else 'offre'} fraîche",
        )
