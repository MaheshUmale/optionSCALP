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
            response = await self.async_client.get(search_url, params=params)
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
            response = await self.async_client.get(url, params=params)
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
"""
Intraday Live Oi Multi Expiry Data
https://smartoptions.trendlyne.com/phoenix/api/live-oi-data/?stockId=1887&expDateList=2026-01-27&minTime=9%3A15&maxTime=9%3A15
HTTP 200 OK
Allow: GET, HEAD, OPTIONS
Content-Type: application/json
Vary: Accept

{
    "head": {
        "status": "0",
        "statusDescription": "Success",
        "responseCode": null
    },
    "body": {
        "overallData": {
            "totalVol": 9290806720.0,
            "totalCallOi": 199082845.0,
            "totalCallOiChange": 2439320.0,
            "totalCallOiChangeP": 1.9455043132050431,
            "totalPutOi": 127821720.0,
            "totalPutOiChange": 72938970.0,
            "totalPutOiChangeP": 57.822046452909426,
            "totalPCR": 0.6420529101842,
            "spotPrice": 25048.65,
            "spotChange": -241.25,
            "spotChangeP": -0.95,
            "atm": 25050,
            "hideTimeSlider": true,
            "strikePriceList": [
                19900,
                19950,
                20000,
                20050,
                20100,
                20150,
                20200,
                20250,
                20300,
                20350,
                20400,
                20450,
                20500,
                20550,
                20600,
                20650,
                20700,
                20750,
                20800,
                20850,
                20900,
                20950,
                21000,
                21050,
                21100,
                21150,
                21200,
                21250,
                21300,
                21350,
                21400,
                21450,
                21500,
                21550,
                21600,
                21650,
                21700,
                21750,
                21800,
                21850,
                21900,
                21950,
                22000,
                22050,
                22100,
                22150,
                22200,
                22250,
                22300,
                22350,
                22400,
                22450,
                22500,
                22550,
                22600,
                22650,
                22700,
                22750,
                22800,
                22850,
                22900,
                22950,
                23000,
                23050,
                23100,
                23150,
                23200,
                23250,
                23300,
                23350,
                23400,
                23450,
                23500,
                23550,
                23600,
                23650,
                23700,
                23750,
                23800,
                23850,
                23900,
                23950,
                24000,
                24050,
                24100,
                24150,
                24200,
                24250,
                24300,
                24350,
                24400,
                24450,
                24500,
                24550,
                24600,
                24650,
                24700,
                24750,
                24800,
                24850,
                24900,
                24950,
                25000,
                25050,
                25100,
                25150,
                25200,
                25250,
                25300,
                25350,
                25400,
                25450,
                25500,
                25550,
                25600,
                25650,
                25700,
                25750,
                25800,
                25850,
                25900,
                25950,
                26000,
                26050,
                26100,
                26150,
                26200,
                26250,
                26300,
                26350,
                26400,
                26450,
                26500,
                26550,
                26600,
                26650,
                26700,
                26750,
                26800,
                26850,
                26900,
                26950,
                27000,
                27050,
                27100,
                27150,
                27200,
                27250,
                27300,
                27350,
                27400,
                27450,
                27500,
                27550,
                27600,
                27650,
                27700,
                27750,
                27800,
                27850,
                27900,
                27950,
                28000,
                28050,
                28100,
                28150,
                28200,
                28250,
                28300,
                28350,
                28400,
                28450,
                28500,
                28550,
                28600,
                28650,
                28700,
                28750,
                28800,
                28850,
                28900,
                28950,
                29000,
                29050,
                29100,
                29150,
                29200,
                29250,
                29300,
                29350,
                29400,
                29450,
                29500,
                29550,
                29600,
                29650,
                29700,
                29750,
                29800,
                29850,
                29900,
                29950,
                30000,
                30050,
                30100,
                30150,
                30200,
                30250,
                30300,
                30350,
                30400,
                30450,
                30500,
                30550,
                30600,
                30650,
                30700,
                30750,
                30800,
                30850,
                30900,
                30950,
                31000,
                31050,
                31100,
                31150,
                31200,
                31250,
                31300,
                31350,
                31400,
                31450,
                31500,
                31550,
                31600
            ]
        },
        "oiData": {
            "23800": {
                "putOi": 3357770.0,
                "putPrevOi": 2620150.0,
                "putOiChange": 737620.0,
                "putOiChangeP": 28.151823368891094,
                "callOi": 16055.0,
                "callPrevOi": 22100.0,
                "callOiChange": -6045.0,
                "callOiChangeP": -27.352941176470587
            },
            "23850": {
                "putOi": 436020.0,
                "putPrevOi": 351845.0,
                "putOiChange": 84175.0,
                "putOiChangeP": 23.923886938850913,
                "callOi": 975.0,
                "callPrevOi": 975.0,
                "callOiChange": 0.0,
                "callOiChangeP": 0.0
            },
            "23900": {
                "putOi": 1551225.0,
                "putPrevOi": 890955.0,
                "putOiChange": 660270.0,
                "putOiChangeP": 74.10811993871745,
                "callOi": 9295.0,
                "callPrevOi": 9230.0,
                "callOiChange": 65.0,
                "callOiChangeP": 0.704225352112676
            },
            "23950": {
                "putOi": 643955.0,
                "putPrevOi": 382915.0,
                "putOiChange": 261040.0,
                "putOiChangeP": 68.17178747241555,
                "callOi": 1625.0,
                "callPrevOi": 1430.0,
                "callOiChange": 195.0,
                "callOiChangeP": 13.636363636363637
            },
            "24000": {
                "putOi": 10253880.0,
                "putPrevOi": 9216480.0,
                "putOiChange": 1037400.0,
                "putOiChangeP": 11.255924170616113,
                "callOi": 573430.0,
                "callPrevOi": 801840.0,
                "callOiChange": -228410.0,
                "callOiChangeP": -28.48573281452659
            },
            "24050": {
                "putOi": 561665.0,
                "putPrevOi": 396695.0,
                "putOiChange": 164970.0,
                "putOiChangeP": 41.586105194166805,
                "callOi": 585.0,
                "callPrevOi": 260.0,
                "callOiChange": 325.0,
                "callOiChangeP": 125.0
            },
            "24100": {
                "putOi": 1527565.0,
                "putPrevOi": 1255475.0,
                "putOiChange": 272090.0,
                "putOiChangeP": 21.672275433600827,
                "callOi": 3250.0,
                "callPrevOi": 3900.0,
                "callOiChange": -650.0,
                "callOiChangeP": -16.666666666666668
            },
            "24150": {
                "putOi": 587600.0,
                "putPrevOi": 475345.0,
                "putOiChange": 112255.0,
                "putOiChangeP": 23.615479283467796,
                "callOi": 130.0,
                "callPrevOi": 130.0,
                "callOiChange": 0.0,
                "callOiChangeP": 0.0
            },
            "24200": {
                "putOi": 3216590.0,
                "putPrevOi": 3430570.0,
                "putOiChange": -213980.0,
                "putOiChangeP": -6.237447421274016,
                "callOi": 2730.0,
                "callPrevOi": 3250.0,
                "callOiChange": -520.0,
                "callOiChangeP": -16.0
            },
            "24250": {
                "putOi": 1185405.0,
                "putPrevOi": 1143610.0,
                "putOiChange": 41795.0,
                "putOiChangeP": 3.654654996021371,
                "callOi": 2795.0,
                "callPrevOi": 2665.0,
                "callOiChange": 130.0,
                "callOiChangeP": 4.878048780487805
            },
            "24300": {
                "putOi": 2861950.0,
                "putPrevOi": 3017560.0,
                "putOiChange": -155610.0,
                "putOiChangeP": -5.156815440289505,
                "callOi": 4810.0,
                "callPrevOi": 5980.0,
                "callOiChange": -1170.0,
                "callOiChangeP": -19.565217391304348
            },
            "24350": {
                "putOi": 1558700.0,
                "putPrevOi": 754585.0,
                "putOiChange": 804115.0,
                "putOiChangeP": 106.56387285726592,
                "callOi": 3835.0,
                "callPrevOi": 3770.0,
                "callOiChange": 65.0,
                "callOiChangeP": 1.7241379310344827
            },
            "24400": {
                "putOi": 3067805.0,
                "putPrevOi": 2442830.0,
                "putOiChange": 624975.0,
                "putOiChangeP": 25.58405619711564,
                "callOi": 11830.0,
                "callPrevOi": 17615.0,
                "callOiChange": -5785.0,
                "callOiChangeP": -32.84132841328413
            },
            "24450": {
                "putOi": 1241955.0,
                "putPrevOi": 1253915.0,
                "putOiChange": -11960.0,
                "putOiChangeP": -0.9538126587527863,
                "callOi": 13455.0,
                "callPrevOi": 15015.0,
                "callOiChange": -1560.0,
                "callOiChangeP": -10.38961038961039
            },
            "24500": {
                "putOi": 9173060.0,
                "putPrevOi": 8766030.0,
                "putOiChange": 407030.0,
                "putOiChangeP": 4.643264967151607,
                "callOi": 466505.0,
                "callPrevOi": 322595.0,
                "callOiChange": 143910.0,
                "callOiChangeP": 44.61011484988918
            },
            "24550": {
                "putOi": 1247090.0,
                "putPrevOi": 1156675.0,
                "putOiChange": 90415.0,
                "putOiChangeP": 7.816802472604664,
                "callOi": 10530.0,
                "callPrevOi": 19240.0,
                "callOiChange": -8710.0,
                "callOiChangeP": -45.270270270270274
            },
            "24600": {
                "putOi": 4523610.0,
                "putPrevOi": 2781090.0,
                "putOiChange": 1742520.0,
                "putOiChangeP": 62.656008974898334,
                "callOi": 28340.0,
                "callPrevOi": 40820.0,
                "callOiChange": -12480.0,
                "callOiChangeP": -30.573248407643312
            },
            "24650": {
                "putOi": 2909140.0,
                "putPrevOi": 2109250.0,
                "putOiChange": 799890.0,
                "putOiChangeP": 37.92295839753467,
                "callOi": 20735.0,
                "callPrevOi": 35100.0,
                "callOiChange": -14365.0,
                "callOiChangeP": -40.925925925925924
            },
            "24700": {
                "putOi": 7218120.0,
                "putPrevOi": 4613960.0,
                "putOiChange": 2604160.0,
                "putOiChangeP": 56.44088808745633,
                "callOi": 171015.0,
                "callPrevOi": 161720.0,
                "callOiChange": 9295.0,
                "callOiChangeP": 5.747588424437299
            },
            "24750": {
                "putOi": 2611050.0,
                "putPrevOi": 1954940.0,
                "putOiChange": 656110.0,
                "putOiChangeP": 33.56164383561644,
                "callOi": 52845.0,
                "callPrevOi": 46475.0,
                "callOiChange": 6370.0,
                "callOiChangeP": 13.706293706293707
            },
            "24800": {
                "putOi": 6582810.0,
                "putPrevOi": 5689060.0,
                "putOiChange": 893750.0,
                "putOiChangeP": 15.709976692107308,
                "callOi": 307840.0,
                "callPrevOi": 295165.0,
                "callOiChange": 12675.0,
                "callOiChangeP": 4.294208324157674
            },
            "24850": {
                "putOi": 2567825.0,
                "putPrevOi": 1815645.0,
                "putOiChange": 752180.0,
                "putOiChangeP": 41.4277020012172,
                "callOi": 89635.0,
                "callPrevOi": 69615.0,
                "callOiChange": 20020.0,
                "callOiChangeP": 28.758169934640524
            },
            "24900": {
                "putOi": 6037980.0,
                "putPrevOi": 5531370.0,
                "putOiChange": 506610.0,
                "putOiChangeP": 9.158852146936473,
                "callOi": 503750.0,
                "callPrevOi": 184925.0,
                "callOiChange": 318825.0,
                "callOiChangeP": 172.40773286467487
            },
            "24950": {
                "putOi": 2877225.0,
                "putPrevOi": 2167230.0,
                "putOiChange": 709995.0,
                "putOiChangeP": 32.7604822746086,
                "callOi": 247260.0,
                "callPrevOi": 110435.0,
                "callOiChange": 136825.0,
                "callOiChangeP": 123.8964096527369
            },
            "25000": {
                "putOi": 9746945.0,
                "putPrevOi": 10056475.0,
                "putOiChange": -309530.0,
                "putOiChangeP": -3.077917461138222,
                "callOi": 3726710.0,
                "callPrevOi": 2011880.0,
                "callOiChange": 1714830.0,
                "callOiChangeP": 85.23520289480486
            },
            "25050": {
                "putOi": 4277260.0,
                "putPrevOi": 2204605.0,
                "putOiChange": 2072655.0,
                "putOiChangeP": 94.01480083733821,
                "callOi": 2297620.0,
                "callPrevOi": 604240.0,
                "callOiChange": 1693380.0,
                "callOiChangeP": 280.249569707401
            },
            "25100": {
                "putOi": 5802290.0,
                "putPrevOi": 5183165.0,
                "putOiChange": 619125.0,
                "putOiChangeP": 11.944921683951794,
                "callOi": 7733180.0,
                "callPrevOi": 2058940.0,
                "callOiChange": 5674240.0,
                "callOiChangeP": 275.5903523172118
            },
            "25150": {
                "putOi": 2262910.0,
                "putPrevOi": 3170570.0,
                "putOiChange": -907660.0,
                "putOiChangeP": -28.627660010660545,
                "callOi": 4034680.0,
                "callPrevOi": 1151280.0,
                "callOiChange": 2883400.0,
                "callOiChangeP": 250.4516711833785
            },
            "25200": {
                "putOi": 3426410.0,
                "putPrevOi": 7475780.0,
                "putOiChange": -4049370.0,
                "putOiChangeP": -54.16652175425173,
                "callOi": 10313420.0,
                "callPrevOi": 3260530.0,
                "callOiChange": 7052890.0,
                "callOiChangeP": 216.31115186794784
            },
            "25250": {
                "putOi": 1538095.0,
                "putPrevOi": 2579005.0,
                "putOiChange": -1040910.0,
                "putOiChangeP": -40.36091438364796,
                "callOi": 5881785.0,
                "callPrevOi": 1798095.0,
                "callOiChange": 4083690.0,
                "callOiChangeP": 227.11202689513067
            },
            "25300": {
                "putOi": 4501120.0,
                "putPrevOi": 6205680.0,
                "putOiChange": -1704560.0,
                "putOiChangeP": -27.467739232445116,
                "callOi": 14447550.0,
                "callPrevOi": 5805215.0,
                "callOiChange": 8642335.0,
                "callOiChangeP": 148.8719194724054
            },
            "25350": {
                "putOi": 1191580.0,
                "putPrevOi": 2021630.0,
                "putOiChange": -830050.0,
                "putOiChangeP": -41.05845283261527,
                "callOi": 8622250.0,
                "callPrevOi": 2944825.0,
                "callOiChange": 5677425.0,
                "callOiChangeP": 192.79328992384947
            },
            "25400": {
                "putOi": 1901640.0,
                "putPrevOi": 2942095.0,
                "putOiChange": -1040455.0,
                "putOiChangeP": -35.36442568985706,
                "callOi": 12996295.0,
                "callPrevOi": 7709910.0,
                "callOiChange": 5286385.0,
                "callOiChangeP": 68.56610518151314
            },
            "25450": {
                "putOi": 457405.0,
                "putPrevOi": 806975.0,
                "putOiChange": -349570.0,
                "putOiChangeP": -43.31856625050342,
                "callOi": 5590390.0,
                "callPrevOi": 3240380.0,
                "callOiChange": 2350010.0,
                "callOiChangeP": 72.52266709460001
            },
            "25500": {
                "putOi": 2837770.0,
                "putPrevOi": 3646760.0,
                "putOiChange": -808990.0,
                "putOiChangeP": -22.183801511478684,
                "callOi": 17697160.0,
                "callPrevOi": 11430770.0,
                "callOiChange": 6266390.0,
                "callOiChangeP": 54.820366432007646
            },
            "25550": {
                "putOi": 230100.0,
                "putPrevOi": 341120.0,
                "putOiChange": -111020.0,
                "putOiChangeP": -32.545731707317074,
                "callOi": 5239000.0,
                "callPrevOi": 2992535.0,
                "callOiChange": 2246465.0,
                "callOiChangeP": 75.06896327027086
            },
            "25600": {
                "putOi": 1058785.0,
                "putPrevOi": 1723085.0,
                "putOiChange": -664300.0,
                "putOiChangeP": -38.55294428307367,
                "callOi": 8899865.0,
                "callPrevOi": 7286045.0,
                "callOiChange": 1613820.0,
                "callOiChangeP": 22.149465176237587
            },
            "25650": {
                "putOi": 161330.0,
                "putPrevOi": 243685.0,
                "putOiChange": -82355.0,
                "putOiChangeP": -33.79567884769272,
                "callOi": 4763655.0,
                "callPrevOi": 2500355.0,
                "callOiChange": 2263300.0,
                "callOiChangeP": 90.51914628122806
            },
            "25700": {
                "putOi": 1186575.0,
                "putPrevOi": 1408420.0,
                "putOiChange": -221845.0,
                "putOiChangeP": -15.751338379176666,
                "callOi": 11313640.0,
                "callPrevOi": 6460350.0,
                "callOiChange": 4853290.0,
                "callOiChangeP": 75.1242579736392
            },
            "25750": {
                "putOi": 188435.0,
                "putPrevOi": 212485.0,
                "putOiChange": -24050.0,
                "putOiChangeP": -11.318446007953503,
                "callOi": 3873870.0,
                "callPrevOi": 3431415.0,
                "callOiChange": 442455.0,
                "callOiChangeP": 12.894243336932432
            },
            "25800": {
                "putOi": 1371305.0,
                "putPrevOi": 1640210.0,
                "putOiChange": -268905.0,
                "putOiChangeP": -16.39454703970833,
                "callOi": 10191090.0,
                "callPrevOi": 8761545.0,
                "callOiChange": 1429545.0,
                "callOiChangeP": 16.31612917584741
            },
            "25850": {
                "putOi": 138450.0,
                "putPrevOi": 217295.0,
                "putOiChange": -78845.0,
                "putOiChangeP": -36.28477415495065,
                "callOi": 3065530.0,
                "callPrevOi": 2625285.0,
                "callOiChange": 440245.0,
                "callOiChangeP": 16.76941741563297
            },
            "25900": {
                "putOi": 612950.0,
                "putPrevOi": 854230.0,
                "putOiChange": -241280.0,
                "putOiChangeP": -28.245320346979153,
                "callOi": 7100535.0,
                "callPrevOi": 6663540.0,
                "callOiChange": 436995.0,
                "callOiChangeP": 6.558000702329393
            },
            "25950": {
                "putOi": 108095.0,
                "putPrevOi": 124020.0,
                "putOiChange": -15925.0,
                "putOiChangeP": -12.840670859538784,
                "callOi": 2052830.0,
                "callPrevOi": 2302885.0,
                "callOiChange": -250055.0,
                "callOiChangeP": -10.858336391092044
            },
            "26000": {
                "putOi": 3491865.0,
                "putPrevOi": 4139915.0,
                "putOiChange": -648050.0,
                "putOiChangeP": -15.653703034965694,
                "callOi": 16822325.0,
                "callPrevOi": 14365000.0,
                "callOiChange": 2457325.0,
                "callOiChangeP": 17.10633484162896
            },
            "26050": {
                "putOi": 87815.0,
                "putPrevOi": 90545.0,
                "putOiChange": -2730.0,
                "putOiChangeP": -3.0150753768844223,
                "callOi": 2603900.0,
                "callPrevOi": 1787045.0,
                "callOiChange": 816855.0,
                "callOiChangeP": 45.70981704433856
            },
            "26100": {
                "putOi": 1150045.0,
                "putPrevOi": 1246050.0,
                "putOiChange": -96005.0,
                "putOiChangeP": -7.704747000521649,
                "callOi": 7427290.0,
                "callPrevOi": 5704400.0,
                "callOiChange": 1722890.0,
                "callOiChangeP": 30.202825888787604
            },
            "26150": {
                "putOi": 91195.0,
                "putPrevOi": 118950.0,
                "putOiChange": -27755.0,
                "putOiChangeP": -23.333333333333332,
                "callOi": 2050230.0,
                "callPrevOi": 1447875.0,
                "callOiChange": 602355.0,
                "callOiChangeP": 41.602693602693606
            },
            "26200": {
                "putOi": 1296620.0,
                "putPrevOi": 1476735.0,
                "putOiChange": -180115.0,
                "putOiChangeP": -12.196839649632466,
                "callOi": 8425235.0,
                "callPrevOi": 7464210.0,
                "callOiChange": 961025.0,
                "callOiChangeP": 12.875106675723218
            },
            "26250": {
                "putOi": 127855.0,
                "putPrevOi": 162565.0,
                "putOiChange": -34710.0,
                "putOiChangeP": -21.351459416233507,
                "callOi": 2746055.0,
                "callPrevOi": 2217670.0,
                "callOiChange": 528385.0,
                "callOiChangeP": 23.826132833108623
            },
            "26300": {
                "putOi": 776880.0,
                "putPrevOi": 872170.0,
                "putOiChange": -95290.0,
                "putOiChangeP": -10.925622298405127,
                "callOi": 6623500.0,
                "callPrevOi": 5943405.0,
                "callOiChange": 680095.0,
                "callOiChangeP": 11.442851362140052
            }
        },
        "inputData": {
            "tradingDate": "2026-01-23",
            "lastUpdatedDateTime": "2026-01-23T15:40:00+05:30",
            "minTime": "09:15",
            "maxTime": "15:30",
            "minStrikePrice": 23797,
            "maxStrikePrice": 26302,
            "expDateList": [
                "2026-01-27"
            ]
        }
    }
}





refer to URL https://smartoptions.trendlyne.com/derivative/buildup-15-minutes/27-jan-2026/1887/NIFTY/nifty-50/
FUTURE BUILDUP DATA 
Request URL
https://smartoptions.trendlyne.com/phoenix/api/fno/buildup-5/27-jan-2026-near/NIFTY/?fno_mtype=futures
Request Method
GET 


STRIKEPRICE WISE BUILDUP 
https://smartoptions.trendlyne.com/phoenix/api/fno/buildup-5/27-jan-2026-near/BANKNIFTY/?fno_mtype=options&strikePrice=59600&option_type=call


"""



