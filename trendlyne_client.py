import requests
import httpx
import asyncio

class TrendlyneClient:
    def __init__(self):
        self.base_url = "https://smartoptions.trendlyne.com/phoenix/api"
        self.async_client = httpx.AsyncClient(timeout=10.0)

    async def get_stock_id_for_symbol(self, symbol):
        # Strip common prefixes
        s = symbol.upper()
        if '|' in s:
            s = s.split('|')[-1]
        
        # Map indices to Trendlyne ticker codes
        if "NIFTY 50" in s or s == "NIFTY":
            s = "NIFTY"
        elif "NIFTY BANK" in s or s == "BANKNIFTY":
            s = "BANKNIFTY"
            
        search_url = f"{self.base_url}/search-contract-stock/"
        params = {'query': s.lower()}
        try:
            response = requests.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data and 'body' in data and 'data' in data['body'] and len(data['body']['data']) > 0:
                for item in data['body']['data']:
                    target_code = item.get('stock_code', '').upper()
                    if target_code == s:
                        return item['stock_id']
                return data['body']['data'][0]['stock_id']
            return None
        except Exception as e:
            print(f"[Trendlyne] Error fetching stock ID for {symbol}: {e}")
            return None

    async def get_expiry_dates(self, stock_id):
        expiry_url = f"{self.base_url}/fno/get-expiry-dates/?mtype=options&stock_id={stock_id}"
        try:
            response = await self.async_client.get(expiry_url)
            response.raise_for_status()
            return response.json().get('body', {}).get('expiryDates', [])
        except Exception as e:
            print(f"[Trendlyne] Error fetching expiry dates: {e}")
            return []

    async def get_live_oi_data(self, stock_id, expiry_date, min_time, max_time):
        url = f"{self.base_url}/live-oi-data/"
        params = {
            'stockId': stock_id,
            'expDateList': expiry_date,
            'minTime': min_time,
            'maxTime': max_time
        }
        try:
            print(f"[Trendlyne] Fetching live OI data for stock_id={stock_id}, expiry_date={expiry_date}, min_time={min_time}, max_time={max_time}")
            print(f"[Trendlyne] URL: {url} with params: {params}")
            response = await self.async_client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[Trendlyne] Error fetching live OI data: {e}")
            return None

    async def get_buildup_5m_data(self, expiry, symbol, strike_price, option_type):
        """
        Fetches 5-minute buildup data for a specific option strike.
        Expiry format expected by Trendlyne: '27-jan-2026-near'
        """
        # Map symbol if needed
        if "BANKNIFTY" in symbol.upper():
            symbol = "BANKNIFTY"
        elif "NIFTY" in symbol.upper():
            symbol = "NIFTY"

        url = f"{self.base_url}/fno/buildup-5/{expiry}/{symbol}/"
        params = {
            'fno_mtype': 'options',
            'strikePrice': strike_price,
            'option_type': option_type.lower()
        }
        try:
            print(f"[Trendlyne] Fetching 5m buildup data from {url}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[Trendlyne] Error fetching 5m buildup data: {e}")
            return None

#  THIS IS FOR LIVE BELOW 

    
# ***
# client = trendlyne_client.TrendlyneClient()
# # stock_id = client.get_stock_id_for_symbol("NIFTY")
# # expiryList = client.get_expiry_dates(stock_id)    
# # #get nearest expiry date
# # nearest_expiry = expiryList[0]
# # data = client.get_live_oi_data(stock_id, nearest_expiry, '9:15', '15:30')

# # print(data)
# # OVERALL DATA in RESPONSE -- AT Day LEVEL 
# ###"overallData": {
#             "totalVol": 4720894360.0,
#             "totalCallOi": 131889095.0,
#             "totalCallOiChange": 59469085.0,
#             "totalCallOiChangeP": 75.72452402609818,
#             "totalPutOi": 138002540.0,
#             "totalPutOiChange": 36213840.0,
#             "totalPutOiChangeP": 37.85079015467479,
#             "totalPCR": 1.0463529225065955,
#             "spotPrice": 25208.9,
#             "spotChange": -23.6,
#             "spotChangeP": -0.09,
#             "atm": 25200,


# ## THIS IS LIST OF STRIKES 
#             "strikePriceList": [
#                 20000,
#                 20050,
#                 20100,
#                 20150,
#                 20200,
#                 20250,

#                 # .... MANY MORE STRIKES
#             ],



#             ### THIS IS  CURRENT DATA PER STRIKE
#               "oiData": {
             

#              "25050": {
#                 "putOi": 3611075.0,  // CURRENT OI 
#                 "putPrevOi": 683865.0,  /// PREVIOUS DAY LAST OI
#                 "putOiChange": 2927210.0,
#                 "putOiChangeP": 428.0391597756867, //percent
#                 "callOi": 934375.0, //CURRENT OI 
#                 "callPrevOi": 40105.0, // PREV DAY OI
#                 "callOiChange": 894270.0,
#                 "callOiChangeP": 2229.8217179902754
#             },
#    "25100": {
#                 "putOi": 7547865.0,
#                 "putPrevOi": 2521610.0,
#                 "putOiChange": 5026255.0,
#                 "putOiChangeP": 199.3272155487962,
#                 "callOi": 2962570.0,
#                 "callPrevOi": 252525.0,
#                 "callOiChange": 2710045.0,
#                 "callOiChangeP": 1073.178893178893
#             },...

#              "26400": {
#                 "putOi": 449540.0,
#                 "putPrevOi": 486265.0,
#                 "putOiChange": -36725.0,
#                 "putOiChangeP": -7.55246624782783,
#                 "callOi": 3821415.0,
#                 "callPrevOi": 3769285.0,
#                 "callOiChange": 52130.0,
#                 "callOiChangeP": 1.3830209177602648
#             }
#         },
#         "inputData": {
#             "tradingDate": "2026-01-21",
#             "lastUpdatedDateTime": "2026-01-21T13:54:59+05:30",
#             "minTime": "09:15",
#             "maxTime": "13:58",
#             "minStrikePrice": 23892,
#             "maxStrikePrice": 26407,
#             "expDateList": [
#                 "2026-01-27"
#             ]
#             #
# # ***
########## USE BELOW FOR CURRENT DATE 5 MIN DATA FETCHING ##############
##    https://smartoptions.trendlyne.com/phoenix/api/fno/buildup-5/27-jan-2026-near/BANKNIFTY/?fno_mtype=options&strikePrice=59600&option_type=call
