import httpx
import asyncio
import json
from datetime import datetime

class TrendlyneScalper:
    def __init__(self):
        self.base_url = "https://smartoptions.trendlyne.com/phoenix/api"
        self.client = httpx.AsyncClient(timeout=20.0, follow_redirects=True)

    async def get_stock_id(self, symbol):
        s = "BANKNIFTY" if "BANK" in symbol.upper() else "NIFTY"
        url = f"{self.base_url}/search-contract-stock/"
        try:
            resp = await self.client.get(url, params={'query': s.lower()})
            data = resp.json()
            return data['body']['data'][0]['stock_id']
        except Exception as e:
            print(f"Error fetching stock ID: {e}")
            return None

    async def get_expiry_data(self, stock_id):
        url = f"{self.base_url}/fno/get-expiry-dates/?mtype=options&stock_id={stock_id}"
        try:
            resp = await self.client.get(url)
            # We map this to match your saved parsing logic key "expiresDts"
            return {"expiresDts": resp.json().get('body', {}).get('expiryDates', [])}
        except Exception:
            return {"expiresDts": []}

    async def get_live_oi_snapshot(self, stock_id, expiry_str):
        url = f"{self.base_url}/live-oi-data/"
        params = {'stockId': stock_id, 'expDateList': expiry_str, 'minTime': '09:15', 'maxTime': '15:30'}
        try:
            resp = await self.client.get(url, params=params)
            return resp.json()
        except Exception as e:
            print(f"Error fetching live OI: {e}")
            return None

    async def get_buildup_5m(self, expiry_dt, symbol, strike=None, o_type=None):
        """Fetches 5-minute buildup data for index or specific strike."""
        s_mapped = "BANKNIFTY" if "BANK" in symbol.upper() else "NIFTY"
        # Format: 27-jan-2026-near
        fmt_exp = f"{expiry_dt.strftime('%d-%b-%Y').lower()}-near"
        url = f"{self.base_url}/fno/buildup-5/{fmt_exp}/{s_mapped}/"
        print(url)
        params = {}
        if strike and o_type:
            params = {'fno_mtype': 'options', 'strikePrice': strike, 'option_type': o_type.lower()}
        
        try:
            resp = await self.client.get(url, params=params)
            # Returns list of lists: [Time, Status, PriceRange, PriceChg%, OIChg%]
            return resp.json().get('body', {}).get('data_v2', [])
        
        except Exception:
            return []

    def extract_writer_insights(self, live_data):
        """
        Parses JSON using your understanding:
        - putOi/callOi: Current
        - putOiChange/callOiChange: Change vs Prev Day
        """
        body = live_data.get('body', {})
        overall = body.get('overallData', {})
        strike_data = body.get('strikeWiseData', {})
        atm = overall.get('atm')

        # 1. Overall PCR Calculation
        total_p_oi = overall.get('totalPutOi', 0)
        total_c_oi = overall.get('totalCallOi', 0)
        pcr = total_p_oi / total_c_oi if total_c_oi > 0 else 0
        
        # 2. Change in PCR (Writers adding Puts vs Calls today)
        total_p_change = overall.get('totalPutOiChange', 0)
        total_c_change = overall.get('totalCallOiChange', 0)
        pcr_change = total_p_change / total_c_change if total_c_change > 0 else 0

        # 3. Highest OI Extraction
        # Highest CALL OI at or ABOVE ATM (Resistance)
        high_call = {"strike": 0, "oi": 0}
        # Highest PUT OI at or BELOW ATM (Support)
        high_put = {"strike": 0, "oi": 0}

        for strike, vals in strike_data.items():
            s_val = int(strike)
            # Call side logic (Writers capping the top)
            if s_val >= atm and vals['callOi'] > high_call['oi']:
                high_call = {"strike": s_val, "oi": vals['callOi']}
            # Put side logic (Writers floors)
            if s_val <= atm and vals['putOi'] > high_put['oi']:
                high_put = {"strike": s_val, "oi": vals['putOi']}

        return {
            "atm": atm,
            "pcr": round(pcr, 3),
            "pcr_change": round(pcr_change, 3),
            "resistance": high_call,
            "support": high_put
        }

