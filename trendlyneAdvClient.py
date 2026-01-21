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
            # We map this to match parsing logic key "expiresDts"
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
        params = {}
        if strike and o_type:
            params = {'fno_mtype': 'options', 'strikePrice': strike, 'option_type': o_type.lower()}

        try:
            resp = await self.client.get(url, params=params)
            # Returns list of dicts or lists depending on the exact API response
            data = resp.json().get('body', {}).get('data_v2', [])
            return data
        except Exception:
            return []

    def extract_writer_insights(self, live_data):
        """
        Parses JSON:
        - putOi/callOi: Current
        - putOiChange/callOiChange: Change vs Prev Day
        """
        if not live_data or 'body' not in live_data:
            return None

        body = live_data.get('body', {})
        overall = body.get('overallData', {})
        strike_data = body.get('strikeWiseData', {})
        atm = overall.get('atm', 0)

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
            try:
                s_val = int(strike)
                # Call side logic (Writers capping the top)
                if s_val >= atm and vals.get('callOi', 0) > high_call['oi']:
                    high_call = {"strike": s_val, "oi": vals['callOi']}
                # Put side logic (Writers floors)
                if s_val <= atm and vals.get('putOi', 0) > high_put['oi']:
                    high_put = {"strike": s_val, "oi": vals['putOi']}
            except ValueError:
                continue

        return {
            "atm": atm,
            "pcr": round(pcr, 3),
            "pcr_change": round(pcr_change, 3),
            "resistance": high_call,
            "support": high_put
        }

    async def aclose(self):
        await self.client.aclose()
