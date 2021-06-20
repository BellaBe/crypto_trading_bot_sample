import logging
import time
from threading import Timer
import pandas as pd

from models.models import *
import typing

if typing.TYPE_CHECKING:
    from connectors.bitmex import BitmexClient
    from connectors.binance import BinanceClient

logger = logging.getLogger()

TF_EQUIV = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


class Strategy:

    def __init__(self,
                 client: typing.Union["BitmexClient", "BinanceClient"],
                 contract: Contract,
                 exchange: str,
                 timeframe: str,
                 balance_pct: float,
                 take_profit: float,
                 stop_loss: float,
                 strategy_name: str
                 ):

        self.client = client
        self.contract = contract
        self.exchange = exchange
        self.timeframe = timeframe
        self.tf_equiv = TF_EQUIV[timeframe] * 1000  # convert to milliseconds
        self.balance_ptc = balance_pct
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.ongoing_position = False
        self.strategy_name = strategy_name
        self.trades: typing.List[Trade] = []

        self.candles: typing.List[Candle] = []
        self.logs = []

    def _add_log(self, msg: str):
        logger.info(f"{msg}")
        self.logs.append({"log": msg, "displayed": False})

    def parse_trades(self, price: float, size: float, timestamp: int) -> str:
        timestamp_diff = int(time.time() * 1000) - timestamp
        if timestamp_diff >= 2000:
            logger.warning(
                f"{self.exchange} {self.contract.symbol}: {timestamp_diff} milliseconds of difference between the "
                f"current time and the trade time")
        last_candle = self.candles[-1]
        # Same candle
        if timestamp < last_candle.timestamp + self.tf_equiv:
            last_candle.close = price
            last_candle.volume += size

            if price > last_candle.high:
                last_candle.high = price
            elif price < last_candle.low:
                last_candle.low = price

            # Check take profit or stop loss

            for trade in self.trades:
                if trade.status == "open" and trade.entry_price is not None:
                    self._check_tp_sl(trade)

            return "same_candle"

        # Missing candles
        elif timestamp >= last_candle.timestamp + 2 * self.tf_equiv:

            missing_candles = int((timestamp - last_candle.timestamp) / self.tf_equiv) - 1
            logger.info(
                f"{self.exchange} :: {missing_candles} missing candles for {self.contract.symbol} {self.timeframe} ({timestamp} {last_candle.timestamp})")

            for missing_candles in range(missing_candles):
                new_ts = last_candle.timestamp + self.tf_equiv
                candle_info = {
                    "ts": new_ts,
                    "open": price,
                    "close": price,
                    "high": price,
                    "low": price,
                    "size": size
                }
                new_candle = Candle(candle_info, self.timeframe, "parse_trade")
                self.candles.append(new_candle)
                last_candle = new_candle
                logger.info(f"{self.exchange} :: New missing candles for {self.contract.symbol} {self.timeframe}")

            new_ts = last_candle.timestamp + self.tf_equiv
            candle_info = {
                "ts": new_ts,
                "open": price,
                "close": price,
                "high": price,
                "low": price,
                "size": size
            }
            new_candle = Candle(candle_info, self.timeframe, "parse_trade")
            self.candles.append(new_candle)
            logger.info(f"{self.exchange} :: New candle for {self.contract.symbol} {self.timeframe}")

            return "new_candle"

        # New candle
        elif timestamp >= last_candle.timestamp + self.tf_equiv:
            new_ts = last_candle.timestamp + self.tf_equiv
            candle_info = {
                "ts": new_ts,
                "open": price,
                "close": price,
                "high": price,
                "low": price,
                "size": size
            }
            new_candle = Candle(candle_info, self.timeframe, "parse_trade")
            self.candles.append(new_candle)
            logger.info(f"{self.exchange} :: New candle for {self.contract.symbol} {self.timeframe}")
            return "new_candle"

    def _check_order_status(self, order_id):
        order_status = self.client.get_order_status(self.contract, order_id)
        if order_status is not None:
            logger.info(f"{self.exchange} order status: {order_status.status}")
            if order_status.status == "filled":
                for trade in self.trades:
                    if trade.entry_id == order_id:
                        trade.entry_price = order_status.avg_price
                        break
                return
        t = Timer(2.0, lambda: self._check_order_status(order_id))
        t.start()

    def _open_position(self, signal_result: int):
        trade_size = self.client.get_trade_size(self.contract, self.candles[-1].close, self.balance_ptc)
        if trade_size is None:
            return

        order_side = "buy" if signal_result == 1 else "sell"
        position_side = "long" if signal_result == 1 else "short"
        self._add_log(f"{position_side.capitalize()} signal on {self.contract.symbol} {self.timeframe}")
        order_status = self.client.place_order(self.contract, "MARKET", trade_size, order_side)
        if order_status is not None:
            self._add_log(f"{order_side.capitalize()} order placed on {self.exchange} | Status: {order_status.status} ")
            self.ongoing_position = True

            avg_fill_price = None

            if order_status.status == "filled":
                avg_fill_price = order_status.avg_price
            else:
                t = Timer(2.0, lambda: self._check_order_status(order_status.order_id))
                t.start()
            new_trade = Trade({
                "time": int(time.time() * 1000),
                "entry_price": avg_fill_price,
                "contract": self.contract,
                "strategy": self.strategy_name,
                "side": position_side,
                "status": "open",
                "pnl": 0,
                "quantity": trade_size,
                "entry_id": order_status.order_id
            })
            self.trades.append(new_trade)

    # Check take profit or stop loss position
    def _check_tp_sl(self, trade: Trade):
        tp_triggered = False
        sl_triggered = False
        price = self.candles[-1].close

        if trade.side == "long":
            if self.stop_loss is not None:
                if price <= trade.entry_price * (1 - self.stop_loss / 100):
                    sl_triggered = True

            if self.take_profit is not None:
                if price >= trade.entry_price * (1 + self.take_profit / 100):
                    tp_triggered = True

        elif trade.side == "short":
            if self.stop_loss is not None:
                if price >= trade.entry_price * (1 + self.stop_loss / 100):
                    sl_triggered = True

            if self.take_profit is not None:
                if price <= trade.entry_price * (1 - self.take_profit / 100):
                    tp_triggered = True

        if tp_triggered or sl_triggered:
            self._add_log(
                f"{'Stop loss' if sl_triggered else 'Take profit'} for {self.contract.symbol} {self.timeframe}")

            order_side = "SELL" if trade.side == "long" else "BUY"
            order_status = self.client.place_order(self.contract, "MARKET", trade.quantity, order_side)

            if order_status is not None:
                self._add_log(f"Exit order on {self.contract.symbol} {self.timeframe} placed successfully")
                trade.status = "closed"
                self.ongoing_position = False


