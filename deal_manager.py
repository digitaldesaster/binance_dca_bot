#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import os,sys,json
import config
from time import sleep
from datetime import datetime

from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException

from binance import AsyncClient, BinanceSocketManager

from helper import getSymbolInfo,handleTradeFormat,syncAllSymbols,getLatestPrice

from mongoengine import *
connect(db='dca_db')

class Bot(DynamicDocument):
    name = StringField(required=True,min_length=4,unique=True)

class Deal(DynamicDocument):
    name = StringField(required=True,min_length=4)

class Symbol(DynamicDocument):
    name = StringField(required=True,min_length=4)

class Order(DynamicDocument):
    name = StringField(required=True,min_length=4)

def placeOrder(symbol,side,amount,price,type=ORDER_TYPE_LIMIT):

    print (symbol,price,amount)

    try:
        client = Client(config.API_KEY, config.API_SECRET)
        if type==ORDER_TYPE_LIMIT:
            result = client.create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_LIMIT,
            timeInForce='GTC',
            quantity=amount,
            price=price)
        elif type==ORDER_TYPE_MARKET:
            result = client.create_test_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=amount,
            )

        return {'status':'ok','message':result }

    except BinanceAPIException as e:
        # error handling goes here
        return {'status':'error','message': e}
    except BinanceOrderException as e:
        # error handling goes here
        return {'status':'error','message': e}

#
# def testBuyOrder():
#     return {'symbol': 'AAVEBUSD', 'orderId': 99009207, 'orderListId': -1, 'clientOrderId': '3TlOg1jQYu5PZ4S4paozfJ', 'price': '222.96000000', 'origQty': '0.04490000', 'executedQty': '0.04490000', 'cummulativeQuoteQty': '10.01090400', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'LIMIT', 'side': 'BUY', 'stopPrice': '0.00000000', 'icebergQty': '0.00000000', 'time': 1625065783081, 'updateTime': 1625065791741, 'isWorking': True, 'origQuoteOrderQty': '0.00000000'}

def clearDeal(deal):
    deal.status='TO_BE_STARTED'
    deal.active=False
    Order.objects(deal_id=deal.id).delete()
    deal.base_order_id = 0
    deal.start_time=0
    deal.check_base_order_filled=0
    deal.save()
    return deal


def startDeal(deal):
    if deal.status=='TO_BE_STARTED' and deal.active==False:

        base_order = Order()
        base_order.name = deal.pair + '_' + str(deal.id)
        base_order.pair = deal.pair
        base_order.price = getLatestPrice(deal.pair)
        base_order.amount = deal.dca_base_order / base_order.price
        base_order.price, base_order.amount =handleTradeFormat(base_order.price,base_order.amount,deal.pair)
        base_order.deal_id = deal.id
        base_order.bot_id = deal.bot_id
        base_order.type = 'BASE_ORDER'
        base_order.save()

        deal.base_order_id = base_order.id
        deal.save()



        result = placeOrder(deal.pair,SIDE_BUY,base_order.amount,base_order.price,deal.order_type)

        if result['status']=='ok':
            base_order.order_id = result['message']['orderId']
            base_order.status = 'BASE_ORDER_SUBMITTED'
            base_order.save()
            deal.status='BASE_ORDER_SUBMITTED'
            deal.start_time = result['message']['transactTime']
            deal.active=True

            deal.save()

            return {'status':'ok','message':'base_order_submitted'}

        else:
            deal.status='ERROR'
            deal.save()
            return {'status':'error','message':result['message']}

    else:
        return {'status':'error','message':'deal already started'}

def getOrderStatus(order_id,symbol):
    client = Client(config.API_KEY, config.API_SECRET)
    result = client.get_order(symbol=symbol,orderId=order_id)
    return result

def cancelOrder(order_id,symbol):
    client = Client(config.API_KEY, config.API_SECRET)
    try:
        result = client.cancel_order(
        symbol=symbol,
        orderId=order_id)
        if result['orderId']==order_id and result['symbol']==symbol and result['status']==ORDER_STATUS_CANCELED:
            return {'status':'ok','message':result}
        else:
            return {'status':'error','message':'could not cancel the order:' + str(order_id)}
    except BinanceAPIException as e:
        # error handling goes here
        return {'status':'error','message': e}
    except BinanceOrderException as e:
        # error handling goes here
        return {'status':'error','message': e}

