#!/usr/bin/env python
__author__ = 'chase.ufkes'

import time
import json
import gc
import ccxt
from slackclient import SlackClient
import logging

with open("config/botConfig.json", "r") as fin:
    config = json.load(fin)

logging.basicConfig(level=logging.INFO, filename="hitbtc.log", filemode="a+",
                        format="%(asctime)-15s %(levelname)-8s %(message)s")

apiKey = str(config['apiKey'])
apiSecret = str(config['apiSecret'])
trade = config['trade']
currency = config['currency']
sellValuePercent = config.get('sellValuePercent', 4)
buyValuePercent = config.get('buyValuePercent', 4)
volumePercent = config.get('buyVolumePercent', 4)
buyDifference = config.get('buyDifference', 0)
extCoinBalance = config.get('extCoinBalance', 0)
checkInterval = config.get('checkInterval', 30)
initialSellPrice = config.get('initialSellPrice', 0)
tradeAmount = config.get('tradeAmount', 0)
slackChannel = config['slackChannel']
slackToken = config['slackToken']

# global / constants
token = currency + "/" + trade
volumePercent = volumePercent * .01
sellValuePercent = sellValuePercent * .01
buyValuePercent = buyValuePercent * .01
buyDifference = buyDifference * .01
exchange = ccxt.hitbtc2({
    "apiKey": apiKey,
    "secret": apiSecret,
    "enableRateLimit": True,
})

def get_token_balance():
    balance = exchange.fetch_balance()
    currencies = list(balance.keys())
    for c in currencies:
        if currency in c:
            return (balance[c]['free'])

def determine_sell_amount(balance):
    return round(balance * volumePercent,-3)

def determine_buy_amount(balance):
    amount = round(balance * volumePercent * (1 / (1 - volumePercent) * 1 + buyDifference), -3)
    return amount

def get_current_ticker():
    data = exchange.fetch_ticker(token)
    return data['last']

def determine_buy_price(currentTicker):
    price = currentTicker - (currentTicker * buyValuePercent)
    return price

def determine_sell_price(currentTicker):
    price = currentTicker + (currentTicker * sellValuePercent)
    return price

def isWithinChecktime(timeToCheckInMillis, baseTimeInMillis, intervalInSec):
    return abs(timeToCheckInMillis - baseTimeInMillis) <= (intervalInSec * 1000)


def get_last_order_price(checkTime, history, trades):
    for c in history:
        if ((isWithinChecktime((c['timestamp']), checkTime, checkInterval))):
            for t in trades:
                if c['info']['id'] == t['info']['orderId']:
                    return (t['info']['price'])

def get_last_order_amount(checkTime, history, trades):
    for c in history:
        if ((isWithinChecktime((c['timestamp']), checkTime, checkInterval))):
            for t in trades:
                if c['info']['id'] == t['info']['orderId']:
                    return (t['info']['quantity'])

def get_last_order_type(checkTime, history, trades):
    for c in history:
        if ((isWithinChecktime((c['timestamp']), checkTime, checkInterval))):
            for t in trades:
                if c['info']['id'] == t['info']['orderId']:
                    return (t['info']['side'])

def post_slack(type, amount, price):
    logging.info("Attempting to send message...")
    sc = SlackClient(slackToken)
    text = type + " - " + currency + " Amount: " + amount + " Price:  " + price
    sc.api_call(
        "chat.postMessage",
        channel=slackChannel,
        text=text
    )

cycle = 0
while True:
    orders = exchange.fetch_open_orders(token)
    sellOrder = "False"
    buyOrder = "False"

    for order in orders:
        if ('sell' in order['side']):
            sellOrder = "True"
        elif ('buy' in order['side']):
            buyOrder = "True"

    # orders are set, move along
    if (sellOrder == "True") and (buyOrder == "True"):
        logging.info("Order pair still set: ")
        for order in orders:
            logging.info(order)

    # rebase
    elif ((sellOrder == "False") and (buyOrder == "True")) or \
                (buyOrder == "False") and (sellOrder == "True"):
        try:
            for order in orders:
                exchange.cancel_order(order['id'])

            balance = get_token_balance()
            buyAmount = determine_buy_amount(balance)
            sellAmount = determine_sell_amount(balance)

            history = exchange.fetch_closed_orders(token)
            trades = exchange.fetch_my_trades()
            checkTime = time.time() * 1000
            try:
                logging.info("Trying to send message...")
                lastPrice = get_last_order_price(checkTime, history, trades)
                logging.info(lastPrice)
                lastAmount = get_last_order_amount(checkTime, history, trades)
                logging.info(lastAmount)
                orderType = get_last_order_type(checkTime, history, trades)
                logging.info(orderType)

                post_slack(orderType, lastAmount, lastPrice)
            except:
                logging.info("Message send failed...")
            buyPrice = determine_buy_price(float(lastPrice))
            sellPrice = determine_sell_price(float(lastPrice))
            logging.info("Placing buy order for: " + currency + " amount: " + str(buyAmount) + " price: " + str(buyPrice))
            logging.info("Placing sell order for: " + currency + " amount: " + str(sellAmount) + " price: " + str(sellPrice))
            logging.info(exchange.create_order(token, 'limit', 'sell', sellAmount, sellPrice))
            logging.info(exchange.create_order(token, 'limit', 'buy', buyAmount, buyPrice))
        except:
            logging.info("Shit went sideways")

    # fresh order stack
    if orders == []:
        try:
            logging.info("place new order stack")
            balance = get_token_balance()
            buyAmount = determine_buy_amount(balance)
            sellAmount = determine_sell_amount(balance)
            if buyAmount < 1000:
                buyAmount = 1000
            if sellAmount < 1000:
                sellAmount = 1000

            currentTicker = get_current_ticker()
            buyPrice = determine_buy_price(currentTicker)
            sellPrice = determine_sell_price(currentTicker)

            logging.info("Placing buy order for: " + currency + " amount: " + str(buyAmount) + " price: " + str(buyPrice))
            logging.info("Placing sell order for: " + currency + " amount: " + str(sellAmount) + " price: " + str(sellPrice))
            loggin.info(exchange.create_order(token, 'limit', 'sell', sellAmount, sellPrice))
            logging.info(exchange.create_order(token, 'limit', 'buy', buyAmount, buyPrice))
        except:
            logging.info("Either API error or you're out of funds bra")

    if cycle == 100:
            logging.info("Garbage collection")
            gc.collect()
            count = 0
    logging.info("Waiting " + str(checkInterval) + " for next cycle...")
    time.sleep(int(checkInterval))