
import sys
import numpy as np
from PyQt4 import QtGui, QtCore
from collections import deque

import pyqtgraph as pg



class Am_plot(pg.PlotWidget):

    def __init__(self, parent=None, width=5, height=4, dpi=100):

        super(Am_plot, self).__init__()


        #self.setMinimumSize(300, 100)
        self.data = [ deque([]), deque([]), deque([]) ]
        #self.data = deque([])
        self.timestamps = deque([])
        self.x_scale = 300
        self.y_scale = 10

        #font = QtGui.QFont('Serif', 7, QtGui.QFont.Light)
        #qp.setFont(font)

        self.colors = [QtGui.QColor(220, 0, 0), \
                      QtGui.QColor(0, 200, 0), \
                      QtGui.QColor(30, 30, 255)]


        #self.axes.set_xlim([0, 400])


        #self.setDownsampling(ds=2, auto=False, mode='peak')

        left_axis   = self.getAxis('left')
        right_axis  = self.getAxis('right')
        top_axis    = self.getAxis('top')
        bottom_axis = self.getAxis('bottom')



    def clear_slot(self):
	# DEQUE ALLOWS FAST ADD OR REMOVE FROM EITHER END
        self.data = [ deque([]), deque([]), deque([]) ]
        #self.data = deque([]) 
        self.timestamps = deque([])

    # RECEIVE A NEW DATA SAMPLE AND REPAINT GRAPH
    def data_slot(self, timestamp, values, refresh=True):

        #self.data.append(values)
        self.data[0].append(values[0])
        self.data[1].append(values[1])
        self.data[2].append(values[2])
        self.timestamps.append(timestamp)

        if (len(self.timestamps) > self.x_scale):
            #self.data.popleft()
            self.data[0].popleft()
            self.data[1].popleft()
            self.data[2].popleft()
            self.timestamps.popleft()

        #print len(self.data[0])
        if (refresh):
            self.clear()
            self.plot(self.timestamps, self.data[0], pen=(255, 0, 0, 155))
            self.plot(self.timestamps, self.data[1], pen=(0, 255, 0, 155))
            self.plot(self.timestamps, self.data[2], pen=(0, 0, 255, 155))
            ## setting pen=(i,3) automaticaly creates three different-colored pens
            #self.plot(self.timestamps, self.data, pen=(i,3))  ## setting pen=(i,3) automaticaly creates three different-colored pens


