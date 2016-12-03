#!/usr/bin/python 

import json
import time
import yaml
import os
import sys
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
  sbdTarget = float(config['markets']['sbd_btc']['BTCUSD'])
  botAllocation = float(config['markets']['sbd_btc']['bot_allocation'])
  priceSafety= float(config['markets']['sbd_btc']['feed_tolorance'])
  profitThreshold = float(config['markets']['sbd_btc']['profit_threshold'])
  steemAccount = config['accounts']['steem']
  redFlags = 0
  botValue = 0.00
  firstPass = True

  tot_remaining = 0.00

while True:

  lastTarget = sbdTarget
  try:
    sbdTarget = 1/float(coinbase.get_spot_price(currency='USD')['amount'])
  except:
    print("Error getting price from Coinbase")
    time.sleep(5)
    continue

  #Make sure we don't get hosed if feed price slips too much
  if (abs(lastTarget - sbdTarget)/lastTarget/100) > priceSafety:
    print("Something off with the price feed, skipping this round\n")
    redFlags = redFlags + 1
    time.sleep(5)
    continue

  if redFlags >= 5:
     print("Something is really off! Shutting down.\n")
     sys.exit()

  lastTarget = sbdTarget

  bidRatio = sbdTarget - (sbdTarget * sbdBtcSpread)
  askRatio = sbdTarget + (sbdTarget * sbdBtcSpread)


  #Get availabe funds (don't wait for cancel just use available funds):
  try:
    btcBalAvail = bittrex.get_balance('BTC')['result']['Available']
  except:
    print("Error getting btcBalAvail")
    time.sleep(5)
    continue

  try:
    sbdBalAvail = bittrex.get_balance('SBD')['result']['Available']
  except:
    print("Error getting sbdBalAvail")
    time.sleep(5)
    continue
  
  if btcBalAvail is None:
    btcBalAvail = 0
  if sbdBalAvail is None:
    sbdBalAvail = 0

  botValue = (btcBalAvail * 1/sbdTarget) + sbdBalAvail

  btcBalAvail = float(btcBalAvail) * 0.99
  print("BTC: %f" % btcBalAvail)
  sbdBalAvail = float(sbdBalAvail) * 0.99


  minBtcOrder = minOrder * sbdTarget
  maxBtcOrder = maxOrder * sbdTarget 

  #Print simple dashbaoard
  _=os.system('clear')

  print("========================================================================================\n")
  print("RED FLAGS: %0.0f\nBalances:\nBTC: %f ($%0.2f) SBD: %f\n" % (redFlags,btcBalAvail, btcBalAvail * 1/sbdTarget, sbdBalAvail))
  print("Targets:\nBid: %f - Peg %f - Ask: %f\n" % (bidRatio, sbdTarget, askRatio))
  print("========================================================================================\n")

  ordersTotal = 0.00
  try:
    open_orders = bittrex.get_open_orders(market)['result']
  except:
    print("Error getting open_orders")
    time.sleep(5)
    continue

  for order in open_orders:
    remaining = float(order['QuantityRemaining'])
    ordType   = order['OrderType']
    ratio     = float(order['Limit'])
    ordersTotal = ordersTotal + remaining

  if (btcBalAvail >= minBtcOrder) and ((ordersTotal + minBtcOrder) <= botAllocation):
    allocRemaining = botAllocation - ordersTotal

    if btcBalAvail > (allocRemaining * bidRatio):
      btcAmount = (allocRemaining * bidRatio)
    else:
      btcAmount = btcBalAvail

    #Place bid at target
    if btcAmount >= minBtcOrder:
      print("\n>>>>>>> Buying %f SBD @ %0.6f SBD/BTC" % (btcAmount / bidRatio, bidRatio))
      try:
        result = bittrex.buy_limit(market, (btcAmount / bidRatio), bidRatio)
        ordersTotal = ordersTotal + (btcAmount / bidRatio)
        btcBalAvail = btcBalAvail - btcAmount
      except:
        print("Error placing buy order")
        time.sleep(5)
        continue
  if (sbdBalAvail >= minOrder) and ((ordersTotal + minOrder) <= botAllocation):
    allocRemaining = botAllocation - ordersTotal
   
    if sbdBalAvail > allocRemaining:
      sbdAmount = allocRemaining
    else:
      sbdAmount = sbdBalAvail
    #Place Ask at target
    if sbdAmount >= minOrder:
      print("\n<<<<<<< Selling %f SBD @ %0.6f SBD/BTC" % (sbdAmount, askRatio))
      try:
        result = bittrex.sell_limit(market, sbdAmount, askRatio)
        ordersTotal = ordersTotal + sbdBalAvail
        sbdBalAvail = sbdBalAvail - sbdAmount
      except:
        print("Error placing sell order")
        time.sleep(5)
        continue

  print("Open Orders:\n")
  for order in open_orders:
    ordUid  = order['OrderUuid']
    remaining = float(order['QuantityRemaining'])
    ordType   = order['OrderType']
    opened    = order['Opened'] 
    ratio     = float(order['Limit'])
    #Cancel out of bound orders - async if possible:
    if ordType == 'LIMIT_BUY':
      if ((ratio * 1.001) < bidRatio) or (ratio > sbdTarget):
        print("%s %s %s %s [CANCELING BUY]" %  (ordUid, remaining, ordType, ratio))
        result = bittrex.cancel(ordUid)
        ordersTotal = ordersTotal - remaining
        btcBalAvail = btcBalAvail + (remaining * ratio)
      else:
        print("%s %s %s %s" %  (ordUid, remaining, ordType, ratio))

  sbd_remaining = 0.00
  for order in open_orders:
    ordUid  = order['OrderUuid']
    remaining = float(order['QuantityRemaining'])
    tot_remaining = tot_remaining + remaining
    ordType   = order['OrderType']
    opened    = order['Opened']
    ratio     = float(order['Limit'])
    #Cancel out of bound orders - async if possible:
    if ordType == 'LIMIT_SELL':
      sbd_remaining = sbd_remaining + remaining
      if (ratio > (askRatio * 1.001)) or (ratio < sbdTarget):
        print("%s %s %s %s [CANCELING SELL]" %  (ordUid, remaining, ordType, ratio))
        result = bittrex.cancel(ordUid)
        ordersTotal = ordersTotal - remaining
        sbdBalAvail = sbdBalAvail + remaining
      else:
        print("%s %s %s %s" %  (ordUid, remaining, ordType, ratio))

  botValue = ordersTotal + sbdBalAvail + (btcBalAvail / bidRatio)
  print("\nBot value: $%0.2f of $%0.2f allocated\n\n" % (botValue, botAllocation))

  try:
    trades = bittrex.get_market_history(market, '10')['result']
    counter = 1
    for trade in trades:
      print("%7s %-27s %-10s %0.8f %5.4f" % (trade['Id'], trade['TimeStamp'][:16], trade['OrderType'], float(trade['Price']), float(trade['Quantity'])))
      counter = counter + 1
      if counter > 10:
        break
  except:
    print("Error getting history")
    
 
  if botValue > botAllocation + profitThreshold:
   if (sbdBalAvail + sbd_remaining) > botAllocation:
    for order in open_orders:
      ordUid  = order['OrderUuid']
      ordType   = order['OrderType']
      if ordType == 'LIMIT_SELL': 
        print("%s %s %s %s [SBD OVERLOAD]" %  (ordUid, remaining, ordType, ratio))
        result = bittrex.cancel(ordUid)
        time.sleep(5)
    print("Witing for orders to cancel...")
    time.sleep(20)  
    print("\n Sending %f SBD to %s\n" % ((sbdBalAvail + sbd_remaining) - botAllocation), steemAccount)
    result = bittrex.withdraw('SBD', (sbdBalAvail + sbd_remaining) - botAllocation, steemAccount)
   else:
     if sbdBalAvail >= profitThreshold :
       if botValue - botAllocation > sbdBalAvail:
         print("\n Sending %f SBD to %s\n" % (sbdBalAvail, steemAccount))
         result = bittrex.withdraw('SBD', sbdBalAvail, steemAccount)
       else:
         print("\n Sending %f SBD to %s\n" % ((botValue - botAllocation), steemAccount))
         result = bittrex.withdraw('SBD', (botValue - botAllocation), steemAccount)


  firstPass = False

  time.sleep(5)
  
  
