#!/usr/bin/env python
# -*- coding: utf-8 -*-
from mongoengine import *
connect(db='dca_db')
import json
from datetime import datetime
from helper import syncAllSymbols,getSymbolInfo

from binance.enums import *

#bot.start_condition (ONLY ASAP FOR THE MOMENT)

class Bot(DynamicDocument):
    name = StringField(required=True,min_length=4,unique=True)

class Deal(DynamicDocument):
    name = StringField(required=True,min_length=4)

class Order(DynamicDocument):
    name = StringField(required=True,min_length=4)

def templateExpressBot(bot):
    bot.dca_base_order=25
    bot.dca_safety_order=50
    bot.dca_max_safety_orders = 10
    bot.dca_safety_order_volume_scale = 1.5
    bot.dca_target_profit = 0.5
    bot.dca_deviation_to_open_safety_order = 0.5
    bot.dca_safety_order_step_scale = 1.15
    bot.max_active_deals = 1
    bot.max_active_safety_orders = 1
    bot.order_type = ORDER_TYPE_LIMIT
    bot.start_condition = 'ASAP'
    return bot

def templateStandardBot(bot):
    bot.dca_base_order=10
    bot.dca_safety_order=20
    bot.dca_max_safety_orders = 24
    bot.dca_safety_order_volume_scale = 1.05
    bot.dca_target_profit = 1.25
    bot.dca_deviation_to_open_safety_order = 2
    bot.dca_safety_order_step_scale = 1.02
    bot.max_active_deals = 1
    bot.max_active_safety_orders = 1
    bot.order_type = ORDER_TYPE_LIMIT
    bot.start_condition = 'ASAP'
    return bot

def templateTestingBot(bot):
    bot.dca_base_order=10
    bot.dca_safety_order=20
    bot.dca_max_safety_orders = 2
    bot.dca_safety_order_volume_scale = 1.05
    bot.dca_target_profit = 0.5
    bot.dca_deviation_to_open_safety_order = 0.5
    bot.dca_safety_order_step_scale = 1.02
    bot.max_active_deals = 1
    bot.max_active_safety_orders = 2
    bot.order_type = ORDER_TYPE_LIMIT
    bot.start_condition = 'ASAP'
    return bot


def createBot(name,pair,bot_template='StandardBot',activate_bot=False):

    if len(Bot.objects(name=name))!=0:
        return {'status':'error','message':'bot with that name already exists'}

    symbol_info= getSymbolInfo(pair)
    if symbol_info['status']=='error':
        return symbol_info


    bot = Bot()

    if bot_template=='ExpressBot':
        bot = templateExpressBot(bot)
    elif bot_template=="TestingBot":
        bot = templateTestingBot(bot)
    else:
        bot = templateStandardBot(bot)

    if bot.dca_base_order <= 10:
        bot.dca_base_order=10.02

    bot.created = int(datetime.now().timestamp())
    bot.name = name
    bot.pair = pair
    bot.active = False

    try:
        bot.save()

        if activate_bot:
            return (activateBot(name))

        return {'status':'ok','message':'bot successfully created!', 'data':bot.to_json()}
    except:
        return {'status':'error','message':'error saving bot'}

def deleteAllOrders():
    Order.objects().delete()

def deleteAllBots():
    Bot.objects().delete()

def deleteAllDeals():
    Deal.objects().delete()

def listAllBots(active=True):
    bots = Bot.objects(active=active)
    for bot in bots:
        print (bot.to_json())

def listAllOrders():
    orders = Order.objects()
    for order in orders:
        print (order.to_json())

def listAllDeals(active=True):
    deals = Deal.objects(active=active)
    profit = 0
    for deal in deals:
        print (deal.to_json())
        try:
            profit = profit + deal.profit
        except:
            pass
    print (profit)

def createDeal(bot_data):
    bot_data = json.loads(bot_data.to_json())
    bot_data.pop('_id')
    bot_data.pop('max_active_deals')
    deal = Deal.from_json(json.dumps(bot_data))
    deal.created = int(datetime.now().timestamp())

    return deal

def activateBot(name):
    bot = Bot.objects(name=name)

    if len(bot)==0:
        return {'status':'error','message':'bot with that name does not exist'}

    bot = bot[0]

    if bot.active ==True:
        return {'status':'error','message':'bot is already active'}

    bot.active = True
    bot.save()

    deals = Deal.objects(bot_id=bot.id,status__nin=['FINISHED','ERROR'])
    if len(deals) < bot.max_active_deals:
        deal = createDeal(bot)
        deal.bot_id = bot.id
        deal.active = False
        deal.status = 'TO_BE_STARTED'

        deal.save()

        return {'status':'ok','message':'bot successfully started!', 'data':deal.to_json()}
    else:
        return {'status':'error','message':'max_active_deals reached'}

syncAllSymbols()

deleteAllOrders()
deleteAllBots()
deleteAllDeals()

status = createBot(name='AAVE #testing',pair='AAVEBUSD',bot_template="TestingBot", activate_bot=True)

print (status)

#listAllDeals(active=False)

#listAllOrders()

#listAllBots(active=False)