async def main():
    scalper = TrendlyneScalper()
    symbol = "BANKNIFTY"
    t_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        stock_id = await scalper.get_stock_id(symbol)
        expiries = await scalper.get_expiry_data(stock_id)

        # USING YOUR PERSONALIZED DATE PARSING LOGIC
        # Added try/except block to handle YYYY-MM-DD vs DD-Mon-YYYY
        valid = []
        for e in expiries["expiresDts"]:
            try:
                dt = datetime.strptime(e, "%d-%b-%Y")
            except ValueError:
                dt = datetime.strptime(e, "%Y-%m-%d")
            
            if dt >= t_date:
                valid.append(dt)
        
        if not valid: return
        target_dt = valid[0]
        # String format for live-oi-data (YYYY-MM-DD)
        api_expiry_str = target_dt.strftime("%Y-%m-%d")

        # 1. Live OI Analysis
        live_data = await scalper.get_live_oi_snapshot(stock_id, api_expiry_str)
        if live_data:
            insights = scalper.extract_writer_insights(live_data)
            print(f"=== {symbol} Scalping Setup ===")
            print(f"ATM: {insights['atm']} | PCR: {insights['pcr']} | PCR Change: {insights['pcr_change']}")
            print(f"Writer Resistance (Highest Call >= ATM): {insights['resistance']['strike']} (OI: {insights['resistance']['oi']})")
            print(f"Writer Support (Highest Put <= ATM): {insights['support']['strike']} (OI: {insights['support']['oi']})")
            
            # Trend Check
            if insights['pcr_change'] > 1.2:
                print("SENTIMENT: Strong Bullish Change (Put Writing > Call Writing)")
            elif insights['pcr_change'] < 0.8:
                print("SENTIMENT: Strong Bearish Change (Call Writing > Put Writing)")

        # 2. 5-Min Buildup Trend
        buildup_5m = await scalper.get_buildup_5m(target_dt, symbol)
        # print("----------------------------------------")
        # print(buildup_5m)
        print(f"\n--- 5-Min {symbol} Index Buildup (Recent) --- {target_dt.strftime('%d-%b-%Y')}")
        # get list from [{},{},...] to [[...],[...],... ] of buildup_5m
        buildup_5m = [list(d.values()) for d in buildup_5m]
        
        for row in buildup_5m:
            print(f"{row[0]} | {row[1]} | Price Chg: {row[3]}% | OI Chg: {row[4]}%")
            print("----------------------------------------")
            print(row)
    except Exception as e:
        print(f"Error in main: {e}")

    finally:
        await scalper.client.aclose()

if __name__ == "__main__":
    asyncio.run(main())


#multiline comment test
""" output sample
--- 5-Min BANKNIFTY Index Buildup (Recent) --- 27-Jan-2026
15:25 TO 15:30 | Short Covering | Price Chg: -0.13% | OI Chg: 1.03%
----------------------------------------
['15:25 TO 15:30', 'Short Covering', '58794.800 - 58850.000', -0.13, 1.03, 58854.8, 1152750.0, -1500.0, 1301430.0, None, None, None, 1152750.0]
15:20 TO 15:25 | Short Build Up | Price Chg: 0.27% | OI Chg: 1.38%
----------------------------------------
['15:20 TO 15:25', 'Short Build Up', '58812.000 - 58868.000', 0.27, 1.38, 58818.4, 1154250.0, 3150.0, 1288170.0, None, None, None, 1154250.0]
15:15 TO 15:20 | Short Build Up | Price Chg: 0.4% | OI Chg: 0.83%
----------------------------------------
['15:15 TO 15:20', 'Short Build Up', '58835.000 - 58897.800', 0.4, 0.83, 58855.0, 1151100.0, 4560.0, 1270650.0, None, None, None, 1151100.0]
15:10 TO 15:15 | Short Build Up | Price Chg: 0.63% | OI Chg: 1.01%
----------------------------------------
['15:10 TO 15:15', 'Short Build Up', '58875.600 - 58983.000', 0.63, 1.01, 58864.4, 1146540.0, 7140.0, 1260240.0, None, None, None, 1146540.0]
15:05 TO 15:10 | Short Build Up | Price Chg: 0.08% | OI Chg: 0.89%
----------------------------------------
['15:05 TO 15:10', 'Short Build Up', '58870.000 - 58955.000', 0.08, 0.89, 58888.0, 1139400.0, 960.0, 1247640.0, None, None, None, 1139400.0]
15:00 TO 15:05 | Long Build Up | Price Chg: 0.05% | OI Chg: 0.46%
----------------------------------------
['15:00 TO 15:05', 'Long Build Up', '58880.200 - 58977.800', 0.05, 0.46, 58955.0, 1138440.0, 600.0, 1236690.0, None, None, None, 1138440.0]
14:55 TO 15:00 | Short Build Up | Price Chg: 0.08% | OI Chg: 0.37%
----------------------------------------
"""