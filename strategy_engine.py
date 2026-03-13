"""
strategy_engine.py
Orchestrateur des stratégies.
Sélectionne et exécute la stratégie selon le mode et les conditions de marché.
"""

import pandas as pd
import logging
from dataclasses import dataclass
from typing import Optional, Any

import config
from market_analysis import MarketAnalyzer, MarketCondition
from smc_strategy import SMCStrategy
from ict_strategy import ICTStrategy
from supply_demand_strategy import SupplyDemandStrategy
from price_action_strategy import PriceActionStrategy

logger = logging.getLogger(__name__)


@dataclass
class StrategySignal:
    valid: bool
    strategy: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    confidence: float
    confluence: list
    setup_type: str
    reason: str
    market_condition: Optional[MarketCondition] = None


class StrategyEngine:
    """Sélectionne et exécute la meilleure stratégie selon les conditions."""

    def __init__(self):
        self.analyzer  = MarketAnalyzer()
        self.smc       = SMCStrategy()
        self.ict       = ICTStrategy()
        self.sd        = SupplyDemandStrategy()
        self.pa        = PriceActionStrategy()

        self.active_strategy = config.ACTIVE_STRATEGY
        self.active_mode     = config.ACTIVE_MODE

    # ──────────────────────────────────────────
    # STRATÉGIE SÉLECTIONNÉE
    # ──────────────────────────────────────────

    def run(self, df: pd.DataFrame, pair: str) -> StrategySignal:
        """
        Exécute la stratégie active et retourne un signal unifié.
        En mode 'auto', sélectionne la stratégie selon les conditions.
        """
        condition = self.analyzer.analyze(df)
        logger.info(
            f"[Engine] {pair} | trend={condition.trend} | regime={condition.regime} "
            f"| bias={condition.bias} | strategy={self.active_strategy}"
        )

        strategy = self.active_strategy

        # Sélection automatique selon le régime de marché
        if strategy == "auto":
            if condition.regime == "ranging":
                strategy = "supplydemand"
            elif condition.momentum == "strong":
                strategy = "smc"
            else:
                strategy = "priceaction"

        raw = self._dispatch(strategy, df, pair)
        return self._normalize(raw, strategy, condition)

    def _dispatch(self, strategy: str, df: pd.DataFrame, pair: str) -> Any:
        if strategy == "smc":
            return self.smc.generate_signal(df, pair)
        elif strategy == "ict":
            return self.ict.generate_signal(df, pair)
        elif strategy == "supplydemand":
            return self.sd.generate_signal(df, pair)
        elif strategy == "priceaction":
            return self.pa.generate_signal(df, pair)
        else:
            logger.warning(f"Stratégie inconnue : {strategy}, fallback SMC")
            return self.smc.generate_signal(df, pair)

    def _normalize(self, raw: Any, strategy: str, condition: MarketCondition) -> StrategySignal:
        """Convertit le signal brut en StrategySignal unifié."""
        if not raw.valid:
            return StrategySignal(
                valid=False, strategy=strategy, direction="",
                entry=0, stop_loss=0, take_profit=0,
                confidence=0, confluence=[], setup_type="",
                reason=raw.reason, market_condition=condition,
            )

        # Filtre de cohérence : signal vs trend global
        if raw.direction == "buy" and condition.trend == "bearish" and condition.momentum == "strong":
            logger.info("[Engine] Signal BUY filtré (contre-tendance forte)")
            return StrategySignal(
                valid=False, strategy=strategy, direction="buy",
                entry=raw.entry, stop_loss=raw.stop_loss, take_profit=raw.take_profit,
                confidence=0, confluence=raw.confluence, setup_type=getattr(raw, "setup_type", ""),
                reason="Filtré : contre-tendance forte",
                market_condition=condition,
            )

        if raw.direction == "sell" and condition.trend == "bullish" and condition.momentum == "strong":
            logger.info("[Engine] Signal SELL filtré (contre-tendance forte)")
            return StrategySignal(
                valid=False, strategy=strategy, direction="sell",
                entry=raw.entry, stop_loss=raw.stop_loss, take_profit=raw.take_profit,
                confidence=0, confluence=raw.confluence, setup_type=getattr(raw, "setup_type", ""),
                reason="Filtré : contre-tendance forte",
                market_condition=condition,
            )

        return StrategySignal(
            valid=True,
            strategy=strategy,
            direction=raw.direction,
            entry=raw.entry,
            stop_loss=raw.stop_loss,
            take_profit=raw.take_profit,
            confidence=raw.confidence,
            confluence=raw.confluence,
            setup_type=getattr(raw, "setup_type", ""),
            reason=raw.reason,
            market_condition=condition,
        )

    # ──────────────────────────────────────────
    # CONFIGURATION
    # ──────────────────────────────────────────

    def set_strategy(self, name: str) -> bool:
        valid = ["smc", "ict", "supplydemand", "priceaction", "auto"]
        if name in valid:
            self.active_strategy = name
            logger.info(f"[Engine] Stratégie changée : {name}")
            return True
        return False

    def set_mode(self, mode: str) -> bool:
        if mode in config.TRADING_MODES:
            self.active_mode = mode
            logger.info(f"[Engine] Mode changé : {mode}")
            return True
        return False

    def get_status(self) -> dict:
        return {
            "strategy": self.active_strategy,
            "mode":     self.active_mode,
        }
