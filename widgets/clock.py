# -*- coding: utf-8 -*-

# Copyright © 2018 Jean-Sébastien Gosselin
# https://github.com/jnsebgosselin/qwatson
#
# This file is part of QWatson.
# Licensed under the terms of the GNU General Public License.

# ---- Standard imports

import time
import sys

# ---- Third party imports

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QLCDNumber, QApplication

# https://stackoverflow.com/questions/14478574/
# changing-the-digit-color-of-qlcd-number


class ElapsedTimeLCDNumber(QLCDNumber):
    """A widget that displays elapsed time in digital format."""

    def __init__(self, parent=None):
        super(ElapsedTimeLCDNumber, self).__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_elapsed_time)

        self.setDigitCount(8)
        self.setSegmentStyle(QLCDNumber.Flat)
        self.display(time.strftime("%H:%M:%S", time.gmtime(0)))
        self.setFrameStyle(0)

    def start(self):
        """Start the elapsed time counter."""
        self._start_time = time.time()
        self.timer.start(10)

    def stop(self):
        """Stop the elapsed time counter."""
        self.timer.stop()

    def update_elapsed_time(self):
        """Update elapsed time in the widget."""
        elapsed_time = time.time() - self._start_time
        self.display(time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    timer = ElapsedTimeLCDNumber()
    timer.show()
    app.exec_()