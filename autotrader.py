import asyncio
import numpy as np
import pandas as pd
from typing import List, Tuple
import itertools
import time
from ready_trader_one import BaseAutoTrader, Instrument, Lifespan, Side
import math

#chall 2

class AutoTrader(BaseAutoTrader):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        """Initialise a new instance of the AutoTrader class."""
        super(AutoTrader, self).__init__(loop)

        self.order_ids: Iterator[int] = itertools.count(1)
        self.ask_id = self.ask_price = self.bid_id = self.bid_price = self.position = 0
        print('setting up params')
        self.s0 = 100 #initial price
        self.T = 1 #time
        self.dt = 0.0001 #time step
        self.sigma = 1 #volatility
        self.q0 = 0 
        self.gamma = 1 #risk aversion
        self.k = 1.5 
        self.A = 10 #order probability
        self.time = 0
        self.volume = 10
        self.buyvol = 30
        self.sellvol = 30
        self.shape = -0.005
        self.ordmaxb = 0
        self.ordmaxs = 0
        self.remaining_volume = 0

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:
        """Called when the exchange detects an error.

        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """
        self.logger.warning("error with order %d: %s", client_order_id, error_message.decode())
        self.on_order_status_message(client_order_id, 0, 0, 0)

    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically to report the status of an order book.

        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """
        #Pricing component - based on optimal HF MM paper by tfushimi et al. 2018
        
        #Inventory Strategy
        if instrument == Instrument.FUTURE:
            for step, s in enumerate(ask_prices):
                reservation_price = ask_prices[0] - self.position * self.gamma * self.sigma**2 * (self.T-step*self.dt)
                spread = self.gamma * self.sigma**2 * (self.T-step*self.dt) + (2/self.gamma) * np.log(1 + (self.gamma/self.k))
                spread /= 2

            if reservation_price >= ask_prices[0]:
                ask_spread = spread + (reservation_price - ask_prices[0])
                bid_spread = spread - (reservation_price - ask_prices[0])
            else:
                ask_spread = spread - (ask_prices[0] - reservation_price)
                bid_spread = spread + (ask_prices[0] - reservation_price)
            

            best_ask  = ask_prices[0] + ask_spread if ask_prices[0] != 0 else 0
            best_bid  = ask_prices[0] - bid_spread if bid_prices[0] != 0 else 0

            best_ask = int((math.ceil(best_ask/100)) * 100)
            best_bid = int((math.floor(best_bid/100)) * 100)

            #print(best_ask, 'best ask')
            #print(best_bid, 'best bid')

            if self.bid_id != 0 and best_bid not in (self.bid_price, 0):
                self.send_cancel_order(self.bid_id)
                self.bid_id = 0
                
            if self.ask_id != 0 and best_ask not in (self.ask_price, 0): #look more closely of the not in for optimisation
                self.send_cancel_order(self.ask_id)
                self.ask_id = 0


            if self.bid_id == 0 and best_bid != 0 and self.position + self.remaining_volume < 70 and self.buyvol > 0:
                self.bid_id = next(self.order_ids)
                self.bid_price = best_bid
                print('buyvol& id', self.bid_id, self.buyvol)
                self.send_insert_order(self.bid_id, Side.BUY, int(best_bid), self.buyvol, Lifespan.GOOD_FOR_DAY)
                self.time = time.time()

            if self.ask_id == 0 and best_ask != 0 and self.position - self.remaining_volume > -70 and self.sellvol > 0:
                self.ask_id = next(self.order_ids)
                self.ask_price = best_ask
                print('sellvol', self.sellvol)
                self.send_insert_order(self.ask_id, Side.SELL, int(best_ask), self.sellvol, Lifespan.GOOD_FOR_DAY)
                self.time = time.time()


    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int, fees: int) -> None:
        """Called when the status of one of your orders changes.

        The fill_volume is the number of lots already traded, remaining_volume
        is the number of lots yet to be traded and fees is the total fees for
        this order. Remember that you pay fees for being a market taker, but
        you receive fees for being a market maker, so fees can be negative.

        If an order is cancelled its remaining volume will be zero.
        """
        self.remaining_volume = remaining_volume
        print('remainingvol', self.remaining_volume)
        if remaining_volume == 0 or int(time.time()-self.time) > 3:
            if client_order_id == self.bid_id:
                self.bid_id = 0
            elif client_order_id == self.ask_id:
                self.ask_id = 0

    def on_position_change_message(self, future_position: int, etf_position: int) -> None:
        """Called when your position changes.

        Since every trade in the ETF is automatically hedged in the future,
        future_position and etf_position will always be the inverse of each
        other (i.e. future_position == -1 * etf_position).
        """
        self.position = etf_position

    def on_trade_ticks_message(self, instrument: int, trade_ticks: List[Tuple[int, int]]) -> None:
        """Called periodically to report trading activity on the market.

        Each trade tick is a pair containing a price and the number of lots
        traded at that price since the last trade ticks message.
        """
        pass
        #print('trade ticks', trade_ticks)
