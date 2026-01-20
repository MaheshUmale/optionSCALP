import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QLabel, QComboBox, QTabWidget
from PyQt6 import QtCore
import pyqtgraph as pg
from data.gathering.data_manager import DataManager
from core.strategies.trend_following import TrendFollowingStrategy
from visualization.candlestick import CandlestickItem
from visualization.footprint import FootprintItem
from tvDatafeed import Interval

class ScalpApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OptionScalp - Quant Scalper Pro")
        self.dm = DataManager()
        self.strategy = TrendFollowingStrategy()
        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.index_combo = QComboBox()
        self.index_combo.addItems(["BANKNIFTY", "NIFTY"])
        ctrl_layout.addWidget(QLabel("Index:"))
        ctrl_layout.addWidget(self.index_combo)

        self.fetch_btn = QPushButton("Refresh Market Data")
        self.fetch_btn.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold;")
        self.fetch_btn.clicked.connect(self.update_charts)
        ctrl_layout.addWidget(self.fetch_btn)

        layout.addLayout(ctrl_layout)

        # Tabs for different views
        self.tabs = QTabWidget()

        # Tab 1: Standard View
        self.std_tab = QWidget()
        std_layout = QVBoxLayout(self.std_tab)
        self.index_plot = pg.PlotWidget(title="Index Chart (15m Trend)")
        self.option_plot = pg.PlotWidget(title="Option Chart (5m Scalp)")
        std_layout.addWidget(self.index_plot)
        std_layout.addWidget(self.option_plot)
        self.tabs.addTab(self.std_tab, "Standard View")

        # Tab 2: Footprint View
        self.fp_tab = QWidget()
        fp_layout = QVBoxLayout(self.fp_tab)
        self.fp_plot = pg.PlotWidget(title="Option Footprint (Order Flow)")
        self.fp_plot.setBackground('k')
        fp_layout.addWidget(self.fp_plot)
        self.tabs.addTab(self.fp_tab, "Footprint Analysis")

        layout.addWidget(self.tabs)

        # Info Panel
        self.info_panel = QLabel("Status: Ready")
        self.info_panel.setStyleSheet("font-size: 14px; color: yellow; background-color: black; padding: 5px;")
        layout.addWidget(self.info_panel)

    def update_charts(self):
        index_sym = self.index_combo.currentText()
        self.info_panel.setText("Fetching data...")

        # 1. Index Data (Trend)
        index_df = self.dm.get_data(index_sym, interval=Interval.in_15_minute, n_bars=100)
        if index_df is not None:
            self.plot_candlesticks(self.index_plot, index_df)
            trend = self.strategy.get_trend(index_df)

            # 2. Strike & Option
            last_spot = index_df['close'].iloc[-1]
            strike = self.dm.get_atm_strike(last_spot, step=100 if index_sym=="BANKNIFTY" else 50)
            opt_type = "C" if trend == "BULLISH" else "P"
            opt_sym = self.dm.get_option_symbol(index_sym, strike, opt_type, "260127")

            self.info_panel.setText(f"Trend: {trend} | ATM: {strike} | Option: {opt_sym}")

            # 3. Option Data
            opt_df = self.dm.get_data(opt_sym, interval=Interval.in_5_minute, n_bars=50)
            if opt_df is not None:
                self.plot_candlesticks(self.option_plot, opt_df)
                self.plot_footprint(self.fp_plot, opt_df)

                # 4. Strategy Check
                setup = self.strategy.check_setup(opt_df, trend)
                if setup:
                    self.info_panel.setText(f"SIGNAL! BUY {opt_sym} Above {setup['entry_price']} | SL: {setup['sl']}")
                    # Visual Signal
                    line = pg.InfiniteLine(pos=setup['entry_price'], angle=0, pen=pg.mkPen('b', width=2))
                    self.option_plot.addItem(line)
                    sl_line = pg.InfiniteLine(pos=setup['sl'], angle=0, pen=pg.mkPen('r', width=2, style=QtCore.Qt.PenStyle.DashLine))
                    self.option_plot.addItem(sl_line)

    def plot_candlesticks(self, plot_widget, df):
        plot_widget.clear()
        data = []
        for i, row in df.iterrows():
            data.append((i, row['open'], row['close'], row['low'], row['high']))
        item = CandlestickItem(data)
        plot_widget.addItem(item)

    def plot_footprint(self, plot_widget, df):
        plot_widget.clear()
        # Keep only last 10 candles for footprint visibility
        df_tail = df.tail(10).reset_index(drop=True)
        item = FootprintItem(df_tail)
        plot_widget.addItem(item)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScalpApp()
    window.resize(1200, 900)
    window.show()
    sys.exit(app.exec())
