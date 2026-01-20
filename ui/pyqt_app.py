import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QHBoxLayout, QPushButton, QLabel, QComboBox,
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6 import QtCore
import pyqtgraph as pg
from data.gathering.data_manager import DataManager
from core.strategies.trend_following import TrendFollowingStrategy
from visualization.candlestick import CandlestickItem
from visualization.footprint import FootprintItem
from tvDatafeed import Interval
import pandas as pd

class ScalpApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OptionScalp - Pro Quant Trader")
        self.dm = DataManager()
        self.strategy = TrendFollowingStrategy()

        # Timer for Auto-Refresh
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_charts)

        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel: Charts
        chart_layout = QVBoxLayout()

        # Controls
        ctrl_layout = QHBoxLayout()
        self.index_combo = QComboBox()
        self.index_combo.addItems(["BANKNIFTY", "NIFTY"])
        ctrl_layout.addWidget(QLabel("Index:"))
        ctrl_layout.addWidget(self.index_combo)

        self.refresh_btn = QPushButton("Auto-Refresh: OFF")
        self.refresh_btn.setCheckable(True)
        self.refresh_btn.clicked.connect(self.toggle_refresh)
        ctrl_layout.addWidget(self.refresh_btn)

        chart_layout.addLayout(ctrl_layout)

        # Tabs
        self.tabs = QTabWidget()

        # Standard View
        self.std_tab = QWidget()
        std_layout = QVBoxLayout(self.std_tab)
        self.index_plot = pg.PlotWidget(title="Index (15m)")
        self.option_plot = pg.PlotWidget(title="Option (5m)")
        std_layout.addWidget(self.index_plot)
        std_layout.addWidget(self.option_plot)
        self.tabs.addTab(self.std_tab, "Charts")

        # Footprint View
        self.fp_tab = QWidget()
        fp_layout = QVBoxLayout(self.fp_tab)
        self.fp_plot = pg.PlotWidget(title="Footprint (Order Flow)")
        self.fp_plot.setBackground('k')
        fp_layout.addWidget(self.fp_plot)
        self.tabs.addTab(self.fp_tab, "Footprint")

        # Backtest Tab
        self.bt_tab = QWidget()
        bt_layout = QVBoxLayout(self.bt_tab)
        self.bt_report = QLabel("Backtest results will appear here...")
        self.bt_run_btn = QPushButton("Run Backtest on Current Symbol")
        self.bt_run_btn.clicked.connect(self.run_backtest)
        bt_layout.addWidget(self.bt_run_btn)

        # Replay Controls in Backtest Tab
        replay_ctrl = QHBoxLayout()
        self.replay_btn = QPushButton("Start Visual Replay")
        self.replay_btn.clicked.connect(self.start_replay)
        replay_ctrl.addWidget(self.replay_btn)
        self.replay_speed = QComboBox()
        self.replay_speed.addItems(["1s", "2s", "5s"])
        replay_ctrl.addWidget(QLabel("Speed:"))
        replay_ctrl.addWidget(self.replay_speed)
        bt_layout.addLayout(replay_ctrl)

        bt_layout.addWidget(self.bt_report)
        self.tabs.addTab(self.bt_tab, "Backtest / Replay")

        chart_layout.addWidget(self.tabs)

        # Replay Timer & State
        self.replay_timer = QtCore.QTimer()
        self.replay_timer.timeout.connect(self.step_replay)
        self.replay_idx = 0
        self.replay_df_index = None
        self.replay_df_option = None
        main_layout.addLayout(chart_layout, stretch=3)

        # Right Panel: Signals & Trade Details
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("<b>ACTIVE SIGNALS</b>"))
        self.signal_table = QTableWidget(0, 4)
        self.signal_table.setHorizontalHeaderLabels(["Time", "Symbol", "Type", "Status"])
        self.signal_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_panel.addWidget(self.signal_table)

        right_panel.addWidget(QLabel("<b>TRADE DETAILS</b>"))
        self.details_label = QLabel("No active trade")
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet("background-color: #1a1a1a; padding: 10px; border: 1px solid #333;")
        right_panel.addWidget(self.details_label)

        main_layout.addLayout(right_panel, stretch=1)

    def toggle_refresh(self):
        if self.refresh_btn.isChecked():
            self.refresh_btn.setText("Auto-Refresh: ON")
            self.refresh_btn.setStyleSheet("background-color: green; color: white;")
            self.timer.start(60000) # 1 minute
            self.update_charts()
        else:
            self.refresh_btn.setText("Auto-Refresh: OFF")
            self.refresh_btn.setStyleSheet("")
            self.timer.stop()

    def update_charts(self):
        index_sym = self.index_combo.currentText()

        # 1. Index Trend
        index_df = self.dm.get_data(index_sym, interval=Interval.in_15_minute, n_bars=100)
        if index_df is not None:
            self.plot_candlesticks(self.index_plot, index_df)
            trend = self.strategy.get_trend(index_df)

            # 2. Strike Selection
            last_spot = index_df['close'].iloc[-1]
            strike = self.dm.get_atm_strike(last_spot, step=100 if index_sym=="BANKNIFTY" else 50)
            opt_type = "C" if trend == "BULLISH" else "P"
            opt_sym = self.dm.get_option_symbol(index_sym, strike, opt_type)

            # 3. Option Data
            opt_df = self.dm.get_data(opt_sym, interval=Interval.in_5_minute, n_bars=50)
            if opt_df is not None:
                self.plot_candlesticks(self.option_plot, opt_df)
                self.plot_footprint(self.fp_plot, opt_df)

                # 4. Signal Logic
                setup = self.strategy.check_setup(opt_df, trend)
                if setup:
                    self.add_signal(opt_sym, "BUY", "READY")
                    self.details_label.setText(
                        f"<b>SYMBOL:</b> {opt_sym}<br>"
                        f"<b>ENTRY:</b> Above {setup['entry_price']}<br>"
                        f"<b>SL:</b> {setup['sl']}<br>"
                        f"<b>T1:</b> {setup['entry_price']+30}<br>"
                        f"<b>T2:</b> {setup['entry_price']+60}"
                    )
                    # Mark on chart
                    self.option_plot.addLine(y=setup['entry_price'], pen=pg.mkPen('b', width=2))
                    self.option_plot.addLine(y=setup['sl'], pen=pg.mkPen('r', width=1, style=QtCore.Qt.PenStyle.DashLine))

    def add_signal(self, sym, type, status):
        row = self.signal_table.rowCount()
        self.signal_table.insertRow(row)
        time_str = QtCore.QDateTime.currentDateTime().toString("hh:mm:ss")
        self.signal_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.signal_table.setItem(row, 1, QTableWidgetItem(sym))
        self.signal_table.setItem(row, 2, QTableWidgetItem(type))
        self.signal_table.setItem(row, 3, QTableWidgetItem(status))

    def plot_candlesticks(self, plot_widget, df):
        plot_widget.clear()
        data = []
        for i, row in df.iterrows():
            data.append((i, row['open'], row['close'], row['low'], row['high']))
        item = CandlestickItem(data)
        plot_widget.addItem(item)

    def plot_footprint(self, plot_widget, df):
        plot_widget.clear()
        df_tail = df.tail(8).reset_index(drop=True)
        item = FootprintItem(df_tail, price_step=2 if "NIFTY" in self.index_combo.currentText() else 5)
        plot_widget.addItem(item)

    def run_backtest(self):
        index_sym = self.index_combo.currentText()
        df = self.dm.get_data(index_sym, interval=Interval.in_5_minute, n_bars=500)
        if df is not None:
            results = []
            for i in range(20, len(df)):
                sub_df = df.iloc[:i]
                trend = self.strategy.get_trend(sub_df)
                setup = self.strategy.check_setup(sub_df, trend)
                if setup:
                    results.append(f"Time: {i}, Signal: BUY")
            self.bt_report.setText("<br>".join(results) if results else "No signals found in history.")

    def start_replay(self):
        if self.replay_timer.isActive():
            self.replay_timer.stop()
            self.replay_btn.setText("Start Visual Replay")
            return

        self.info_panel.setText("Initializing Replay...")
        index_sym = self.index_combo.currentText()
        self.replay_df_index = self.dm.get_data(index_sym, interval=Interval.in_15_minute, n_bars=100)

        # Determine ATM Option for the start of the replay
        if self.replay_df_index is not None:
            last_spot = self.replay_df_index['close'].iloc[0]
            strike = self.dm.get_atm_strike(last_spot)
            # Fetch Call option for simulation
            opt_sym = self.dm.get_option_symbol(index_sym, strike, "C")
            self.replay_df_option = self.dm.get_data(opt_sym, interval=Interval.in_5_minute, n_bars=100)

            if self.replay_df_option is not None:
                self.replay_idx = 20 # Start with some history
                speed_map = {"1s": 1000, "2s": 2000, "5s": 5000}
                self.replay_timer.start(speed_map[self.replay_speed.currentText()])
                self.replay_btn.setText("Stop Replay")
                self.tabs.setCurrentIndex(0) # Switch to Charts view

    def step_replay(self):
        if self.replay_idx >= len(self.replay_df_option):
            self.replay_timer.stop()
            self.replay_btn.setText("Start Visual Replay")
            self.info_panel.setText("Replay Finished.")
            return

        # Feed one more candle
        sub_idx = self.replay_df_index.iloc[:min(len(self.replay_df_index), self.replay_idx // 3 + 10)]
        sub_opt = self.replay_df_option.iloc[:self.replay_idx]

        self.plot_candlesticks(self.index_plot, sub_idx)
        self.plot_candlesticks(self.option_plot, sub_opt)
        self.plot_footprint(self.fp_plot, sub_opt)

        trend = self.strategy.get_trend(sub_idx)
        setup = self.strategy.check_setup(sub_opt, trend)

        if setup:
            self.info_panel.setText(f"[REPLAY] SIGNAL! BUY Above {setup['entry_price']}")
            self.add_signal("REPLAY_OPT", "BUY", "TRIGGERED")
            self.option_plot.addLine(y=setup['entry_price'], pen=pg.mkPen('b', width=2))
        else:
            self.info_panel.setText(f"[REPLAY] Stepping... Index: {sub_idx['close'].iloc[-1]:.2f} | Option: {sub_opt['close'].iloc[-1]:.2f}")

        self.replay_idx += 1

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScalpApp()
    window.showMaximized()
    sys.exit(app.exec())
