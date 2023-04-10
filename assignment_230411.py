import dash
from dash import *
import plotly.graph_objects as go
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from binance.client import Client
import configparser
from binance.um_futures import UMFutures
from pprint import pprint
import time
import datetime
import hashlib
import json
import requests
import websocket
import threading
from binance.enums import HistoricalKlinesType
import math
import pandas as pd
import sys
import talib
from talib import stream
import numpy as np

import logging
# create logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)

formatter = logging.Formatter(u'%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

dashlog = logging.getLogger('werkzeug')
dashlog.setLevel(logging.ERROR)
#
isFutures = True
isTest = True
my_symbol = 'BTCUSDT'
api_key = 'e66daf8db0ffa187e96430c4f1af35abb111c6679a6e869887168d93c9ca8644'#config.get('BINANCE', 'TEST_API_KEY')
api_secret = 'd979a16822f586075d78bf8c23e86f836ffb24c61343b578e5e95ffccfbe0f5a' #config.get('BINANCE', 'TEST_SECRET_KEY')
hashedsig = hashlib.sha256(api_secret.encode('utf-8'))
client = Client(api_key, api_secret, testnet = isTest)
if isFutures:
    if isTest: 
        base_url = 'https://testnet.binancefuture.com'
        stream_url = 'wss://stream.binancefuture.com'
    else:
        base_url = 'https://fapi.binance.com'
        stream_url = 'wss://fstream.binance.com'
        
um_futures_client = UMFutures(key = api_key, secret = api_secret, base_url = base_url)
client.futures_change_leverage(symbol = my_symbol, leverage = 20, timestamp = time.time())

def accurate_precision(client,symbol): # price 
    if isFutures:
        symbols = client.futures_exchange_info()['symbols']
    else:
        symbols = client.get_exchange_info()['symbols']
    for s in symbols:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    precision = int(math.log10(float(f['tickSize'])))*-1
                
                    return precision
            
def accurate_quantity(client,symbol): # quantity
    if isFutures:
        symbols = client.futures_exchange_info()['symbols']
    else:
        symbols = client.get_exchange_info()['symbols']
    for s in symbols:
        if s['symbol'] == symbol:            
            if isFutures:
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':

                        return int(math.log10(float(f['stepSize'])))*-1
            else:
                roundnum = math.log10(float(s['filters'][2]['stepSize']))
                return int(roundnum) * -1     


def get_listenkey(api_key, hashedsig):
    global listenUrl
    headers = {'X-MBX-APIKEY': api_key}
    params = {'signature': hashedsig}
    if isTest:
        if isFutures: listenUrl = base_url+'/fapi/v1/listenKey'
        
    req = requests.post(listenUrl, headers = headers, params = params)
    listenKey = json.loads(req.text)['listenKey']
    return listenKey
    
def update_listenkey(api_key, hashedsig):
    now = datetime.datetime.now()
    nowDatetime = now.strftime('%Y-%m-%d %H:%M:%S')
    logging.info(nowDatetime)
    threading.Timer(3000.0, update_listenkey,args=(api_key, hashedsig,)).start()
    headers = {'X-MBX-APIKEY': api_key}
    params = {'signature': hashedsig}
            
    req = requests.put(listenUrl, headers = headers, params = params)
    logging.info(req)

def start_update_listenkey(api_key, hashedsig):
    threading.Timer(3000.0, update_listenkey,args=(api_key, hashedsig,)).start()

USER_URL = stream_url+'/stream?streams='+get_listenkey(api_key, hashedsig)
API_URL = stream_url+'/ws'  # To change endpoint URL for test account

count = 0
strategy_d = {}
order_d = {}
ma_d = {}
depth_updated = False
price = float(client.futures_symbol_ticker(symbol = my_symbol)['price'])

klines = um_futures_client.klines("BTCUSDT", "1m", **{"limit": 121})
klines_d = pd.to_numeric(pd.DataFrame(klines).set_index(0).loc[:,4]).T.to_dict()

# Kline1분봉, depth를 websocket으로 수신
params = {
"method": "SUBSCRIBE",
"params":[my_symbol.lower()+'@kline_1m', my_symbol.lower()+'@depth10@100ms'],
"id": 1}

#-------------------------------------------------------------------------------------------------------#
# fstream ws
def reconnect():
    ws.send(json.dumps(params))
def on_open(ws):
    ws.send(json.dumps(params))
    logging.info("fstream Opened")
def on_error(ws, error):
    nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')            
    logging.info(nowDatetime+" error: "+str(error))        
    logging.info('fstream WinError로 접속 연결 꺼짐 알림')
def on_message(ws, msg):
    global price, price_l, entry_price, unpnl, total_bal, total
    global strategy_d, buy_price, sell_price, df, klines_d, ma_d, depth_updated
    try:
        data = json.loads(msg)      
        if 'id' not in data:
            if data['e'] == 'kline' and depth_updated:
                price = float(data['k']['c'])
                klines_d[data['k']['t']] = price
                while len(klines_d) > 120:
                    klines_d.pop(list(klines_d.keys())[0])
                    
                for i in range(10,121):
                    ma_d[i] = talib.MA(np.array(list(klines_d.values())),i)
                    
                for i in range(20,121):
                    if ma_d[i-10][-1] > ma_d[i][-1] and ma_d[i-10][-2] <= ma_d[i][-2]: # golden cross: BUY
                        if strategy_d[i-10]['status'] == 0: #start
                            q = None 
                            send_order('BUY', i-10, price, 1, 'start', q)
                        elif strategy_d[i-10]['status'] == 'start' and strategy_d[i-10]['side'] == 'SELL':#end
                            q = abs(strategy_d[i-10]['pos']) 
                            if q != 0: 
                                send_order('BUY', i-10, price, 1, 'end', q)
                        if strategy_d[i-10]['pos'] == 0 and strategy_d[i-10]['status'] == 'start' and \
                        strategy_d[i-10]['side'] == 'SELL': # start 체결이 안되었을 시에는 취소
                            c = client.futures_cancel_order(symbol = my_symbol, orderId = strategy_d[i-10]['order_id'],
                                                           timestamp = int(time.time())*1000)
                            print(c)
                            strategy_d[i-10]['order_id'] = 0
                            strategy_d[i-10]['status'] = 0
                            logging.info(str(i-10)+' '+c['side']+' is cancelled')

                    elif ma_d[i-10][-1] < ma_d[i][-1] and ma_d[i-10][-2] >= ma_d[i][-2]:# dead cross: SELL
                        if strategy_d[i-10]['status'] == 0: #start
                            q = None 
                            send_order('SELL', i-10, price, -1, 'start', q)
                        elif strategy_d[i-10]['status'] == 'start' and strategy_d[i-10]['side'] == 'BUY':#end
                            q = abs(strategy_d[i-10]['pos']) 
                            if q != 0: 
                                send_order('SELL', i-10, price, -1, 'end', q)
                        if strategy_d[i-10]['pos'] == 0 and strategy_d[i-10]['status'] == 'start' and \
                        strategy_d[i-10]['side'] == 'BUY': # start 체결이 안되었을 시에는 취소
                            c = client.futures_cancel_order(symbol = my_symbol, orderId = strategy_d[i-10]['order_id'],
                                                           timestamp = int(time.time())*1000)
                            print(c)
                            strategy_d[i-10]['order_id'] = 0
                            strategy_d[i-10]['status'] = 0
                            logging.info(str(i-10)+' '+c['side']+' is cancelled')

                for i in range(10,111):
                    i_entry_price = strategy_d[i]['entry_price']
                    i_pos = strategy_d[i]['pos']
                    strategy_d[i]['unpnl'] = (price - i_entry_price)*i_pos
                    
            # 가장 빠른 체결예상 유리한 가격을 찾아야. 너무 멀면 그래프가 따라가며 cross나서 안됌
            if data['e'] == 'depthUpdate': # maker or taker? 그것이 문제로다
#                 if isTest: # 모의 트레이딩은 호가 간 간격이 넓으니 체결 안될 확률 높음
#                 buy_price = float(data['b'][1][0]) + 1/10**precision # 두번째 호가의 1틱 위에
#                 sell_price = float(data['a'][1][0]) - 1/10**precision
                buy_price = float(data['a'][0][0])
                sell_price = float(data['b'][0][0])
#                 else:
#                     buy_price = float(data['b'][0][0]) - 2/10**precision # 첫번째 호가의 2틱 아래에
#                     sell_price = float(data['a'][0][0]) + 2/10**precision
                    
#                 buy_price = (float(data['b'][0][0])+float(data['b'][1][0]))/2 
#                 sell_price = (float(data['a'][0][0])+float(data['a'][1][0]))/2
                depth_updated = True 
                                 
    except Exception as e:
        logger.exception(e)
    if count > 10:
        ws.close()
        sys.exit()

def on_close(ws, code, reason):
    nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
    logging.info(nowDatetime+"fstream closed: "+str(code)+' '+str(reason))
    
# userstream ws2
def on_open2(ws2):
    start_update_listenkey(api_key, hashedsig)
    logging.info("userstream Opened")
def on_error2(ws2, error):
    nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')            
    logging.info(nowDatetime+" error: "+str(error))        
    logging.info('userstream WinError로 접속 연결 꺼짐 알림')
def on_message2(ws2, msg):
    global w_bal, total_bal, pos, entry_price, unpnl
    try:
        data = json.loads(msg)['data']
        if data['e'] == 'ACCOUNT_UPDATE':
            B_l, P_l = data['a']['B'], data['a']['P']
            for B in B_l:
                if B['a'] == 'USDT': 
                    w_bal = float(B['wb'])
            for P in P_l:
                if P['s'] == my_symbol: 
                    unpnl = float(P['up'])
                    pos = float(P['pa'])
                    entry_price = float(P['ep'])
            total_bal = float(w_bal + unpnl)
            
        if data['e'] == 'ORDER_TRADE_UPDATE':
            if data['o']['X'] == 'FILLED':
                for j in range(3):
                    try:
                        i = order_d[data['o']['i']] # 전략 번호를 구함
                        break
                    except Exception as e:
                        logger.exception(e)
                        time.sleep(1)
                if strategy_d[i]['status'] == 'start' : # start라면
                    strategy_d[i]['side'] = data['o']['S'] # side 부여
                    
                    if data['o']['S'] == 'SELL': plus = -1
                    else: plus = 1
                    strategy_d[i]['pos'] = float(data['o']['q']) * plus # +- 곱해줘서 부호붙여줌        
                
                elif strategy_d[i]['status'] == 'end': # 해당전략 포지션 클리어로 end라면
                    strategy_d[i]['side'] = 'BOTH'
                    strategy_d[i]['pos'] = 0
                    strategy_d[i]['order_id'] = 0
                    strategy_d[i]['status']= 0
                    
                strategy_d[i]['pnl'] += float(data['o']['rp'])
                strategy_d[i]['total'] = strategy_d[i]['unpnl'] + strategy_d[i]['pnl']
                strategy_d[i]['entry_price'] = float(data['o']['ap'])
                
                logging.info('FILLED '+str(i)+' '+data['o']['S'])
                
    except Exception as e:
        logger.exception(e)
    if count > 10:
        ws2.close()
        sys.exit()
        
def on_close2(ws2, code, reason):
    nowDatetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
    logging.info(nowDatetime+" closed: "+str(code)+' '+str(reason))

#-------------------------------------------------------------------------------------------------------#
def send_order(side, i, price, plus, status, q = None):
    global strategy_d, order_d, count
    
    w_bal = float(client.futures_account()['totalWalletBalance'])
    one_turn = w_bal/1000 # balance를 기준으로 기본수량 계산
    if q == None: q = round(one_turn/(price*0.01), accuQ)
    if side == 'SELL': order_price = round(sell_price, precision)
    elif side == 'BUY': order_price = round(buy_price, precision)
        
    strategy_d[i]['status'] = status
    strategy_d[i]['side'] = side
    logging.info(str(i)+' '+side+' '+str(order_price)+' '+status)
    
    order = client.futures_create_order(    
        symbol = my_symbol,
        side = side,
        type = 'LIMIT',
        timeInForce = 'GTC',
        quantity = abs(q),
        price = order_price
    )
    count += 1
    strategy_d[i]['order_id'] = order['orderId']
    order_d[order['orderId']] = i

    
total_bal = float(client.futures_account()['totalMarginBalance']) # Portfolio Value(USDT)
w_bal = float(client.futures_account()['totalWalletBalance'])
precision = accurate_precision(client, my_symbol) 
accuQ = accurate_quantity(client, my_symbol)
unpnl = float(client.futures_account()['totalUnrealizedProfit'])

pos_info = client.futures_position_information(timestamp = int(time.time())*1000)
for p in pos_info:
    if p['symbol'] == my_symbol:
        pos = float(p['positionAmt'])
        entry_price = float(p['entryPrice'])
        
# set strategy_d for each strategy
for i in range(10,111):
    strategy_d[i] = {}
    strategy_d[i]['pnl'] = 0
    strategy_d[i]['side'] = 'BOTH'
    strategy_d[i]['entry_price'] = entry_price
    strategy_d[i]['pos'] = 0
    strategy_d[i]['order_id'] = 0 
    strategy_d[i]['status'] = 0 
    strategy_d[i]['unpnl'] = 0
#-------------------------------------------------------------------------------------------------------#
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
server = app.server
app.layout = html.Div([
    html.Div([
        html.Div([
            dcc.Graph(
                id='figure-1',
                figure={
                    'data': [
                        go.Indicator(
                            mode="number",
                            value=total_bal,
                        )
                    ],
                    'layout':
                        go.Layout(
                            title="Portfolio Value (USDT)"
                        )
                }
            )], style={'width': '30%', 'height': '300px',
                       'display': 'inline-block'}),
        html.Div([
            dcc.Graph(
                id='figure-2',
                figure={
                    'data': [
                        go.Indicator(
                            mode="number",
                            value=(price-entry_price)*pos,
                        )
                    ],
                    'layout':
                        go.Layout(
                            title="Current Position PnL (USDT)"
                        )
                }
            )],
            style={'width': '30%', 'height': '300px', 'display': 'inline-block'}),
        html.Div([
            dcc.Graph(
                id='figure-3',
                figure={
                    'data': [
                        go.Indicator(
                            mode = "number",
                            value = pos
                        )
                    ],
                    'layout':
                        go.Layout(
                            title="Current Position Amount"
                        )
                }
            )], style={'width': '30%', 'height': '300px', 'display': 'inline-block'}),
    ]),
    html.Div([
        html.Div([
            dcc.Graph(
                id='figure-4',
                figure={
                    'data': [
                        go.Bar(
                            x=list(strategy_d.keys()),
                            y=[strategy_d[i]['pnl']  for i in strategy_d],
                        )
                    ],
                    'layout':
                        go.Layout(
                            showlegend=False,
                            title="Strategy Cumulative PnL"
                        )
                }
            )], style={'width': '50%', 'display': 'inline-block'}),
        
        html.Div([
            dcc.Graph(
                id='live-update-graph',
                figure=dict(
                    data=[{'x': [0], 
                           'y': [total_bal],
                           'name': 'Total Balance',
                           'mode': 'lines',
                           'type': 'scatter'}],
                layout={'title':"Portfolio Value history"})
            )], style={'width': '50%', 'display': 'inline-block'}),
        
        dcc.Interval(
            id='1-second-interval',
            interval=1000,  # 1000 milliseconds
            n_intervals=0
        )
    ]),
])


@app.callback(Output('live-update-graph', 'extendData'),
              Input('1-second-interval', 'n_intervals'),
              [State('live-update-graph', 'figure')])
def update_graph_live(n, existing):
    data = {
        'time': [],
        'Total Balance': []
    }
    time = existing['data'][0]['x'][-1] + 1 
    y_new = total_bal
    return dict(x=[[time]], y=[[y_new]])

@app.callback(Output('figure-1', 'figure'),
              Output('figure-2', 'figure'),
              Output('figure-3', 'figure'),
              Output('figure-4', 'figure'),
#               Output('figure-5', 'extendData'),
              Input('1-second-interval', 'n_intervals'))
def update_layout(n):
    figure1 = {
        'data': [
            go.Indicator(
                mode="number",
                value=total_bal,
            )
        ],
        'layout':
            go.Layout(
                title="Portfolio Value (USDT)"
            )
    }
    figure2 = {
        'data': [
            go.Indicator(
                mode="number",
                value=(price-entry_price)*pos,
            )
        ],
        'layout':
            go.Layout(
                title="Current Position PnL (USDT)"
            )
    }
    figure3 = {
        'data': [
            go.Indicator(
                    mode = "number",
                    value = pos,
            )
        ],
        'layout':
            go.Layout(
                title="Current Position Amount"
            )
    }
    figure4 = {
        'data': [
            go.Bar(
                    x=list(strategy_d.keys()),
                    y=[strategy_d[i]['pnl']  for i in strategy_d]
            )
        ],
        'layout':
            go.Layout(
                showlegend=False,
                title="Strategy Cumulative PnL"
            )
    }

    return figure1, figure2, figure3, figure4


if __name__ == '__main__':

    ws = websocket.WebSocketApp(API_URL,
                            on_open = on_open,
                            on_message = on_message,
                            on_error = on_error,
                            on_close = on_close)
    thread = threading.Thread(target=ws.run_forever, daemon=True)
    thread.start()
    
    ws2 = websocket.WebSocketApp(USER_URL,
                            on_open = on_open2,
                            on_message = on_message2,
                            on_error = on_error2,
                            on_close = on_close2)
    thread2 = threading.Thread(target=ws2.run_forever, daemon=True)
    thread2.start()

    app.run_server(host='127.0.0.1', port='8050', debug=False)
    sys.exit() 
