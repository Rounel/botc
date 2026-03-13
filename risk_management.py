"""
risk_management.py
Gestion du risque professionnelle :
- Calcul de la taille de position
- Validation des setups (RR, drawdown, trades consécutifs)
- Protection du capital
"""

import logging
from dataclasses import dataclass
from typing import Optional

import config

logger = logging.getLogger(__name__)


@dataclass
class TradeParameters:
    pair: str
    direction: str          # "buy" | "sell"
    entry: float
    stop_loss: float
    take_profit: float
    lot_size: float
    risk_amount: float      # en USD
    risk_percent: float
    risk_reward: float
    valid: bool
    reason: str = ""


class RiskManager:
    """Calcule et valide les paramètres de chaque trade."""

    def __init__(self):
        self.risk_pct          = config.DEFAULT_RISK_PERCENT
        self.max_risk_pct      = config.MAX_RISK_PERCENT
        self.min_rr            = config.MIN_RISK_REWARD
        self.max_consec_losses = config.MAX_CONSECUTIVE_LOSSES
        self.max_daily_trades  = config.MAX_DAILY_TRADES
        self.max_dd_pct        = config.MAX_DAILY_DRAWDOWN_PCT
        self.total_dd_pct      = config.MAX_TOTAL_DRAWDOWN_PCT

        # État interne
        self.consecutive_losses  = 0
        self.daily_trades        = 0
        self.daily_pnl           = 0.0
        self.peak_balance        = 0.0
        self.bot_active          = True

    # ──────────────────────────────────────────
    # TAILLE DE POSITION
    # ──────────────────────────────────────────

    def calculate_lot_size(
        self,
        balance: float,
        entry: float,
        stop_loss: float,
        pair: str,
    ) -> float:
        """
        Calcule le lot size basé sur le risque en % du capital.
        Formule : lot = (balance * risk_pct) / (pip_distance * pip_value)
        """
        cfg = config.ASSET_CONFIG.get(pair, {
            "pip_size": 0.0001, "contract_size": 100000, "min_lot": 0.01
        })

        risk_amount   = balance * (self.risk_pct / 100)
        pip_distance  = abs(entry - stop_loss) / cfg["pip_size"]
        pip_value     = cfg["pip_size"] * cfg["contract_size"]

        if pip_distance == 0 or pip_value == 0:
            return cfg["min_lot"]

        lot = risk_amount / (pip_distance * pip_value)
        lot = max(lot, cfg["min_lot"])
        lot = round(lot, 3)

        logger.info(
            f"[RiskMgr] {pair} | Balance={balance:.2f} | Risk={risk_amount:.2f}$ "
            f"| SL_pips={pip_distance:.1f} | Lot={lot}"
        )
        return lot

    # ──────────────────────────────────────────
    # CALCUL DES TARGETS
    # ──────────────────────────────────────────

    def calculate_take_profit(
        self,
        entry: float,
        stop_loss: float,
        direction: str,
        rr: float = 2.0,
        liquidity_target: Optional[float] = None,
    ) -> float:
        """Calcule le TP basé sur le RR ou un target de liquidité."""
        sl_distance = abs(entry - stop_loss)

        if direction == "buy":
            tp_rr = entry + sl_distance * rr
            if liquidity_target and liquidity_target > entry:
                return min(tp_rr, liquidity_target)
            return tp_rr
        else:
            tp_rr = entry - sl_distance * rr
            if liquidity_target and liquidity_target < entry:
                return max(tp_rr, liquidity_target)
            return tp_rr

    # ──────────────────────────────────────────
    # VALIDATION DU SETUP
    # ──────────────────────────────────────────

    def validate_trade(
        self,
        balance: float,
        entry: float,
        stop_loss: float,
        take_profit: float,
        direction: str,
        pair: str,
    ) -> TradeParameters:
        """Valide et construit les paramètres complets d'un trade."""

        # Vérifications bot actif
        if not self.bot_active:
            return self._invalid("Bot arrêté (drawdown/pertes consécutives)")

        if self.daily_trades >= self.max_daily_trades:
            return self._invalid(f"Limite journalière atteinte ({self.max_daily_trades} trades)")

        if self.consecutive_losses >= self.max_consec_losses:
            self.bot_active = False
            return self._invalid(f"{self.max_consec_losses} pertes consécutives — bot arrêté")

        # Drawdown journalier
        if balance > 0 and self.peak_balance > 0:
            drawdown = (self.peak_balance - balance) / self.peak_balance * 100
            if drawdown >= self.total_dd_pct:
                self.bot_active = False
                return self._invalid(f"Drawdown total {drawdown:.1f}% atteint — bot arrêté")

        daily_dd = self.daily_pnl / balance * 100 if balance > 0 else 0
        if daily_dd <= -self.max_dd_pct:
            return self._invalid(f"Drawdown journalier {daily_dd:.1f}% atteint")

        # Calcul RR
        sl_dist = abs(entry - stop_loss)
        tp_dist = abs(take_profit - entry)
        if sl_dist == 0:
            return self._invalid("Stop loss identique à l'entrée")

        rr = tp_dist / sl_dist
        if rr < self.min_rr:
            return self._invalid(f"RR {rr:.2f} insuffisant (min {self.min_rr})")

        # Calcul lot
        lot = self.calculate_lot_size(balance, entry, stop_loss, pair)
        risk_amount = balance * (self.risk_pct / 100)

        return TradeParameters(
            pair=pair,
            direction=direction,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=lot,
            risk_amount=risk_amount,
            risk_percent=self.risk_pct,
            risk_reward=round(rr, 2),
            valid=True,
            reason="Setup valide",
        )

    def _invalid(self, reason: str) -> TradeParameters:
        logger.warning(f"[RiskMgr] Trade rejeté : {reason}")
        return TradeParameters(
            pair="", direction="", entry=0, stop_loss=0, take_profit=0,
            lot_size=0, risk_amount=0, risk_percent=0, risk_reward=0,
            valid=False, reason=reason,
        )

    # ──────────────────────────────────────────
    # MISE À JOUR DE L'ÉTAT
    # ──────────────────────────────────────────

    def record_trade_result(self, pnl: float, balance: float):
        """Mise à jour après fermeture d'un trade."""
        self.daily_trades += 1
        self.daily_pnl += pnl

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        if balance > self.peak_balance:
            self.peak_balance = balance

    def reset_daily(self):
        """Réinitialise les compteurs journaliers (appelé chaque jour)."""
        self.daily_trades = 0
        self.daily_pnl    = 0.0
        logger.info("[RiskMgr] Compteurs journaliers réinitialisés")

    def set_risk(self, pct: float):
        """Modifie le risque par trade (via commande Telegram)."""
        if 0.1 <= pct <= self.max_risk_pct:
            self.risk_pct = pct
            logger.info(f"[RiskMgr] Risque mis à jour : {pct}%")
            return True
        return False

    def resume(self):
        """Réactive le bot manuellement."""
        self.consecutive_losses = 0
        self.bot_active = True
        logger.info("[RiskMgr] Bot réactivé manuellement")
