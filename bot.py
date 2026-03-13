"""
bot.py
Contrôleur principal du bot de trading.
Orchestre tous les modules : analyse, stratégie, risque, exécution, Telegram.
"""

import asyncio
import logging
import time
from datetime import datetime, time as dtime
from typing import Optional
import pandas as pd
import numpy as np
from dotenv import load_dotenv
load_dotenv()

import config
from strategy_engine import StrategyEngine
from risk_management import RiskManager
from trade_executor import TradeExecutor, Trade
from performance_tracker import PerformanceTracker
from news_filter import NewsFilter
from telegram_interface import TelegramInterface

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log"),
    ]
)
logger = logging.getLogger(__name__)


class TradingBot:
    """Bot de trading principal."""

    def __init__(self):
        self.running          = False
        self.active_pair      = config.ACTIVE_PAIR

        _mode_tf = {"scalping": "M5", "intraday": "H1", "swing": "H4"}
        self.active_timeframe = _mode_tf.get(config.ACTIVE_MODE, "H1")

        # Modules
        self.engine       = StrategyEngine()
        self.risk_manager = RiskManager()
        self.executor     = TradeExecutor()
        self.tracker      = PerformanceTracker()
        self.news_filter  = NewsFilter()
        self.telegram     = TelegramInterface(self)

        # Initialisation du peak balance
        balance = self.executor.get_balance()
        self.risk_manager.peak_balance = balance
        logger.info(f"[Bot] Initialisé | Balance={balance:.2f}$ | Paire={self.active_pair}")

    # ──────────────────────────────────────────
    # CONTRÔLE
    # ──────────────────────────────────────────

    def start(self) -> str:
        self.running = True
        self.risk_manager.bot_active = True
        balance = self.executor.get_balance()
        msg = (
            f"✅ Bot démarré\n"
            f"💱 Paire : {self.active_pair}\n"
            f"⚡ Mode : {self.engine.active_mode}\n"
            f"🎯 Stratégie : {self.engine.active_strategy}\n"
            f"⚖️ Risque : {self.risk_manager.risk_pct}%\n"
            f"💰 Balance : {balance:.2f}$"
        )
        logger.info("[Bot] Démarré")
        return msg

    def stop(self) -> str:
        self.running = False
        logger.info("[Bot] Arrêté")
        return "Bot stoppé. Positions ouvertes conservées jusqu'au SL/TP."

    def get_status(self) -> str:
        balance = self.executor.get_balance()
        open_trades = self.executor.get_open_trades()
        stats = self.tracker.calculate_stats()
        risk = self.risk_manager

        return (
            f"📊 *Statut du Bot*\n\n"
            f"{'🟢 Actif' if self.running else '🔴 Stoppé'}\n\n"
            f"💱 Paire : `{self.active_pair}`\n"
            f"⏱ Timeframe : `{self.active_timeframe}`\n"
            f"⚡ Mode : `{self.engine.active_mode}`\n"
            f"🎯 Stratégie : `{self.engine.active_strategy}`\n"
            f"⚖️ Risque : `{risk.risk_pct}%`\n\n"
            f"💰 Balance : `{balance:.2f}$`\n"
            f"📂 Trades ouverts : `{len(open_trades)}`\n"
            f"📈 Trades totaux : `{stats.total_trades}`\n"
            f"🎯 Win Rate : `{stats.win_rate}%`\n"
            f"💹 PnL Total : `{stats.total_pnl:+.2f}$`\n\n"
            f"🛡 Pertes consécutives : `{risk.consecutive_losses}/{risk.max_consec_losses}`\n"
            f"📅 Trades aujourd'hui : `{risk.daily_trades}/{risk.max_daily_trades}`"
        )

    def get_dashboard(self) -> str:
        balance = self.executor.get_balance()
        stats = self.tracker.calculate_stats()
        open_trades = self.executor.get_open_trades()
        news_ok, news_reason = self.news_filter.is_trading_allowed(self.active_pair)

        trades_str = ""
        for t in open_trades:
            icon = "📈" if t.direction == "buy" else "📉"
            trades_str += f"\n  {icon} {t.pair} {t.direction.upper()} @ {t.entry}"

        return (
            f"🎛 *Dashboard*\n"
            f"{'─' * 30}\n"
            f"💰 Balance : `{balance:.2f}$`\n"
            f"📈 PnL Total : `{stats.total_pnl:+.2f}$`\n"
            f"🎯 Win Rate : `{stats.win_rate}%`\n"
            f"🔁 Profit Factor : `{stats.profit_factor}`\n"
            f"📉 Max DD : `{stats.max_drawdown:.2f}$`\n"
            f"{'─' * 30}\n"
            f"⚡ Mode : `{self.engine.active_mode}`\n"
            f"🎯 Stratégie : `{self.engine.active_strategy}`\n"
            f"💱 Paire : `{self.active_pair}`\n"
            f"⏱ TF : `{self.active_timeframe}`\n"
            f"⚖️ Risque : `{self.risk_manager.risk_pct}%`\n"
            f"{'─' * 30}\n"
            f"{'🟢 News OK' if news_ok else '🔴 ' + news_reason}\n"
            f"📂 Positions ouvertes : {len(open_trades)}"
            f"{trades_str}\n"
            f"{'─' * 30}\n"
            f"🕐 `{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}`"
        )

    # ──────────────────────────────────────────
    # DONNÉES DE MARCHÉ (simulé / à connecter)
    # ──────────────────────────────────────────

    def get_market_data(self, pair: str, timeframe: str, bars: int = 200) -> pd.DataFrame:
        """
        Récupère les données OHLCV depuis le broker.
        En mode demo : génère des données synthétiques réalistes.
        """
        if config.BROKER == "mt5" and self.executor._broker_client:
            return self._get_mt5_data(pair, timeframe, bars)
        elif config.BROKER == "binance" and self.executor._broker_client:
            return self._get_binance_data(pair, timeframe, bars)
        else:
            return self._generate_synthetic_data(pair, bars)

    def _get_mt5_data(self, pair: str, timeframe: str, bars: int) -> pd.DataFrame:
        import MetaTrader5 as mt5
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,  "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,  "D1": mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe, mt5.TIMEFRAME_H1)
        rates = mt5.copy_rates_from_pos(pair, tf, 0, bars)
        if rates is None:
            return self._generate_synthetic_data(pair, bars)
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.rename(columns={"tick_volume": "volume"})
        return df[['time', 'open', 'high', 'low', 'close', 'volume']]

    def _get_binance_data(self, pair: str, timeframe: str, bars: int) -> pd.DataFrame:
        tf_map = {"M1": "1m", "M5": "5m", "M15": "15m", "H1": "1h", "H4": "4h", "D1": "1d"}
        tf = tf_map.get(timeframe, "1h")
        klines = self.executor._broker_client.get_klines(
            symbol=pair.replace("USD", "USDT"), interval=tf, limit=bars
        )
        df = pd.DataFrame(klines, columns=[
            'time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        return df[['time', 'open', 'high', 'low', 'close', 'volume']]

    def _generate_synthetic_data(self, pair: str, bars: int = 200) -> pd.DataFrame:
        """Données synthétiques pour mode demo/test."""
        np.random.seed(42)
        base_prices = {
            "XAUUSD": 2300.0, "BTCUSD": 65000.0,
            "EURUSD": 1.0850, "GBPUSD": 1.2700, "XAGUSD": 29.0,
        }
        base = base_prices.get(pair, 1.0)
        returns = np.random.normal(0, 0.001, bars)
        closes = base * np.cumprod(1 + returns)

        highs  = closes * (1 + np.abs(np.random.normal(0, 0.0005, bars)))
        lows   = closes * (1 - np.abs(np.random.normal(0, 0.0005, bars)))
        opens  = np.roll(closes, 1)
        opens[0] = closes[0]
        volumes = np.random.randint(100, 10000, bars).astype(float)

        return pd.DataFrame({
            'time':   pd.date_range(end=datetime.utcnow(), periods=bars, freq='1h'),
            'open':   opens, 'high': highs, 'low': lows,
            'close':  closes, 'volume': volumes,
        })

    # ──────────────────────────────────────────
    # BOUCLE PRINCIPALE
    # ──────────────────────────────────────────

    async def trading_loop(self):
        """Boucle asynchrone principale d'analyse et de trading."""
        logger.info("[Bot] Boucle de trading démarrée")
        interval_map = {
            "M1": 60, "M5": 300, "M15": 900,
            "H1": 3600, "H4": 14400, "D1": 86400,
        }

        while True:
            try:
                if self.running and self.risk_manager.bot_active:
                    # Vérifier SL/TP des trades ouverts
                    df = self.get_market_data(self.active_pair, self.active_timeframe, bars=200)
                    if df is not None and len(df) >= 1:
                        current_price = df['close'].iloc[-1]
                        closed_trades = self.executor.check_sl_tp(self.active_pair, current_price)
                        for trade in closed_trades:
                            self.risk_manager.record_trade_result(
                                trade.pnl, self.executor.get_balance()
                            )
                            self.tracker.record_trade(trade)
                            notif = self.tracker.format_trade_notification(trade, opened=False)
                            await self.telegram.send_notification(notif)

                    await self._analyze_and_trade()

                    # Reset compteurs journaliers à minuit UTC
                    now = datetime.utcnow()
                    if now.hour == 0 and now.minute < 1:
                        self.risk_manager.reset_daily()
                        await self.telegram.send_notification(
                            self.tracker.format_daily_summary()
                        )
            except Exception as e:
                logger.error(f"[Bot] Erreur boucle : {e}", exc_info=True)

            interval = interval_map.get(self.active_timeframe, 3600)
            await asyncio.sleep(interval)

    async def _analyze_and_trade(self):
        """Analyse le marché et exécute un trade si signal valide."""
        pair = self.active_pair
        tf   = self.active_timeframe

        # Filtre news
        allowed, reason = self.news_filter.is_trading_allowed(pair)
        if not allowed:
            logger.info(f"[Bot] Trading bloqué : {reason}")
            await self.telegram.send_notification(f"⚠️ {reason}")
            return

        # Données marché
        df = self.get_market_data(pair, tf, bars=200)
        if df is None or len(df) < 50:
            logger.warning("[Bot] Données insuffisantes")
            return

        # Signal stratégie
        signal = self.engine.run(df, pair)
        logger.info(
            f"[Bot] {pair} {tf} | Signal={signal.valid} "
            f"| dir={signal.direction} | conf={signal.confidence:.2f}"
        )

        if not signal.valid:
            logger.info(f"[Bot] Pas de signal : {signal.reason}")
            return

        # Validation risque
        balance = self.executor.get_balance()
        params = self.risk_manager.validate_trade(
            balance=balance,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            direction=signal.direction,
            pair=pair,
        )

        if not params.valid:
            logger.info(f"[Bot] Trade rejeté : {params.reason}")
            await self.telegram.send_notification(f"🚫 Trade rejeté : {params.reason}")
            return

        # Exécution
        trade = self.executor.open_trade(
            pair=pair,
            direction=signal.direction,
            entry=params.entry,
            stop_loss=params.stop_loss,
            take_profit=params.take_profit,
            lot_size=params.lot_size,
            strategy=signal.strategy,
            setup_type=signal.setup_type,
        )

        if trade:
            notif = self.tracker.format_trade_notification(trade, opened=True)
            rr_line = f"\n📐 RR : `{params.risk_reward}` | Risque : `{params.risk_amount:.2f}$`"
            conf_line = f"\n🔗 Confluences :\n" + "\n".join(f"  • {c}" for c in signal.confluence)
            await self.telegram.send_notification(notif + rr_line + conf_line)

    # ──────────────────────────────────────────
    # LANCEMENT
    # ──────────────────────────────────────────

    def run(self):
        """Lance le bot complet (Telegram + boucle de trading)."""
        async def post_init(app):
            asyncio.create_task(self.trading_loop())

        # Fix Python 3.10+ : créer l'event loop avant run_polling
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Setup Telegram avec post_init pour démarrer la boucle de trading
        self.telegram.setup(config.TELEGRAM_TOKEN, post_init=post_init)

        # Lancer Telegram polling (gère son propre event loop)
        self.telegram.run()


if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
