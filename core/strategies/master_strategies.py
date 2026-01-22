import pandas as pd
import pandas_ta as ta
import numpy as np
from core.strategies.base_strategy import BaseStrategy

def get_prev_day_close(df):
    if df is None or len(df) < 2: return None
    last_dt = df.index[-1]
    # Find candles from previous days
    prev_days = df[df.index.date < last_dt.date()]
    if not prev_days.empty:
        return prev_days['close'].iloc[-1]
    return None

class BBMeanReversionLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("BB_MEAN_REVERSION_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        if pcr_insights is None: pcr_insights = {}

        buildup = pcr_insights.get('buildup_status', '').upper()
        pcr = pcr_insights.get('pcr', 1.0)

        if not (any(x in buildup for x in ['LONG BUILD', 'SHORT COVER', 'NEUTRAL']) or buildup == ''):
            return None
        if pcr <= 0.8: return None

        df_ta = df.copy()
        bb = ta.bbands(df_ta['close'], length=20, std=2.0)
        if bb is None or 'BBL_20_2.0' not in bb or pd.isna(bb['BBL_20_2.0'].iloc[-1]):
            return None

        lower_band = bb['BBL_20_2.0'].iloc[-1]
        last_candle = df.iloc[-1]

        if last_candle['low'] < lower_band:
            self.vars['lower_band'] = lower_band

        if 'lower_band' in self.vars:
            if last_candle['close'] > self.vars['lower_band'] and last_candle['close'] > last_candle['open']:
                lb = self.vars['lower_band']
                self.reset_vars()
                return {
                    "type": "LONG",
                    "entry_price": last_candle['close'],
                    "sl": last_candle['low'] - 5,
                    "target": last_candle['close'] + (last_candle['close'] - last_candle['low']) * 2,
                    "reason": "Price hit lower Bollinger Band and reversed."
                }
        return None

class BBMeanReversionShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("BB_MEAN_REVERSION_SHORT", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        if pcr_insights is None: pcr_insights = {}

        buildup = pcr_insights.get('buildup_status', '').upper()
        pcr = pcr_insights.get('pcr', 1.0)

        if not (any(x in buildup for x in ['SHORT BUILD', 'LONG UNWIND', 'NEUTRAL']) or buildup == ''):
            return None
        if pcr >= 1.2: return None

        df_ta = df.copy()
        bb = ta.bbands(df_ta['close'], length=20, std=2.0)
        if bb is None or 'BBU_20_2.0' not in bb or pd.isna(bb['BBU_20_2.0'].iloc[-1]):
            return None

        upper_band = bb['BBU_20_2.0'].iloc[-1]
        last_candle = df.iloc[-1]

        if last_candle['high'] > upper_band:
            self.vars['upper_band'] = upper_band

        if 'upper_band' in self.vars:
            if last_candle['close'] < self.vars['upper_band'] and last_candle['close'] < last_candle['open']:
                ub = self.vars['upper_band']
                self.reset_vars()
                return {
                    "type": "SHORT",
                    "entry_price": last_candle['close'],
                    "sl": last_candle['high'] + 5,
                    "target": last_candle['close'] - (last_candle['high'] - last_candle['close']) * 2,
                    "reason": "Price hit upper Bollinger Band and reversed."
                }
        return None

class BigDogBreakoutLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("BIGDOG_BREAKOUT_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 20: return None

        last_10 = df.iloc[-10:]
        range_high = last_10['high'].max()
        range_low = last_10['low'].min()
        price = df['close'].iloc[-1]

        if (range_high - range_low) / price < 0.002:
            self.vars['range_high'] = range_high
            self.vars['range_low'] = range_low

        if 'range_high' in self.vars:
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            last_candle = df.iloc[-1]
            if last_candle['close'] > self.vars['range_high'] and last_candle['volume'] > 1.8 * avg_vol:
                rl = self.vars['range_low']
                self.reset_vars()
                return {
                    "type": "LONG",
                    "entry_price": last_candle['close'],
                    "sl": rl,
                    "target": last_candle['close'] + (last_candle['close'] - rl) * 3,
                    "reason": "Low volatility consolidation broken upside with high volume."
                }
        return None

class BigDogBreakoutShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("BIGDOG_BREAKOUT_SHORT", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 20: return None

        last_10 = df.iloc[-10:]
        range_high = last_10['high'].max()
        range_low = last_10['low'].min()
        price = df['close'].iloc[-1]

        if (range_high - range_low) / price < 0.002:
            self.vars['range_high'] = range_high
            self.vars['range_low'] = range_low

        if 'range_low' in self.vars:
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            last_candle = df.iloc[-1]
            if last_candle['close'] < self.vars['range_low'] and last_candle['volume'] > 1.8 * avg_vol:
                rh = self.vars['range_high']
                self.reset_vars()
                return {
                    "type": "SHORT",
                    "entry_price": last_candle['close'],
                    "sl": rh,
                    "target": last_candle['close'] - (rh - last_candle['close']) * 3,
                    "reason": "Low volatility consolidation broken downside with high volume."
                }
        return None

class BRFShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("BRF_SHORT", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 10: return None
        last_candle = df.iloc[-1]

        if last_candle['volume'] > 10000:
            self.vars['mother_h'] = last_candle['high']
            self.vars['mother_l'] = last_candle['low']
            self.vars['setup_idx'] = len(df)

        if 'mother_l' in self.vars:
            if len(df) - self.vars['setup_idx'] <= 5:
                if last_candle['close'] < self.vars['mother_l']:
                    self.vars['validated'] = True

            if self.vars.get('validated') and last_candle['high'] < self.vars['mother_h'] and last_candle['close'] > self.vars['mother_l']:
                 mh = self.vars['mother_h']
                 self.reset_vars()
                 return {
                    "type": "SHORT",
                    "entry_price": last_candle['close'],
                    "sl": mh,
                    "target": last_candle['close'] - 50,
                    "reason": "Mother candle breakout (Downside)."
                }
        return None

class BRFReversalShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("BRF_REVERSAL_SHORT", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 5: return None
        last_candle = df.iloc[-1]

        if last_candle['volume'] > 10000:
            self.vars['mother_h'] = last_candle['high']
            self.vars['mother_l'] = last_candle['low']

        if 'mother_l' in self.vars:
            if last_candle['close'] < self.vars['mother_l']:
                self.vars['broken_low'] = True

            if self.vars.get('broken_low') and last_candle['high'] < self.vars['mother_h'] and last_candle['close'] < self.vars['mother_l']:
                 mh = self.vars['mother_h']
                 self.reset_vars()
                 return {
                    "type": "SHORT",
                    "entry_price": last_candle['close'],
                    "sl": mh,
                    "target": last_candle['close'] - 100,
                    "reason": "Mother candle reversal from high."
                }
        return None

class GapFillLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("GAP_FILL_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 5: return None
        prev_close = get_prev_day_close(df)
        if not prev_close: return None

        last_time = df.index[-1]
        if not (last_time.hour == 9 and 15 <= last_time.minute <= 30): return None

        day_open = df[df.index.date == last_time.date()]['open'].iloc[0]
        if day_open > prev_close * 0.998: return None

        ma5 = df['close'].rolling(5).mean().iloc[-1]
        buildup = pcr_insights.get('buildup_status', '').upper() if pcr_insights else ''

        if df.iloc[-1]['close'] > ma5 and any(x in buildup for x in ['LONG BUILD', 'SHORT COVER']):
            return {
                "type": "LONG",
                "entry_price": df.iloc[-1]['close'],
                "sl": df.iloc[-1]['low'],
                "target": prev_close,
                "reason": "Price opening lower than previous close with bullish buildup."
            }
        return None

class IndexBreakoutLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("INDEX_BREAKOUT_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        last_candle = df.iloc[-1]

        if last_candle['close'] > ma20 and last_candle['volume'] > 1.2 * avg_vol and last_candle['close'] > last_candle['open']:
            return {
                "type": "LONG",
                "entry_price": last_candle['close'],
                "sl": last_candle['low'],
                "target": last_candle['close'] + 50,
                "reason": "Price above MA20 with volume breakout."
            }
        return None

class RSIScalperLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("RSI_SCALPER_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 15: return None
        rsi = ta.rsi(df['close'], length=14)
        if rsi is None or pd.isna(rsi.iloc[-1]): return None

        if rsi.iloc[-1] < 30: self.vars['oversold'] = True

        if self.vars.get('oversold'):
            if df.iloc[-1]['close'] > df.iloc[-1]['open'] and rsi.iloc[-1] > rsi.iloc[-2]:
                self.reset_vars()
                return {
                    "type": "LONG",
                    "entry_price": df.iloc[-1]['close'],
                    "sl": df.iloc[-1]['low'],
                    "target": df.iloc[-1]['close'] + 30,
                    "reason": "RSI Oversold reversal."
                }
        return None

class RSIScalperShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("RSI_SCALPER_SHORT", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 15: return None
        rsi = ta.rsi(df['close'], length=14)
        if rsi is None or pd.isna(rsi.iloc[-1]): return None

        if rsi.iloc[-1] > 70: self.vars['overbought'] = True

        if self.vars.get('overbought'):
            if df.iloc[-1]['close'] < df.iloc[-1]['open'] and rsi.iloc[-1] < rsi.iloc[-2]:
                self.reset_vars()
                return {
                    "type": "SHORT",
                    "entry_price": df.iloc[-1]['close'],
                    "sl": df.iloc[-1]['high'],
                    "target": df.iloc[-1]['close'] - 30,
                    "reason": "RSI Overbought reversal."
                }
        return None

class SnapReversalLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("SNAP_REVERSAL_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        last = df.iloc[-1]
        size = last['high'] - last['low']
        wick = min(last['open'], last['close']) - last['low']
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]

        if size > 0 and (wick / size) >= 0.4 and last['volume'] > 1.2 * avg_vol:
            self.vars['snap_high'] = last['high']

        if 'snap_high' in self.vars:
            if last['close'] > self.vars['snap_high']:
                sh = self.vars['snap_high']
                self.reset_vars()
                return {
                    "type": "LONG",
                    "entry_price": last['close'],
                    "sl": last['low'],
                    "target": last['close'] + 40,
                    "reason": "Pin bar reversal (Bullish)."
                }
        return None

class SnapReversalShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("SNAP_REVERSAL_SHORT", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        last = df.iloc[-1]
        size = last['high'] - last['low']
        wick = last['high'] - max(last['open'], last['close'])

        if size > 0 and (wick / size) >= 0.4:
            self.vars['snap_low'] = last['low']

        if 'snap_low' in self.vars:
            if last['close'] < self.vars['snap_low']:
                sl = self.vars['snap_low']
                self.reset_vars()
                return {
                    "type": "SHORT",
                    "entry_price": last['close'],
                    "sl": last['high'],
                    "target": last['close'] - 40,
                    "reason": "Pin bar reversal (Bearish)."
                }
        return None

class SmartTrendIndexLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("SMART_TREND_INDEX_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        buildup = pcr_insights.get('buildup_status', '').upper() if pcr_insights else ''
        if any(x in buildup for x in ['LONG BUILD', 'SHORT COVER']):
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            if df.iloc[-1]['close'] > ma20 and df.iloc[-1]['volume'] > df['volume'].rolling(20).mean().iloc[-1]:
                return {
                    "type": "LONG",
                    "entry_price": df.iloc[-1]['close'],
                    "sl": df.iloc[-1]['low'],
                    "target": df.iloc[-1]['close'] + 60,
                    "reason": "Bullish trend with EMA/VWAP support."
                }
        return None

class SmartTrendIndexShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("SMART_TREND_INDEX_SHORT", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        buildup = pcr_insights.get('buildup_status', '').upper() if pcr_insights else ''
        if any(x in buildup for x in ['SHORT BUILD', 'LONG UNWIND']):
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            if df.iloc[-1]['close'] < ma20 and df.iloc[-1]['volume'] > df['volume'].rolling(20).mean().iloc[-1]:
                return {
                    "type": "SHORT",
                    "entry_price": df.iloc[-1]['close'],
                    "sl": df.iloc[-1]['high'],
                    "target": df.iloc[-1]['close'] - 60,
                    "reason": "Bearish trend with EMA/VWAP resistance."
                }
        return None

class InstitutionalDemandLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("INSTITUTIONAL_DEMAND_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 51: return None
        last = df.iloc[-1]
        low50 = df['low'].rolling(50).min().iloc[-1]
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]

        if last['low'] <= low50 and last['volume'] > 1.5 * avg_vol:
            self.vars['block_high'] = last['high']
            self.vars['block_low'] = last['low']

        if 'block_low' in self.vars:
            brange = self.vars['block_high'] - self.vars['block_low']
            if self.vars['block_low'] <= last['low'] <= self.vars['block_low'] + 0.3 * brange:
                self.vars['retested'] = True
            if self.vars.get('retested') and last['close'] > self.vars['block_high']:
                bl = self.vars['block_low']
                self.reset_vars()
                return {
                    "type": "LONG",
                    "entry_price": last['close'],
                    "sl": bl,
                    "target": last['close'] + 100,
                    "reason": "Retest of institutional demand zone."
                }
        return None

class RoundLevelRejectionShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("ROUND_LEVEL_REJECTION_SHORT", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 2: return None
        price = df.iloc[-1]['close']
        round_level = round(price / 100) * 100
        if abs(price - round_level) <= 50:
            self.vars['round_level'] = round_level

        if 'round_level' in self.vars:
            if price < df.iloc[-2]['low']:
                self.reset_vars()
                return {
                    "type": "SHORT",
                    "entry_price": price,
                    "sl": df.iloc[-1]['high'],
                    "target": price - 50,
                    "reason": "Rejection from round psychological level."
                }
        return None

class SampleTrendReversalShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("SAMPLE_TREND_REVERSAL", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
        if df.iloc[-1]['close'] > ma20 + 2 * atr and df.iloc[-1]['volume'] > 50000:
            self.vars['overextended'] = True
        if self.vars.get('overextended'):
            if df.iloc[-1]['close'] < df.iloc[-2]['low']:
                self.reset_vars()
                return {
                    "type": "SHORT",
                    "entry_price": df.iloc[-1]['close'],
                    "sl": df.iloc[-1]['high'],
                    "target": df.iloc[-1]['close'] - 100,
                    "reason": "Overextended trend reversal."
                }
        return None

class ScreenerMomentumLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("SCREENER_MOMENTUM_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        open_price = df[df.index.date == df.index[-1].date()]['open'].iloc[0]
        if (df.iloc[-1]['volume'] / avg_vol) > 1.2 and (df.iloc[-1]['close'] / open_price) > 1.003:
            atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
            if df['close'].iloc[-5:].std() < atr:
                self.vars['range_max'] = df['high'].iloc[-5:].max()
        if 'range_max' in self.vars:
            if df.iloc[-1]['close'] > self.vars['range_max'] and df.iloc[-1]['volume'] > avg_vol:
                self.reset_vars()
                return {
                    "type": "LONG",
                    "entry_price": df.iloc[-1]['close'],
                    "sl": df.iloc[-1]['low'],
                    "target": df.iloc[-1]['close'] + 50,
                    "reason": "Strong momentum with volume breakout."
                }
        return None

class VolumeSpikeScalperLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("VOLUME_SPIKE_SCALPER_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        if df.iloc[-1]['volume'] > 3.0 * avg_vol:
            avg_body = abs(df['close'] - df['open']).rolling(20).mean().iloc[-1]
            if abs(df.iloc[-1]['close'] - df.iloc[-1]['open']) > 1.5 * avg_body:
                self.vars['spike_high'] = df.iloc[-1]['high']
        if 'spike_high' in self.vars:
            if df.iloc[-1]['close'] > self.vars['spike_high']:
                self.reset_vars()
                return {
                    "type": "LONG",
                    "entry_price": df.iloc[-1]['close'],
                    "sl": df.iloc[-1]['low'],
                    "target": df.iloc[-1]['close'] + 30,
                    "reason": "Volume spike with large body candle."
                }
        return None

class VWAPEMAGateLong(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("VWAP_EMA_GATE_LONG", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        vwap = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        ema9 = ta.ema(df['close'], length=9)
        if df.iloc[-1]['close'] > vwap.iloc[-1] and df.iloc[-1]['close'] > ema9.iloc[-1]:
            if df.iloc[-1]['volume'] > 1.5 * df['volume'].rolling(20).mean().iloc[-1]:
                return {
                    "type": "LONG",
                    "entry_price": df.iloc[-1]['close'],
                    "sl": ema9.iloc[-1],
                    "target": df.iloc[-1]['close'] + 40,
                    "reason": "Price above VWAP and EMA9 with volume."
                }
        return None

class VWAPEMAGateShort(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("VWAP_EMA_GATE_SHORT", symbol_type, is_index_driven=True)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 21: return None
        vwap = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        ema9 = ta.ema(df['close'], length=9)
        if df.iloc[-1]['close'] < vwap.iloc[-1] and df.iloc[-1]['close'] < ema9.iloc[-1]:
            if df.iloc[-1]['volume'] > 1.5 * df['volume'].rolling(20).mean().iloc[-1]:
                return {
                    "type": "SHORT",
                    "entry_price": df.iloc[-1]['close'],
                    "sl": ema9.iloc[-1],
                    "target": df.iloc[-1]['close'] - 40,
                    "reason": "Price below VWAP and EMA9 with volume."
                }
        return None

class OptionBuyTest(BaseStrategy):
    def __init__(self, symbol_type="BANKNIFTY"):
        super().__init__("OPTION_BUY_TEST", symbol_type, is_index_driven=False)

    def check_setup(self, df, pcr_insights=None):
        if df is None or len(df) < 2: return None
        # Always trigger a test signal to verify PnL flow
        last_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]
        if last_candle['close'] > prev_candle['high']:
            return {
                "type": "LONG",
                "entry_price": last_candle['close'],
                "sl": last_candle['low'] - 10,
                "target": last_candle['close'] + 20,
                "reason": "Test Signal."
            }
        return None

STRATEGIES = [
    BBMeanReversionLong, BBMeanReversionShort, BigDogBreakoutLong, BigDogBreakoutShort,
    BRFShort, BRFReversalShort, GapFillLong, IndexBreakoutLong, RSIScalperLong, RSIScalperShort,
    SnapReversalLong, SnapReversalShort, SmartTrendIndexLong, SmartTrendIndexShort,
    InstitutionalDemandLong, RoundLevelRejectionShort, SampleTrendReversalShort,
    ScreenerMomentumLong, VolumeSpikeScalperLong, VWAPEMAGateLong, VWAPEMAGateShort, OptionBuyTest
]
