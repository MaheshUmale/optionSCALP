from PyQt6 import QtCore, QtGui
import pyqtgraph as pg
import numpy as np

class FootprintItem(pg.GraphicsObject):
    def __init__(self, df, price_step=5):
        pg.GraphicsObject.__init__(self)
        self.df = df # DataFrame with open, close, low, high, volume
        self.price_step = price_step
        self.generatePicture()

    def generatePicture(self):
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)

        font = QtGui.QFont('Consolas', 7)
        p.setFont(font)

        w = 0.9 # Width of candle

        for i, row in self.df.iterrows():
            # Candle boundaries
            low = row['low']
            high = row['high']

            # Start from lowest price step and go up
            current_price = (low // self.price_step) * self.price_step
            while current_price <= high:
                rect = QtCore.QRectF(i - w/2, current_price, w, self.price_step)

                # Simulate volume bifurcation per price level
                # Since we don't have real tick data, we use a distribution
                # centered around (open+close)/2
                mid = (row['open'] + row['close']) / 2
                dist = np.exp(-((current_price - mid) / (row['high'] - row['low'] + 1))**2)
                vol_at_price = int(row['volume'] * dist / 5) # simplified

                # Delta proxy for this level
                level_delta = int(vol_at_price * (1 if row['close'] > row['open'] else -1) * 0.2)

                buy_v = max(0, (vol_at_price + level_delta) // 2)
                sell_v = max(0, (vol_at_price - level_delta) // 2)

                # Color coding
                if buy_v > sell_v:
                    alpha = min(255, 50 + buy_v)
                    p.setBrush(pg.mkBrush(0, 255, 0, alpha // 2))
                else:
                    alpha = min(255, 50 + sell_v)
                    p.setBrush(pg.mkBrush(255, 0, 0, alpha // 2))

                p.setPen(pg.mkPen(255, 255, 255, 20))
                p.drawRect(rect)

                # Text: "Buy | Sell"
                p.setPen(pg.mkPen('w'))
                text = f"{buy_v}|{sell_v}"
                p.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)

                current_price += self.price_step

        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())
