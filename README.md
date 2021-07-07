# binance_dca_bot
Experimental DCA Bot for Binance.com 

This is a very early and experimental version of a DCA Bot for Binance.com
You should use this software for testing purposes only! 
Before using it, you should check the code because the code will not be error free! 
Use it only on Test-Accounts with very small amount of money (e.g. <=50 USD)
The author is not liable for any errors or losses caused by the software.
The intention of this software is to show how one could program a DCA bot.
Please use the open orders / order history function auf binance to check whats going on and to cancel any deals.. 
#dca_bot_manager.py 

Install the needed packages like mongoengine, asyncio and python-binance
PUT your API KEY/SECRET into the config.py file!



1.) The function syncAllSymbols() fetches all supported pairs to the internal MongoDB! Only BUSD/USDT pairs are supported. Dont try to use any other pairs at the moment! This function will be called everytime you start the second script (deal_manager.py) 

2.) status = createBot(name='AAVE #testing',pair='AAVEBUSD',bot_template="TestingBot", activate_bot=True)
Create a bot. The name has to be unique! The idea is to have templates which can be edited. atm these templates are hardcoded. please check and change the settings to your liking! 

3.) As this software is for testing purposes only, it deleted all bots, deals, orders when u start it! You have to then manually delete buy / sell orders on the exchange!!! Dont forget to sell the coins ;-)


4.) after you created a bot / deal (with status "TO_BE_STARTED" you can then go to the next step to start the deal_manager.py

5.) the deal_manager.py manages the deals (haha)! It will check if there are any open deals with the status "WAITING".. These are running deals. For these deals it will check if any BUY or SELL orders gets filled. After the start there are two major functions running!

6.) The dealManager() function will start a new deal which means it submits the base order.. It then waits for the base order to get filled! If its not filled after 10 loops (waiting 3 seconds per loop) it will delete the order and submit a new one with the current price! 

7.) After the base order got filled it will calculate and submit the SELL_ORDER! After that all safety_orders are calculated and based on the parameter max_active_safety_orders the amount of safety orders will be placed on the exchange..

8.) The dealManager() does nothing more then submitting BASE_ORDER, SELL_ORDER and SAFETY_ORDERS... easy right?

9.) The monitorOrders() function connects via Websocket and should!!!! i repeat that... SHOULD receive every filled BUY or SELL_ORDER.. It then manages to cancel and create new BUY/SELL ORDERS or start the function were a new DEAL is started.. Then everything should start again.. 

10.) I dont know how stable the websocket is! during my testing it run for hours.. but i have not tested for days.. Thats why i implemented the checkCurrentDeals() function which will be started every time you start the deal_manager.py

11.) the helper.py has some function that are used by both scripts!

12.) USE THIS SOFTWARE ON YOUR OWN RISK! 




