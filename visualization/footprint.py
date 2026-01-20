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
            low = row['low']
            high = row['high']

            # Draw a light border for the whole candle area
            p.setPen(pg.mkPen(255, 255, 255, 30))
            p.setBrush(pg.mkBrush(0, 0, 0, 0))
            p.drawRect(QtCore.QRectF(i - w/2, low, w, high - low))

            current_price = (low // self.price_step) * self.price_step
            while current_price < high:
                rect = QtCore.QRectF(i - w/2, current_price, w, self.price_step)

                # Enhanced visual logic for footprint
                mid = (row['open'] + row['close']) / 2
                dist = np.exp(-((current_price - mid) / (max(row['high'] - row['low'], 1)))**2)
                vol_at_price = int(row['volume'] * dist / 5)

                level_delta = int(vol_at_price * (1 if row['close'] > row['open'] else -1) * 0.2)
                buy_v = max(0, (vol_at_price + level_delta) // 2)
                sell_v = max(0, (vol_at_price - level_delta) // 2)

                # Imbalance coloring and heat intensity
                total_v = buy_v + sell_v
                intensity = min(200, 50 + int(total_v / 100))

                if buy_v > 2 * sell_v and buy_v > 0:
                    p.setBrush(pg.mkBrush(0, 255, 0, 200)) # Aggressive Buy
                    p.setPen(pg.mkPen(255, 255, 255, 150, width=1))
                elif sell_v > 2 * buy_v and sell_v > 0:
                    p.setBrush(pg.mkBrush(255, 0, 0, 200)) # Aggressive Sell
                    p.setPen(pg.mkPen(255, 255, 255, 150, width=1))
                elif buy_v > sell_v:
                    p.setBrush(pg.mkBrush(0, 150, 0, intensity))
                    p.setPen(pg.mkPen(255, 255, 255, 30))
                else:
                    p.setBrush(pg.mkBrush(150, 0, 0, intensity))
                    p.setPen(pg.mkPen(255, 255, 255, 30))

                p.drawRect(rect)

                # Highlight Point of Control (POC) for the candle
                if abs(current_price - mid) < self.price_step:
                    p.setPen(pg.mkPen(255, 255, 0, 255, width=2))
                    p.drawRect(rect)

                # Numerical values with contrast
                p.setPen(pg.mkPen('w'))
                text = f"{buy_v} × {sell_v}"
                # Use a slightly larger/bolder font for imbalances
                if buy_v > 2 * sell_v or sell_v > 2 * buy_v:
                    f = p.font()
                    f.setBold(True)
                    p.setFont(f)

                p.drawText(rect, QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter, text)

                # Reset font
                f = p.font()
                f.setBold(False)
                p.setFont(f)

                current_price += self.price_step

        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())
