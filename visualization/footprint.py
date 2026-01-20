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
                rect_left = QtCore.QRectF(i - w/2, current_price, w/2, self.price_step)
                rect_right = QtCore.QRectF(i, current_price, w/2, self.price_step)

                # Order Flow Logic
                mid = (row['open'] + row['close']) / 2
                dist = np.exp(-((current_price - mid) / (max(row['high'] - row['low'], 1)))**2)
                vol_at_price = int(row['volume'] * dist / 5)

                level_delta = int(vol_at_price * (1 if row['close'] > row['open'] else -1) * 0.3)
                buy_v = max(0, (vol_at_price + level_delta) // 2)
                sell_v = max(0, (vol_at_price - level_delta) // 2)

                # Split-Cell Coloring
                # Left side (Sellers)
                s_alpha = min(255, 40 + int(sell_v / 50))
                p.setBrush(pg.mkBrush(255, 0, 0, s_alpha))
                p.setPen(pg.mkPen(255, 255, 255, 20))
                p.drawRect(rect_left)

                # Right side (Buyers)
                b_alpha = min(255, 40 + int(buy_v / 50))
                p.setBrush(pg.mkBrush(0, 255, 0, b_alpha))
                p.drawRect(rect_right)

                # Strong Imbalance Highlight
                if buy_v > 3 * sell_v and buy_v > 10:
                    p.setPen(pg.mkPen(255, 255, 255, 200, width=2))
                    p.drawRect(rect_right)
                elif sell_v > 3 * buy_v and sell_v > 10:
                    p.setPen(pg.mkPen(255, 255, 255, 200, width=2))
                    p.drawRect(rect_left)

                # POC Highlight
                if abs(current_price - mid) < self.price_step:
                    p.setPen(pg.mkPen(255, 255, 0, 255, width=1))
                    p.drawLine(QtCore.QPointF(i-w/2, current_price), QtCore.QPointF(i+w/2, current_price))

                # Numerical values
                p.setPen(pg.mkPen('w'))
                p.drawText(rect_left, QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter, str(sell_v))
                p.drawText(rect_right, QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter, str(buy_v))

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
