import plotly.graph_objects as go
import pandas as pd
import numpy as np

def create_footprint_chart(df, title="Footprint Chart"):
    """
    Simulated Footprint chart.
    Displays volume at price for each candle.
    """
    if df is None or df.empty:
        return go.Figure()

    # To create a real footprint we'd need tick data.
    # With OHLCV we can only approximate or show volume per bar.
    # Here we'll create a visualization that shows volume bars next to candles or heatmaps.

    fig = go.Figure()

    # Candlestick as base
    fig.add_trace(go.Candlestick(x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price'))

    # Adding Volume Delta proxy as text or colored bars
    # Delta proxy = (Close - Low) - (High - Close) normalized
    df['delta_proxy'] = (df['close'] - df['low']) - (df['high'] - df['close'])

    # We can add annotations for delta
    for i, row in df.tail(20).iterrows():
        fig.add_annotation(
            x=i, y=row['high'],
            text=f"D:{int(row['delta_proxy'])}",
            showarrow=False,
            yshift=10
        )

    fig.update_layout(title=title, xaxis_rangeslider_visible=False)
    return fig
