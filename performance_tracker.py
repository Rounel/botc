"""
performance_tracker.py
Journal des trades et statistiques de performance.
- Win rate, Profit factor, Drawdown, Expectancy
- Résumés journalier et hebdomadaire
- Export CSV
"""

import csv
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass, asdict
import os

import config
from trade_executor import Trade

logger = logging.getLogger(__name__)


@dataclass
class Stats:
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    max_drawdown: float
    avg_rr: float
    expectancy: float
    best_trade: float
    worst_trade: float
    avg_win: float
    avg_loss: float
    consecutive_wins: int
    consecutive_losses: int


class PerformanceTracker:
    """Suivi complet des performances."""

    def __init__(self):
        self.log_file   = config.LOG_FILE
        self.stats_file = config.STATS_FILE
        self.trades: List[Trade] = []
        self._load_history()

    # ──────────────────────────────────────────
    # ENREGISTREMENT
    # ──────────────────────────────────────────

    def record_trade(self, trade: Trade):
        """Enregistre un trade fermé dans le journal."""
        if trade.status != "closed":
            return

        self.trades.append(trade)
        self._append_csv(trade)
        self._save_stats()
        logger.info(f"[Tracker] Trade enregistré : {trade.id} | PnL={trade.pnl}$")

    def _append_csv(self, trade: Trade):
        file_exists = os.path.exists(self.log_file)
        with open(self.log_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "id", "pair", "direction", "entry", "stop_loss", "take_profit",
                    "lot_size", "open_time", "close_time", "close_price",
                    "pnl", "strategy", "setup_type"
                ])
            writer.writerow([
                trade.id, trade.pair, trade.direction,
                trade.entry, trade.stop_loss, trade.take_profit,
                trade.lot_size,
                trade.open_time.isoformat() if trade.open_time else "",
                trade.close_time.isoformat() if trade.close_time else "",
                trade.close_price, trade.pnl,
                trade.strategy, trade.setup_type,
            ])

    # ──────────────────────────────────────────
    # CALCUL DES STATS
    # ──────────────────────────────────────────

    def calculate_stats(self, trades: Optional[List[Trade]] = None) -> Stats:
        trades = trades or self.trades
        closed = [t for t in trades if t.status == "closed" and t.pnl is not None]

        if not closed:
            return Stats(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

        wins  = [t for t in closed if t.pnl > 0]
        losses = [t for t in closed if t.pnl <= 0]

        total_pnl  = sum(t.pnl for t in closed)
        gross_win  = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1

        win_rate = len(wins) / len(closed) * 100 if closed else 0
        profit_factor = gross_win / gross_loss if gross_loss else float("inf")

        avg_win  = gross_win / len(wins)   if wins   else 0
        avg_loss = gross_loss / len(losses) if losses else 0
        expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss)

        # Drawdown max
        running_pnl = 0
        peak = 0
        max_dd = 0
        for t in closed:
            running_pnl += t.pnl
            if running_pnl > peak:
                peak = running_pnl
            dd = peak - running_pnl
            if dd > max_dd:
                max_dd = dd

        # RR moyen
        rr_list = []
        for t in closed:
            sl_dist = abs(t.entry - t.stop_loss)
            tp_dist = abs(t.take_profit - t.entry)
            if sl_dist:
                rr_list.append(tp_dist / sl_dist)
        avg_rr = sum(rr_list) / len(rr_list) if rr_list else 0

        # Consécutifs
        max_consec_wins = max_consec_losses = 0
        cur_wins = cur_losses = 0
        for t in closed:
            if t.pnl > 0:
                cur_wins += 1
                cur_losses = 0
                max_consec_wins = max(max_consec_wins, cur_wins)
            else:
                cur_losses += 1
                cur_wins = 0
                max_consec_losses = max(max_consec_losses, cur_losses)

        return Stats(
            total_trades=len(closed),
            win_trades=len(wins),
            loss_trades=len(losses),
            win_rate=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            total_pnl=round(total_pnl, 2),
            max_drawdown=round(max_dd, 2),
            avg_rr=round(avg_rr, 2),
            expectancy=round(expectancy, 2),
            best_trade=round(max((t.pnl for t in closed), default=0), 2),
            worst_trade=round(min((t.pnl for t in closed), default=0), 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            consecutive_wins=max_consec_wins,
            consecutive_losses=max_consec_losses,
        )

    def _save_stats(self):
        stats = self.calculate_stats()
        with open(self.stats_file, "w") as f:
            json.dump(
                {k: v for k, v in stats.__dict__.items()},
                f, indent=2
            )

    def _load_history(self):
        if not os.path.exists(self.log_file):
            return
        try:
            with open(self.log_file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    t = Trade(
                        id=row["id"], pair=row["pair"],
                        direction=row["direction"],
                        entry=float(row["entry"]),
                        stop_loss=float(row["stop_loss"]),
                        take_profit=float(row["take_profit"]),
                        lot_size=float(row["lot_size"]),
                        open_time=datetime.fromisoformat(row["open_time"]) if row["open_time"] else datetime.utcnow(),
                        close_time=datetime.fromisoformat(row["close_time"]) if row["close_time"] else None,
                        close_price=float(row["close_price"]) if row["close_price"] else None,
                        pnl=float(row["pnl"]) if row["pnl"] else None,
                        status="closed",
                        strategy=row.get("strategy", ""),
                        setup_type=row.get("setup_type", ""),
                    )
                    self.trades.append(t)
            logger.info(f"[Tracker] {len(self.trades)} trades chargés depuis historique")
        except Exception as e:
            logger.warning(f"[Tracker] Erreur chargement historique : {e}")

    # ──────────────────────────────────────────
    # RÉSUMÉS TELEGRAM
    # ──────────────────────────────────────────

    def format_trade_notification(self, trade: Trade, opened: bool = True) -> str:
        icon = "📈" if trade.direction == "buy" else "📉"
        action = "OUVERT" if opened else "FERMÉ"
        lines = [
            f"{icon} *Trade {action}*",
            f"🔑 ID : `{trade.id}`",
            f"💱 Paire : `{trade.pair}`",
            f"📍 Direction : `{trade.direction.upper()}`",
            f"💰 Entrée : `{trade.entry}`",
            f"🛑 SL : `{trade.stop_loss}`",
            f"🎯 TP : `{trade.take_profit}`",
            f"📦 Lots : `{trade.lot_size}`",
            f"⚡ Stratégie : `{trade.strategy}` ({trade.setup_type})",
        ]
        if not opened and trade.pnl is not None:
            pnl_icon = "✅" if trade.pnl > 0 else "❌"
            lines.append(f"{pnl_icon} PnL : `{trade.pnl:+.2f}$`")
        return "\n".join(lines)

    def format_daily_summary(self) -> str:
        today = datetime.utcnow().date()
        today_trades = [
            t for t in self.trades
            if t.close_time and t.close_time.date() == today
        ]
        stats = self.calculate_stats(today_trades)
        return (
            f"📊 *Résumé journalier — {today}*\n\n"
            f"🔢 Trades : {stats.total_trades}\n"
            f"✅ Gains : {stats.win_trades} | ❌ Pertes : {stats.loss_trades}\n"
            f"🎯 Win Rate : {stats.win_rate}%\n"
            f"💰 PnL : {stats.total_pnl:+.2f}$\n"
            f"📉 Max Drawdown : {stats.max_drawdown:.2f}$\n"
            f"🔁 Profit Factor : {stats.profit_factor}"
        )

    def format_weekly_summary(self) -> str:
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_trades = [
            t for t in self.trades
            if t.close_time and t.close_time >= week_ago
        ]
        stats = self.calculate_stats(week_trades)
        return (
            f"📊 *Résumé hebdomadaire*\n\n"
            f"🔢 Trades : {stats.total_trades}\n"
            f"✅ Win Rate : {stats.win_rate}%\n"
            f"💰 PnL Total : {stats.total_pnl:+.2f}$\n"
            f"📉 Max DD : {stats.max_drawdown:.2f}$\n"
            f"🔁 Profit Factor : {stats.profit_factor}\n"
            f"📐 RR Moyen : {stats.avg_rr}\n"
            f"🏆 Meilleur trade : +{stats.best_trade}$\n"
            f"💔 Pire trade : {stats.worst_trade}$\n"
            f"📊 Expectancy : {stats.expectancy:.2f}$"
        )

    def format_full_stats(self) -> str:
        stats = self.calculate_stats()
        return (
            f"📈 *Statistiques globales*\n\n"
            f"🔢 Total trades : {stats.total_trades}\n"
            f"✅ Gagnants : {stats.win_trades} ({stats.win_rate}%)\n"
            f"❌ Perdants : {stats.loss_trades}\n"
            f"💰 PnL Total : {stats.total_pnl:+.2f}$\n"
            f"🔁 Profit Factor : {stats.profit_factor}\n"
            f"📐 RR Moyen : {stats.avg_rr}\n"
            f"📊 Expectancy : {stats.expectancy:.2f}$\n"
            f"📉 Max Drawdown : {stats.max_drawdown:.2f}$\n"
            f"🏆 Meilleur : +{stats.best_trade}$\n"
            f"💔 Pire : {stats.worst_trade}$\n"
            f"🔥 Série gains : {stats.consecutive_wins}\n"
            f"❄️ Série pertes : {stats.consecutive_losses}"
        )
