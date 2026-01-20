import streamlit as st
import pandas as pd
from data.gathering.data_manager import DataManager
from core.strategies.trend_following import TrendFollowingStrategy
from core.strategies.mean_reversion import MeanReversionStrategy
from core.risk_manager import RiskManager
from visualization.candlestick import create_candlestick_chart
from visualization.footprint import create_footprint_chart
from tvDatafeed import Interval
import time

st.set_page_config(layout="wide", page_title="OptionScalp System")

def main():
    st.title("OptionScalp - Quant Trading System")

    tab1, tab2, tab3 = st.tabs(["Market Monitor", "Backtest", "Order Flow Analysis"])

    dm = DataManager()
    risk = RiskManager()
    strategy_tf = TrendFollowingStrategy()
    strategy_mr = MeanReversionStrategy()

    with tab1:
        st.header("Live Market Monitor (Simulated)")
        col1, col2 = st.columns(2)

        with col1:
            symbol = st.selectbox("Select Index", ["NIFTY", "BANKNIFTY"])
            interval_map = {
                "1m": Interval.in_1_minute,
                "3m": Interval.in_3_minute,
                "5m": Interval.in_5_minute
            }
            interval_str = st.selectbox("Interval", list(interval_map.keys()), index=2)
            interval = interval_map[interval_str]

            if st.button("Fetch Data"):
                with st.spinner("Fetching..."):
                    df = dm.get_data(symbol, interval=interval, n_bars=100, force_refresh=True)
                    if df is not None:
                        st.session_state['current_df'] = df
                        st.success(f"Fetched {len(df)} bars")

        if 'current_df' in st.session_state:
            df = st.session_state['current_df']

            # Trend Check
            trend = strategy_tf.identify_trend(df)
            st.metric("Detected Trend", trend)

            # Chart
            fig = create_candlestick_chart(df, title=f"{symbol} {interval_str} Chart")
            st.plotly_chart(fig, use_container_width=True)

            # Signal Check
            signal = strategy_tf.generate_signal(df, trend)
            if signal:
                st.warning(f"Strategy Signal Detected: {signal}")
                sl_tp = risk.get_sl_tp(signal['entry'], symbol_type=symbol)
                st.write(f"Entry: {signal['entry']}, SL: {sl_tp['sl']}, TP1: {sl_tp['tp1']}")

    with tab2:
        st.header("Backtesting Engine")
        st.info("Upload historical CSV or use fetched data to backtest strategies.")
        # Simplified backtest UI
        if 'current_df' in st.session_state:
            if st.button("Run Strategy 1 Backtest"):
                df = st.session_state['current_df']
                # Mock backtest
                st.write("Backtesting on current data...")
                results = []
                for i in range(10, len(df)):
                    sub_df = df.iloc[:i]
                    trend = strategy_tf.identify_trend(sub_df)
                    sig = strategy_tf.generate_signal(sub_df, trend)
                    if sig:
                        results.append({"time": df.index[i], "signal": sig})
                st.write(f"Found {len(results)} signals")
                st.table(pd.DataFrame(results))

    with tab3:
        st.header("Order Flow & Footprint")
        if 'current_df' in st.session_state:
            df = st.session_state['current_df']
            fig_fp = create_footprint_chart(df, title="Delta Footprint Visualization")
            st.plotly_chart(fig_fp, use_container_width=True)

            mr_signal = strategy_mr.generate_signal(df)
            if mr_signal:
                st.error(f"Mean Reversion Trap Detected! Signal: {mr_signal}")

if __name__ == "__main__":
    main()
