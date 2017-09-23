import numpy as np

from qrypto.data.datasets import OHLCDataset


EXCLUDE_FIELDS = [
    'open',
    'high',
    'low',
    'close',
    'volume',
    'quoteVolume',
    'avg'
]


class QLearnDataset(OHLCDataset):
    actions = ['long', 'short']

    def __init__(self, *args, fee: float = 0.002, **kwargs):
        self.fee = fee

        self._normalized = False
        self.train_counter = None
        self.open_price = None
        self.position = 'long'

        super(QLearnDataset, self).__init__(*args, **kwargs)

    def start_training(self, start_step: int = 0):
        self.train_counter = start_step
        self._init_positions()
        self._init_orders()

        while np.any(np.isnan(self.state())):
            self.next()

        return self.train_counter

    def next(self):
        self.train_counter += 1
        return self.state()

    def stop_training(self):
        self.train_counter = None

    def normalize(self):
        self._normalized = True
        self.mean = self.all.mean()
        self.std = self.all.std()

    @property
    def all(self):
        result = super(QLearnDataset, self).all
        result.drop(EXCLUDE_FIELDS, axis=1, inplace=True)
        return result

    @property
    def last_idx(self):
        return self.train_counter if self.train_counter is not None else -1

    @property
    def last_row(self):
        return self.all.iloc[self.last_idx]

    @property
    def last(self):
        return self._data.iloc[self.last_idx]['close']

    @property
    def time(self):
        return self._data.iloc[self.last_idx].name

    @property
    def n_state_factors(self) -> int:
        return len(self.last_row) + 1

    @property
    def n_actions(self):
        return len(self.actions)

    def state(self):
        result = self.last_row

        if self._normalized:
            result = result - self.mean
            result = result / self.std

        result = np.append(result.values, 1. if self.position == 'long' else -1.)
        return result

    @property
    def period_return(self):
        return (self.close[self.last_idx] / self.close[self.last_idx - 1]) - 1.

    @property
    def cumulative_return(self):
        if self.open_price:
            return (self.last / self.open_price) - 1.
        else:
            return 0.

    def step(self, idx: int):
        action = self.actions[idx]
        self.add_position(action, {'price': self.last})
        switch = self.position != action
        self.position = action

        self.next()

        if self.position == 'long':
            reward = self.period_return
        else:
            reward = self.period_return * -1.

        if switch:
            reward -= self.fee

        return reward

    def step_val(self, idx: int, confidence: float, threshold = (0.5, 0.5)):
        open_thresh, hold_thresh = threshold
        action = self.actions[idx]

        if self.open_price is None:
            if action == 'long' and confidence > open_thresh:
                self.open_price = self.last
                self.add_order('buy', {'price': self.last})
                cum_return = -self.fee
            else:
                cum_return = None
        else:
            if action == 'short' or confidence < hold_thresh:
                cum_return = self.cumulative_return - self.fee
                self.add_order('sell', {'price': self.last})
                self.open_price = None
            else:
                cum_return = None

        reward = self.step(idx)

        return reward, cum_return