from enum import Enum

class OptionType(Enum):
    CALL = 'CALL'
    PUT = 'PUT'


class VanillaIndOptions():
    def __init__(self, spot_price, strike_price, risk_factor_rate, time, dividend_yield, option_type: OptionType):
        self.S = spot_price
        self.K = strike_price
        self.r = risk_factor_rate
        self.T = time
        self.q = dividend_yield
        self.option_type = option_type

    def payout(self):
        payout = 0.0

        if self.option_type == OptionType.CALL:
            pass
        elif self.option_type == OptionType.PUT:
            pass

        return payout

    def put_call_parity(self):
        pass

    