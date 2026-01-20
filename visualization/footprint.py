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

                # Imbalance coloring
                # If Buy Vol > 2x Sell Vol -> Strong Green
                # If Sell Vol > 2x Buy Vol -> Strong Red
                if buy_v > 2 * sell_v and buy_v > 0:
                    p.setBrush(pg.mkBrush(0, 255, 0, 180))
                elif sell_v > 2 * buy_v and sell_v > 0:
                    p.setBrush(pg.mkBrush(255, 0, 0, 180))
                elif buy_v > sell_v:
                    p.setBrush(pg.mkBrush(0, 200, 0, 80))
                else:
                    p.setBrush(pg.mkBrush(200, 0, 0, 80))

                p.setPen(pg.mkPen(255, 255, 255, 40))
                p.drawRect(rect)

                # Value Area Highlight
                if row['low'] <= current_price <= row['high']:
                    if abs(current_price - mid) < self.price_step:
                        p.setPen(pg.mkPen(255, 255, 0, 200, width=1))
                        p.drawRect(rect)

                # Text: "Buy | Sell"
                p.setPen(pg.mkPen('w'))
                text = f"{buy_v} | {sell_v}"
                p.drawText(rect, QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter, text)

                current_price += self.price_step

        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())
