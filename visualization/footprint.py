import pyqtgraph as pg
from PyQt6 import QtCore, QtGui
import numpy as np

class FootprintItem(pg.GraphicsObject):
    def __init__(self, df):
        pg.GraphicsObject.__init__(self)
        self.df = df # DataFrame with open, close, low, high, volume, delta_proxy
        self.generatePicture()

    def generatePicture(self):
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)

        # We need a font for volume numbers
        font = QtGui.QFont('Arial', 8)
        p.setFont(font)

        w = 0.8 # Width of footprint

        for i, row in self.df.iterrows():
            # Draw candle outline lightly
            p.setPen(pg.mkPen(255, 255, 255, 50))
            if row['close'] > row['open']:
                p.setBrush(pg.mkBrush(0, 255, 0, 20))
            else:
                p.setBrush(pg.mkBrush(255, 0, 0, 20))

            p.drawRect(QtCore.QRectF(i - w/2, row['open'], w, row['close'] - row['open']))

            # Draw simulated footprint clusters
            # Since we don't have per-price data, we divide the candle into 4 zones
            candle_range = max(row['high'] - row['low'], 1)
            zones = 4
            zone_height = candle_range / zones

            for z in range(zones):
                z_low = row['low'] + z * zone_height
                z_high = z_low + zone_height
                rect = QtCore.QRectF(i - w/2, z_low, w, zone_height)

                # Mock volume bifurcation for visual representation
                # Using delta_proxy to bias the colors
                vol = int(row['volume'] / zones)
                delta = int((row['close'] - row['open']) / zones)

                # Background color based on delta
                if delta > 0:
                    p.setBrush(pg.mkBrush(0, 150, 0, 100))
                else:
                    p.setBrush(pg.mkBrush(150, 0, 0, 100))

                p.drawRect(rect)

                # Draw text: Buy Vol | Sell Vol (Mocked)
                buy_v = max(0, vol//2 + delta)
                sell_v = max(0, vol//2 - delta)
                text = f"{buy_v}|{sell_v}"

                p.setPen(pg.mkPen('w'))
                p.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)

        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())
