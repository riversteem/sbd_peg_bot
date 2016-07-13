__author__ = 'riverhead'

import json
import time
import yaml
import os
from bittrex.bittrex import Bittrex
from coinbase.wallet.client import Client


with open("config.yml", "r") as config_file:
  config = yaml.load(config_file)
  keys = config['keys']
  bittrex = Bittrex(keys['bittrex']['Pub'],  keys['bittrex']['Sec'])
  coinbase = Client(keys['coinbase']['Pub'], keys['coinbase']['Sec'])
  sbdBtcSpread = float(config['markets']['sbd_btc']['spread'])/100
  minOrder  = float(config['markets']['sbd_btc']['min_order_size'])
  maxOrder  = float(config['markets']['sbd_btc']['max_order_size'])
  market    = config['markets']['sbd_btc']['market']

while True:

  sbdTarget = 1/float(coinbase.get_spot_price(currency='USD')['amount'])

  bidRatio = sbdTarget - (sbdTarget * sbdBtcSpread)
  askRatio = sbdTarget + (sbdTarget * sbdBtcSpread)


  #Get availabe funds (don't wait for cancel just use available funds):
  btcBalAvail = bittrex.get_balance('BTC')['result']['Available']
  sbdBalAvail = bittrex.get_balance('SBD')['result']['Available']

  
  if btcBalAvail is None:
    btcBalAvail = 0
  if sbdBalAvail is None:
    sbdBalAvail = 0

  btcBalAvail = float(btcBalAvail) * 0.95
  sbdBalAvail = float(sbdBalAvail) * 0.95

  minBtcOrder = minOrder * sbdTarget
  maxBtcOrder = maxOrder * sbdTarget 

  #Print simple dashbaoard
  _=os.system('clear')

  print("========================================================================================\n")
  print("Balances:\nBTC: %f ($%0.2f) SBD: %f\n" % (btcBalAvail, btcBalAvail * 1/sbdTarget, sbdBalAvail))
  print("Targets:\nBid: %f @ %f - Peg %f - Ask: %f @ %f\n" % (btcBalAvail, bidRatio, sbdTarget, sbdBalAvail, askRatio))
  print("========================================================================================\n")

  if btcBalAvail >= minBtcOrder:
    #Place bid at target
    print("\n>>>>>>> Buying %f SBD @ %0.6f SBD/BTC\n" % (btcBalAvail * 1/bidRatio, bidRatio))
    result = bittrex.buy_limit(market, (btcBalAvail * 1/bidRatio), bidRatio)

  if sbdBalAvail >= minOrder:
    #Place Ask at target
    print("\n<<<<<<< Selling %f SBD @ %0.6f SBD/BTC\n" % (sbdBalAvail, askRatio))
    result = bittrex.sell_limit(market, sbdBalAvail, bidRatio)


  print("Open Orders:")
  open_orders = bittrex.get_open_orders(market)['result']
  for order in open_orders:
    ordUid  = order['OrderUuid']
    remaining = order['QuantityRemaining']
    ordType   = order['OrderType']
    opened    = order['Opened'] 
    ratio     = order['Limit']
    #Cancel out of bound orders - async if possible:
    if ordType == 'LIMIT_BUY':
      if ((ratio * 1.001) < bidRatio) or (ratio > sbdTarget):
        print("%s %s %s %s [CANCELING BUY]" %  (ordUid, remaining, ordType, ratio))
        result = bittrex.cancel(ordUid)
      else:
        print("%s %s %s %s" %  (ordUid, remaining, ordType, ratio))
    else:
      if (ratio > (askRatio * 1.001)) or (ratio < sbdTarget):
        print("%s %s %s %s [CANCELING SELL]" %  (ordUid, remaining, ordType, ratio))
        result = bittrex.cancel(ordUid)
      else:
        print("%s %s %s %s" %  (ordUid, remaining, ordType, ratio))
      
  time.sleep(10)
  
  