def calculateSafetyOrders(deal):

    order_price = float(getOrderFromDB(deal.base_order_id).price)

    #order_price = float(deal.base_order_price)

    safety_order_nr = 1
    safety_order_volume = deal.dca_safety_order
    safety_order_deviation=deal.dca_deviation_to_open_safety_order
    safety_order_list = []

    while safety_order_nr <=deal.dca_max_safety_orders:
        if safety_order_nr ==1:
            safety_order_price = round(order_price - (order_price/100*safety_order_deviation),8)
        else:
            safety_order_deviation = round(deal.dca_deviation_to_open_safety_order + (safety_order_deviation * deal.dca_safety_order_step_scale),4)
            safety_order_price = round(order_price - (order_price/100*safety_order_deviation),8)
            safety_order_volume = round(safety_order_volume * deal.dca_safety_order_volume_scale,4)

        safety_order_amount = round(safety_order_volume/safety_order_price,8)

        safety_order_price,safety_order_amount = handleTradeFormat(safety_order_price,safety_order_amount,deal.pair)

        check_volume = round(float(safety_order_amount)*float(safety_order_price),2)

        safety_order = Order()
        safety_order.name = deal.pair + '_' + str(deal.id)
        safety_order.pair = deal.pair
        safety_order.price = safety_order_price
        safety_order.amount = safety_order_amount
        safety_order.deal_id = deal.id
        safety_order.bot_id = deal.bot_id
        safety_order.type = 'SAFETY_ORDER'
        safety_order.order_nr = safety_order_nr
        safety_order.volume = safety_order_volume
        safety_order.deviation = safety_order_deviation
        safety_order.check_volume = check_volume
        safety_order.status = "WAITING"
        safety_order.order_id=0
        safety_order.save()

        print (safety_order.to_json())

        safety_order_list.append(safety_order)

        safety_order_nr +=1
    return safety_order_list

def createDeal(bot_data):
    bot_data = json.loads(bot_data.to_json())
    bot_data.pop('_id')
    bot_data.pop('max_active_deals')
    deal = Deal.from_json(json.dumps(bot_data))
    deal.created = int(datetime.now().timestamp())

    return deal



def cancelAllSafetyOrders(deal):
    safety_orders = Order.objects(deal_id=deal.id,status="SAFETY_ORDER_PLACED",type="SAFETY_ORDER")
    safety_orders_canceled = 0
    for safety_order in safety_orders:
        #try:
        if safety_order.order_id !=0:
            result = cancelOrder(safety_order.order_id,deal.pair)
            print (result)
            if result['status']=='ok':
                safety_orders_canceled +=1
                safety_order.status='CANCELED'
                print ("SO: " + str(safety_order.order_nr) + " got canceled!")
                safety_order.save()
    return safety_orders_canceled


        #except:
        #    pass

def getOrderFromDB(order_id):
    return Order.objects(id=order_id)[0]


