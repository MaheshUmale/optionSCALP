import httpx
import asyncio
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TrendlyneScalper:
    def __init__(self):
        self.base_url = "https://smartoptions.trendlyne.com/phoenix/api"
        self.session_cookies = self._fetch_cookies()
        headers = {'Cookie': self.session_cookies}
        self.client = httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers)
    
    def _fetch_cookies(self):
        """Fetch fresh cookies from Trendlyne homepage."""
        try:
            import requests
            logger.info("Fetching fresh Trendlyne cookies...")
            response = requests.get("https://smartoptions.trendlyne.com/", timeout=10)
            
            # Extract csrftoken from cookies
            csrf_token = response.cookies.get('csrftoken')
            if csrf_token:
                cookie_str = f"csrftoken={csrf_token}"
                logger.info(f"✅ Fetched Trendlyne cookie: csrftoken={csrf_token[:10]}...")
                return cookie_str
            else:
                logger.warning("⚠️ No csrftoken found, using fallback")
                return 'csrftoken=TxzIO3d7zB6Mhq7nVxN98vKEPp6qp8BLmtN0ZnuIfHlPNBeWeSue3qqpVym9eKRm'
        except Exception as e:
            logger.error(f"❌ Failed to fetch fresh cookies: {e}")
            return 'csrftoken=TxzIO3d7zB6Mhq7nVxN98vKEPp6qp8BLmtN0ZnuIfHlPNBeWeSue3qqpVym9eKRm'

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

    async def get_buildup_5m(self, symbol, strike=None, o_type=None):
        """Fetches 5-minute buildup data for index or specific strike."""
        import requests  # Use requests like user's example
        stock_id =await self.get_stock_id(symbol)
        expiry_data = await self.get_expiry_data(stock_id)    
        #get nearest expiry date
        nearest_expiry = expiry_data['expiresDts'][0]
        print(nearest_expiry)
        s_mapped = "BANKNIFTY" if "BANK" in symbol.upper() else "NIFTY"
        # CONVERT expirydate 2026-01-27 to new Format: 27-jan-2026  
        # THEN make it 27-jan-2026-near 
        # Input: nearest_expiry is currently "2026-01-27" (a string)
        # 1. Convert string to datetime object
        expiry_dt = datetime.strptime(nearest_expiry, '%Y-%m-%d')

        # 2. Reformat to "27-jan-2026" and add "-near"
        # %b provides the abbreviated month (jan), %d the day, and %Y the 4-digit year
        fmt_exp = f"{expiry_dt.strftime('%d-%b-%Y').lower()}-near"

        url = f"{self.base_url}/fno/buildup-5/{fmt_exp}/{s_mapped}/"
        params = {}
        if strike and o_type:
            params = {'fno_mtype': 'options', 'strikePrice': strike, 'option_type': o_type.lower()}

        print(f"[TrendlyneAdv] Calling: {url} | Params: {params}")
        
        try:
            # Use requests library with cookie header
            headers = {
                'Cookie': 'csrftoken=TxzIO3d7zB6Mhq7nVxN98vKEPp6qp8BLmtN0ZnuIfHlPNBeWeSue3qqpVym9eKRm'
            }
            response = requests.get(url, params=params, headers=headers, timeout=10)
            print(f"[TrendlyneAdv] Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[TrendlyneAdv] ERROR Response: {response.text[:500]}")
                return []
            
            json_data = response.json()
            print(f"[TrendlyneAdv] Response keys: {list(json_data.keys())}")
            
            # DEBUG: Print entire body
            import json as json_mod
            body = json_data.get('body', {})
            print(f"[TrendlyneAdv] Body keys: {list(body.keys())}")
            
            # Returns list of dicts or lists depending on the exact API response
            data_v2 = body.get('data_v2', [])
            table_data = body.get('tableData', [])
            
            print(f"[TrendlyneAdv] data_v2 has {len(data_v2)} records")
            print(f"[TrendlyneAdv] tableData has {len(table_data)} records")
            
            # Prefer data_v2 (list of dicts) over tableData (list of lists)
            if data_v2:
                data = data_v2
                print(f"[TrendlyneAdv] Using data_v2 (dict format)")
            elif table_data:
                # Convert tableData to dict format matching data_v2
                # tableData format: [interval, buildup, price_range, oi_change %, volume_change %]
                data = []
                for row in table_data:
                    if len(row) >= 5:
                        data.append({
                            'interval': row[0],
                            'buildup': row[1],
                            'price_range': row[2],
                            'oi_change': row[3],
                            'volume_change': row[4],
                            # Note: tableData doesn't have absolute OI values, only in data_v2
                        })
                print(f"[TrendlyneAdv] Converted {len(data)} tableData records to dict format")
            else:
                data = []
                print(f"[TrendlyneAdv] No data available")
            
            if data and len(data) > 0:
                print(f"[TrendlyneAdv] Sample record: {data[0]}")
            
            return data
        except Exception as e:
            print(f"[TrendlyneAdv] Exception: {e}")
            import traceback
            traceback.print_exc()
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
