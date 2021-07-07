#!/usr/bin/env python
# -*- coding: utf-8 -*-
from mongoengine import *
connect(db='dca_db')

class Symbol(DynamicDocument):
    name = StringField(required=True,min_length=4)

import config

from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException


def getLatestPrice(symbol):
    client = Client(config.API_KEY, config.API_SECRET)
    ticker = client.get_ticker(symbol=symbol)

    #print (ticker)

    last_price = float(ticker['lastPrice'])

    #price_change = ticker['priceChangePercent']
    #ask_price = float(ticker['askPrice'])
    #volume = ticker['volume']
    #open_time = ticker['closeTime']
    #date = datetime.fromtimestamp(open_time/1000)

    return float(last_price)

def getPriceFormat(price):
    price_format = int(str(price).split('.')[1].find('1')) + 1
    return price_format

def getAmountFormat(amount):
    amount_format = int(str(amount).split('.')[1].find('1')) + 1
    return amount_format

#syncing all allowed pairs! for the moment only USDT/BUSD pairs
def syncAllSymbols():
    Symbol.objects().delete()
    client = Client(config.API_KEY, config.API_SECRET)
    info = client.get_exchange_info()
    all_usd_symbols = []
    for symbol in info['symbols']:
        if symbol['quoteAsset'].find('USD') !=-1 and symbol['status'] =='TRADING':
            db_symbol = Symbol()
            db_symbol.symbol = symbol['symbol']
            for filter in symbol['filters']:
                if filter['filterType']=='PRICE_FILTER':
                    db_symbol.min_price = filter['minPrice']
                    db_symbol.price_format = getPriceFormat(db_symbol.min_price)
                    db_symbol.max_price = filter['maxPrice']
                    db_symbol.tick_size = filter['tickSize']
                if filter['filterType']=='LOT_SIZE':
                    db_symbol.min_amount = filter['minQty']
                    db_symbol.amount_format = getAmountFormat(db_symbol.min_amount)
                    db_symbol.max_amount = filter['maxQty']
            db_symbol.name = symbol['symbol']
            all_usd_symbols.append(db_symbol)
            db_symbol.save()
    return all_usd_symbols

def getSymbolInfo(pair):
    symbol = Symbol.objects(symbol=pair)
    if len(symbol) ==1:
        return {'status':'ok','message':symbol[0]}
    else:
        return {'status':'error','message':'symbol '+ pair +' not supported'}

def handleTradeFormat(price,amount,symbol):

    symbol_data = getSymbolInfo(symbol)

    if symbol_data['status']=='ok':
        symbol_data=symbol_data['message']
        if symbol_data.amount_format ==0:
            amount=str(round(amount))
        else:
            str_format = '{:.'+str(symbol_data.amount_format)+'f}'
            amount = str_format.format(amount)

        str_format = '{:.'+str(symbol_data.price_format)+'f}'
        price = str_format.format(price)

        return price,amount
    else:
        print (symbol_data)
        sys.exit()