async def dealManager():
    client = Client(config.API_KEY, config.API_SECRET)
    try:
        while True:
            deals = Deal.objects(status__nin=['FINISHED','ERROR','WAITING'])
            if len(deals) > 0:
                deal = deals[0]
                print ('we have something ToDo')

                if deal.status=='TO_BE_STARTED':
                    #1 We have to submit or base_order
                    status = (startDeal(deal))
                    print (status)
                elif deal.status=='BASE_ORDER_SUBMITTED':
                    #2 check if base_order_filled
                    print ('check if base order filled')

                    base_order = getOrderFromDB(deal.base_order_id)

                    order = getOrderStatus(base_order.order_id,deal.pair)
                    if order['status']==ORDER_STATUS_FILLED:
                        base_order.price = order['price']
                        base_order.amount = order['executedQty']
                        base_order.volume = order['cummulativeQuoteQty']
                        base_order.time = order['time']
                        base_order.status = order['status']

                        base_order.save()

                        deal.total_volume = base_order.volume
                        target_price = round(float(base_order.price) + (float(base_order.price) / 100 * deal.dca_target_profit),8)

                        target_price, sell_amount =handleTradeFormat(target_price,float(base_order.amount),deal.pair)

                        sell_order = Order()
                        sell_order.name = deal.pair + '_' + str(deal.id)
                        sell_order.pair = deal.pair
                        sell_order.price = target_price
                        sell_order.amount = sell_amount
                        sell_order.deal_id = deal.id
                        sell_order.bot_id = deal.bot_id
                        sell_order.type = 'SELL_ORDER'
                        sell_order.save()

                        deal.avg_price = base_order.price
                        deal.base_order_price = base_order.price
                        deal.total_amount = float(base_order.amount)

                        deal.sell_order_id = sell_order.id
                        deal.save()


                        result = placeOrder(deal.pair,SIDE_SELL,sell_order.amount,sell_order.price,deal.order_type)
                        print (result)
                        if result['status']=='ok':
                            sell_order.order_id = result['message']['orderId']
                            sell_order.price = result['message']['price']
                            sell_order.amount = result['message']['origQty']
                            sell_order.status = "SELL_ORDER_PLACED"
                            sell_order.save()
                            deal.sell_price = sell_order.price

                        deal.status='BASE_ORDER_FILLED'
                        deal.save()



                    else:
                        print ('Waiting for Base Order ' + deal.pair + ' to be filled: ' + str(deal.base_order_id))
                        try:
                            deal.check_base_order_filled=deal.check_base_order_filled + 1
                            deal.save()
                            if deal.check_base_order_filled>=10:
                                print (cancelOrder(base_order.order_id,deal.pair))
                                deal = clearDeal(deal)
                                startDeal(deal)
                        except:
                            deal.check_base_order_filled=1
                            deal.save()

                elif deal.status =='BASE_ORDER_FILLED':

                    safety_orders = calculateSafetyOrders(deal)

                    for safety_order in safety_orders:
                        if safety_order.order_nr <= deal.max_active_safety_orders:
                            print ('Placing SO:' + str(safety_order.order_nr))

                            result = placeOrder(deal.pair,SIDE_BUY,safety_order.amount,safety_order.price,deal.order_type)
                            print (result)
                            if result['status']=='ok':
                                safety_order.order_id = result['message']['orderId']
                                safety_order.status = "SAFETY_ORDER_PLACED"
                                safety_order.save()
                                sleep(2)
                    deal.active_safety_orders=0
                    deal.status='WAITING'
                    deal.save()

            else:
                deals = Deal.objects(status="WAITING")

            await asyncio.sleep(3)

    except KeyboardInterrupt:
        print('interrupted!')


def handleNextSafetyOrder(deal,db_order):
    next_order_nr = db_order.order_nr + 1

    if next_order_nr <= deal.dca_max_safety_orders:
        safety_order = Order.objects(deal_id=deal.id,order_nr=next_order_nr)[0]
        if safety_order.status =="WAITING" and safety_order.order_id==0:

            result = placeOrder(deal.pair,SIDE_BUY,safety_order.amount,safety_order.price,deal.order_type)
            print (result)
            if result['status']=='ok':
                safety_order.order_id = result['message']['orderId']
                safety_order.status = "SAFETY_ORDER_PLACED"
                safety_order.save()

        else:
            print ("Safety Order Status: " + safety_order.status)
    else:
        print ("Max Safety Orders reached " + str(db_order.order_nr))


