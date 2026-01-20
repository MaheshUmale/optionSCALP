import plotly.graph_objects as go
import pandas as pd

def create_candlestick_chart(df, title="Candlestick Chart", signals=None):
    fig = go.Figure(data=[go.Candlestick(x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price')])

    if signals:
        for signal in signals:
            fig.add_trace(go.Scatter(
                x=[signal['time']],
                y=[signal['price']],
                mode='markers',
                marker=dict(symbol='triangle-up', size=10, color='blue'),
                name='Signal'
            ))

    fig.update_layout(title=title, xaxis_rangeslider_visible=False)
    return fig
