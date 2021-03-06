import logging
from typing import Tuple

from qrypto.data.datasets import OHLCDataset
from qrypto.data.indicators import BasicIndicator
from qrypto.strategy.base import BaseStrategy


log = logging.getLogger(__name__)


class MFIMomentumStrategy(BaseStrategy):

    def __init__(self,
                 exchange,
                 base_currency: str,
                 unit: float,
                 quote_currency: str = 'USD',
                 ohlc_interval: int = 5,
                 stop_loss: float = 0.01,
                 sleep_duration: int = 30,
                 macd: Tuple[int, int, int] = (10, 26, 9),
                 macd_slope_min: float = 0.0,
                 mfi: Tuple[int, int, int] = (14, 80, 20)):
        super(MFIMomentumStrategy, self).__init__(base_currency, exchange, unit, quote_currency, sleep_duration)

        indicators = [BasicIndicator('macd'), BasicIndicator('mfi', {'timeperiod': mfi[0]})]
        self.data = OHLCDataset(indicators)

        self.ohlc_interval = ohlc_interval
        self.stop_loss = lambda p: p * (1. - stop_loss)
        self.macd_slope_min = macd_slope_min
        _, self.mfi_top, self.mfi_bottom = mfi

    def update(self) -> None:
        new_data = self.exchange.get_ohlc(self.base_currency, self.quote_currency,
                                          interval=self.ohlc_interval, since_last=True)
        self.data.update(new_data)
        log.info('%.2f; %.2f; %.2f', self.data.last_price, self.data.mfi[-1], self.data.macd_slope())

    def should_open(self) -> bool:
        return len(self.data.mfi) >= 2 \
               and self.data.mfi[-2] < self.mfi_bottom \
               and self.data.mfi[-1] >= self.mfi_bottom \
               and self.data.macd_slope() > self.macd_slope_min

    def should_close(self) -> bool:
        return (self.data.mfi[-2] > self.mfi_top \
               and self.data.mfi[-1] <= self.mfi_top) \
               or self.data.last_price < self.stop_loss(self.position['open'])