def handleOrder(order):
    orders = Order.objects(order_id=order.order_id)

    if len(orders)==1:
        db_order = orders[0]
        deal = Deal.objects(id=db_order.deal_id)[0]

        if order.status=='FILLED':
            if db_order.type == "SAFETY_ORDER" and order.side=="BUY":
                print ("Safety Order " + str(db_order.order_nr) +" got filled!")

                deal.active_safety_orders=db_order.order_nr
                deal.save()

                db_order.status="FILLED"
                db_order.save()
                handleNextSafetyOrder(deal,db_order)

                #Cancel Current Sell Order
                sell_order = Order.objects(deal_id=deal.id,type="SELL_ORDER")[0]
                result = cancelOrder(sell_order.order_id,deal.pair)
                print (result)
                if result['status']=="ok":
                    #recalculate total amount
                    deal.total_volume = float(deal.total_volume) + (float(order.amount)* float(order.price))
                    deal.total_amount = float(deal.total_amount) + float(order.amount)
                    deal.avg_price = round (deal.total_volume / deal.total_amount,8)
                    deal.save()

                    target_price = round(deal.avg_price + (deal.avg_price / 100 * deal.dca_target_profit),8)

                    target_price, sell_amount =handleTradeFormat(float(target_price),float(deal.total_amount),deal.pair)

                    sell_order.price = target_price
                    sell_order.amount = sell_amount

                    sell_order.save()

                    result = placeOrder(deal.pair,SIDE_SELL,sell_order.amount,sell_order.price,deal.order_type)
                    print (result)
                    if result['status']=='ok':
                        sell_order.order_id = result['message']['orderId']
                        sell_order.price = result['message']['price']
                        sell_order.amount = result['message']['origQty']
                        sell_order.status = "SELL_ORDER_PLACED"
                        sell_order.save()
                        deal.sell_price = sell_order.price

                    deal.sell_price = sell_order.price
                    deal.save()
                else:
                    deal.status="ERROR"
                    deal.save()
                    print ("Problem canceling Sell order!")

                #handle the next Safety Order!!!!
            elif db_order.type == "SELL_ORDER" and order.side=="SELL":

                print ("Sell Order @" + str(order.price) +" got filled!")
                print ("Safety Orders Canceled: " +str (cancelAllSafetyOrders(deal)))

                db_order.price = order.price
                db_order.amount = order.amount
                db_order.status = "FILLED"
                db_order.save()

                deal.profit = round ((float(order.price) * float(order.amount)) - float(deal.total_volume),2)
                deal.finish_time=order.time
                deal.sell_price = order.price
                deal.sell_volume = order.amount
                deal.status="FINISHED"
                deal.active=False
                deal.save()

                print ("Deal FINISHED!")
                print (deal.to_json())

                #SHOULD WE DELETE ALL ORDERS?!!! ***

                bot = Bot.objects(id=deal.bot_id)[0]

                #Restart the Deal
                if bot.active:
                    deals = Deal.objects(bot_id=bot.id,status__nin=['FINISHED','ERROR'])
                    if len(deals) < bot.max_active_deals:
                        print ("New Deal will be started!")
                        deal = createDeal(bot)
                        deal.bot_id = bot.id
                        deal.active = False
                        deal.status = 'TO_BE_STARTED'
                        deal.save()
                        print (deal.to_json())
                    else:
                        print ("Max active Deals is reached!")
                else:
                    print ("We dont start a new Deal! Bot is not active!")
            else:
                print (res['e'])


        elif order.status=='NEW':
            print (db_order.to_json())
            print ("New order placed!")


        elif order.status=='CANCELED':
            print (db_order.to_json())
            print ("order got canceled!")



async def monitorOrders():
    client = await AsyncClient.create(api_key=config.API_KEY, api_secret=config.API_SECRET)
    bm = BinanceSocketManager(client)
    # start any sockets here, i.e a trade socket
    ts = bm.user_socket()



    # then start receiving messages
    async with ts as tscm:
        while True:
            res = await tscm.recv()

            try:
                if res['e']=='executionReport':

                    order = Order()
                    order.pair = res['s']
                    order.side = res['S']
                    order.amount = res['q']
                    order.price = res['p']
                    order.status = res['X']
                    order.time = res['T']
                    order.order_id=res['i']

                    handleOrder(order)

            except:
                pass


    await client.close_connection()

def getOrderDetailsAPI(result):
    order = Order()
    order.pair = result['symbol']
    order.side = result['side']
    order.amount = result['executedQty']
    order.price = result['price']
    order.status = result['status']
    order.time = result['time']
    order.order_id=result['orderId']
    return order

def checkCurrentDeals():
    print ("Checking Current Deals")
    deals = Deal.objects(status="WAITING")
    for deal in deals:
        print ("Checking Sell Order for Deal: " + deal.pair)
        sell_order = Order.objects(deal_id=deal.id,type="SELL_ORDER")[0]
        result = getOrderStatus(sell_order.order_id,deal.pair)
        order = getOrderDetailsAPI(result)
        print (order.to_json())
        handleOrder(order)
        sleep(1)

    deals = Deal.objects(status="WAITING")
    for deal in deals:
        print ("Checking SafetyOrders for: " + deal.pair)
        safety_orders = Order.objects(deal_id=deal.id,type="SAFETY_ORDER")
        for safety_order in safety_orders:
            if safety_order.status=="SAFETY_ORDER_PLACED":
                result = getOrderStatus(safety_order.order_id,deal.pair)
                if result['status']=="FILLED":
                    order = getOrderDetailsAPI(result)
                    handleOrder(order)
                    sleep(1)

syncAllSymbols()
checkCurrentDeals()

loop = asyncio.get_event_loop()
try:
    asyncio.ensure_future(monitorOrders())
    asyncio.ensure_future(dealManager())
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    print("Closing Loop")
    loop.close()