class TechnicalStrategy(Strategy):
    def __init__(self,
                 client,
                 contract: Contract,
                 exchange: str,
                 timeframe: str,
                 balance_pct: float,
                 take_profit: float,
                 stop_loss: float,
                 other_params: typing.Dict
                 ):
        super().__init__(client, contract, exchange, timeframe, balance_pct, take_profit, stop_loss, "Technical")

        self._ema_fast = other_params["ema_fast"]
        self._ema_slow = other_params["ema_slow"]
        self._ema_signal = other_params["ema_signal"]
        self._rsi_length = other_params["rsi_length"]

        print("Strategy activated for", contract.symbol)

    def _rsi(self):
        close_list = []
        for candle in self.candles:
            close_list.append(candle.close)

        closes = pd.Series(close_list)

        delta = closes.diff().dropna()

        up, down = delta.copy(), delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0

        avg_gain = up.ewm(com=(self._rsi_length - 1), min_periods=self._rsi_length).mean()
        avg_loss = down.abs().ewm(com=(self._rsi_length - 1), min_periods=self._rsi_length).mean()

        rs = avg_gain / avg_loss

        rsi = 100 - 100 / (1 + rs)

        rsi = rsi.round(2)

        return rsi.iloc[-2]

    def _mcad(self) -> typing.Tuple[float, float]:

        close_list = []
        for candle in self.candles:
            close_list.append(candle.close)

        closes = pd.Series(close_list)

        ema_fast = closes.ewm(span=self._ema_fast).mean()
        ema_slow = closes.ewm(span=self._ema_slow).mean()

        macd_line = ema_fast - ema_slow
        macd_signal = macd_line.ewm(span=self._ema_signal).mean()

        return macd_line.iloc[-2], macd_signal.iloc[-2]

    def _check_signal(self):
        macd_line, macd_signal = self._mcad()
        rsi = self._rsi()

        print("RSI", rsi)
        print("MACD line", macd_line)
        print("MACD signal", macd_signal)

        if rsi < 30 and macd_line > macd_signal:
            return 1

        elif rsi > 70 and macd_line < macd_signal:
            return -1
        else:
            return 0

    def check_trade(self, tick_type: str):
        if tick_type == "new_candle" and not self.ongoing_position:
            signal_result = self._check_signal()
            if signal_result in [-1, 1]:
                self._open_position(signal_result)


class BreakoutStrategy(Strategy):
    def __init__(self,
                 client,
                 contract: Contract,
                 exchange: str,
                 timeframe: str,
                 balance_pct: float,
                 take_profit: float,
                 stop_loss: float,
                 other_params: typing.Dict
                 ):
        super().__init__(client, contract, exchange, timeframe, balance_pct, take_profit, stop_loss, "Breakout")

        self._min_volume = other_params["min_volume"]

    def _check_signal(self) -> int:

        if self.candles[-1].close > self.candles[-2].high and self.candles[-1] > self._min_volume:
            return 1

        elif self.candles[-1].close < self.candles[-2].low and self.candles[-1] > self._min_volume:
            return -1

        else:
            return 0

        # ##  Day trading example
        # if self.candles[-2].high < self.candles[-3].high and self.candles[-2].low > self.candles[-3].low:
        #     if self.candles[-1].close > self.candles[-3].high:
        #         # Upside breakout
        #     elif self.candles[-1].close < self.candles[-3].low:
        #         # Downside breakout

    def check_trade(self, tick_type: str):
        if not self.ongoing_position:
            signal_result = self._check_signal()
            if signal_result in [-1, 1]:
                self._open_position(signal_result)
