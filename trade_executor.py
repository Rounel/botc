"""
trade_executor.py
Exécution des trades sur broker réel (MT5, Binance, OANDA) ou en mode demo.
Gère l'ouverture, fermeture, et suivi des positions.
"""

import logging
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict

import config

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    id: str
    pair: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    lot_size: float
    open_time: datetime
    close_time: Optional[datetime] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    status: str = "open"        # "open" | "closed" | "cancelled"
    strategy: str = ""
    setup_type: str = ""
    broker_ticket: Optional[str] = None


class TradeExecutor:
    """
    Interface d'exécution unifiée.
    Dispatcher selon le broker configuré.
    """

    def __init__(self):
        self.broker = config.BROKER
        self.open_trades: Dict[str, Trade] = {}
        self._balance = config.INITIAL_BALANCE
        self._broker_client = None
        self._init_broker()

    # ──────────────────────────────────────────
    # INITIALISATION BROKER
    # ──────────────────────────────────────────

    def _init_broker(self):
        if self.broker == "mt5":
            self._init_mt5()
        elif self.broker == "binance":
            self._init_binance()
        elif self.broker == "oanda":
            self._init_oanda()
        else:
            logger.info("[Executor] Mode DEMO activé")

    def _init_mt5(self):
        try:
            import MetaTrader5 as mt5
            if not mt5.initialize():
                raise ConnectionError("MT5 init failed")
            login_ok = mt5.login(
                config.MT5_LOGIN,
                password=config.MT5_PASSWORD,
                server=config.MT5_SERVER,
            )
            if not login_ok:
                raise ConnectionError(f"MT5 login failed : {mt5.last_error()}")
            self._broker_client = mt5
            logger.info("[Executor] MT5 connecté")
        except ImportError:
            logger.warning("[Executor] MetaTrader5 non installé, fallback demo")
            self.broker = "demo"

    def _init_binance(self):
        try:
            from binance.client import Client
            self._broker_client = Client(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)
            info = self._broker_client.get_account()
            logger.info(f"[Executor] Binance connecté | Status={info['accountType']}")
        except ImportError:
            logger.warning("[Executor] binance non installé, fallback demo")
            self.broker = "demo"

    def _init_oanda(self):
        try:
            import oandapyV20
            import oandapyV20.endpoints.accounts as accounts
            self._broker_client = oandapyV20.API(access_token=config.OANDA_API_KEY)
            logger.info("[Executor] OANDA connecté")
        except ImportError:
            logger.warning("[Executor] oandapyV20 non installé, fallback demo")
            self.broker = "demo"

    # ──────────────────────────────────────────
    # BALANCE
    # ──────────────────────────────────────────

    def get_balance(self) -> float:
        if self.broker == "demo":
            return self._balance
        elif self.broker == "mt5":
            mt5 = self._broker_client
            info = mt5.account_info()
            return info.balance if info else self._balance
        elif self.broker == "binance":
            info = self._broker_client.get_asset_balance(asset="USDT")
            return float(info["free"])
        elif self.broker == "oanda":
            import oandapyV20.endpoints.accounts as accts
            r = accts.AccountDetails(config.OANDA_ACCOUNT_ID)
            self._broker_client.request(r)
            return float(r.response["account"]["balance"])
        return self._balance

    # ──────────────────────────────────────────
    # OUVERTURE DE TRADE
    # ──────────────────────────────────────────

    def open_trade(
        self,
        pair: str,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        lot_size: float,
        strategy: str = "",
        setup_type: str = "",
    ) -> Optional[Trade]:
        trade_id = str(uuid.uuid4())[:8]
        ticket = None

        try:
            if self.broker == "mt5":
                ticket = self._mt5_open(pair, direction, lot_size, entry, stop_loss, take_profit)
            elif self.broker == "binance":
                ticket = self._binance_open(pair, direction, lot_size)
            elif self.broker == "oanda":
                ticket = self._oanda_open(pair, direction, lot_size, stop_loss, take_profit)
            else:
                # Mode demo : simuler l'ouverture
                ticket = f"DEMO_{trade_id}"
                logger.info(f"[Demo] Trade ouvert : {direction} {lot_size} {pair} @ {entry}")

        except Exception as e:
            logger.error(f"[Executor] Erreur ouverture trade : {e}")
            return None

        trade = Trade(
            id=trade_id,
            pair=pair,
            direction=direction,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=lot_size,
            open_time=datetime.utcnow(),
            status="open",
            strategy=strategy,
            setup_type=setup_type,
            broker_ticket=ticket,
        )
        self.open_trades[trade_id] = trade
        logger.info(f"[Executor] Trade {trade_id} ouvert : {direction} {lot_size}L {pair}")
        return trade

    def _mt5_open(self, pair, direction, lot, entry, sl, tp):
        mt5 = self._broker_client
        import MetaTrader5 as mt5_lib
        order_type = mt5_lib.ORDER_TYPE_BUY if direction == "buy" else mt5_lib.ORDER_TYPE_SELL
        req = {
            "action":    mt5_lib.TRADE_ACTION_DEAL,
            "symbol":    pair,
            "volume":    lot,
            "type":      order_type,
            "price":     entry,
            "sl":        sl,
            "tp":        tp,
            "deviation": 10,
            "magic":     20250101,
            "comment":   "TradingBot",
            "type_time": mt5_lib.ORDER_TIME_GTC,
            "type_filling": mt5_lib.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        if result.retcode != mt5_lib.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 order failed: {result.retcode}")
        return str(result.order)

    def _binance_open(self, pair, direction, lot):
        side = "BUY" if direction == "buy" else "SELL"
        order = self._broker_client.create_order(
            symbol=pair, side=side, type="MARKET", quantity=lot
        )
        return str(order["orderId"])

    def _oanda_open(self, pair, direction, lot, sl, tp):
        import oandapyV20.endpoints.orders as orders
        units = lot if direction == "buy" else -lot
        data = {
            "order": {
                "type": "MARKET",
                "instrument": pair,
                "units": str(int(units * 10000)),
                "stopLossOnFill": {"price": str(round(sl, 5))},
                "takeProfitOnFill": {"price": str(round(tp, 5))},
            }
        }
        r = orders.OrderCreate(config.OANDA_ACCOUNT_ID, data=data)
        self._broker_client.request(r)
        return r.response["orderFillTransaction"]["tradeOpened"]["tradeID"]

    # ──────────────────────────────────────────
    # FERMETURE DE TRADE
    # ──────────────────────────────────────────

    def close_trade(self, trade_id: str, current_price: float) -> Optional[Trade]:
        trade = self.open_trades.get(trade_id)
        if not trade or trade.status != "open":
            return None

        try:
            if self.broker != "demo":
                self._close_on_broker(trade, current_price)
        except Exception as e:
            logger.error(f"[Executor] Erreur fermeture : {e}")

        # Calcul PnL
        contract = config.ASSET_CONFIG.get(trade.pair, {}).get("contract_size", 100000)
        pip_size = config.ASSET_CONFIG.get(trade.pair, {}).get("pip_size", 0.0001)

        if trade.direction == "buy":
            pnl = (current_price - trade.entry) / pip_size * pip_size * contract * trade.lot_size
        else:
            pnl = (trade.entry - current_price) / pip_size * pip_size * contract * trade.lot_size

        trade.close_price = current_price
        trade.close_time  = datetime.utcnow()
        trade.pnl         = round(pnl, 2)
        trade.status      = "closed"

        if self.broker == "demo":
            self._balance += pnl

        del self.open_trades[trade_id]
        logger.info(f"[Executor] Trade {trade_id} fermé | PnL={pnl:.2f}$")
        return trade

    def _close_on_broker(self, trade: Trade, price: float):
        if self.broker == "mt5":
            mt5 = self._broker_client
            import MetaTrader5 as mt5_lib
            pos = mt5.positions_get(ticket=int(trade.broker_ticket))
            if pos:
                close_type = mt5_lib.ORDER_TYPE_SELL if trade.direction == "buy" else mt5_lib.ORDER_TYPE_BUY
                req = {
                    "action":   mt5_lib.TRADE_ACTION_DEAL,
                    "symbol":   trade.pair,
                    "volume":   trade.lot_size,
                    "type":     close_type,
                    "position": pos[0].ticket,
                    "price":    price,
                    "deviation": 10,
                }
                mt5.order_send(req)

    # ──────────────────────────────────────────
    # SUIVI
    # ──────────────────────────────────────────

    def get_open_trades(self) -> List[Trade]:
        return list(self.open_trades.values())

    def check_sl_tp(self, pair: str, current_price: float) -> List[Trade]:
        """Vérifie si SL ou TP est touché pour les trades demo."""
        closed = []
        for tid, trade in list(self.open_trades.items()):
            if trade.pair != pair:
                continue
            if trade.direction == "buy":
                if current_price <= trade.stop_loss or current_price >= trade.take_profit:
                    closed.append(self.close_trade(tid, current_price))
            else:
                if current_price >= trade.stop_loss or current_price <= trade.take_profit:
                    closed.append(self.close_trade(tid, current_price))
        return [t for t in closed if t]
