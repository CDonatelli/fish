#!/usr/bin/python

import os
import sys
import time
import serial
import struct
import random
import array
from PyQt4.QtCore import *

class Am_rx(QObject):

    COM_FLAG                   = 0x7E
    COM_ESCAPE                 = 0X7D
    COM_XOR                    = 0X20
    COM_MAX_PACKET_LENGTH      = 500


    GYRO_SENSITIVITY           = 131     # if range is +- 250
    ACCEL_SENSITIVITY          = 16384   # if range is +- 2

    #PLOT_REFRESH_RATE         = 5
    PLOT_REFRESH_RATE          = 40      # dividable by 4

    DATA_LENGTH = 42

    MAGNETOMETER_SCALE_FACTOR  =   0.15
    WHO_AM_I                   =   0x71

    mag_0_asa = [1, 1, 1]
    mag_1_asa = [1, 1, 1]

    finished_signal = pyqtSignal()
    message_signal = pyqtSignal(QString)
    error_signal = pyqtSignal(QString)

    timestamp_signal = pyqtSignal(float)
    plot_a1_signal = pyqtSignal(float, list, bool)
    plot_a2_signal = pyqtSignal(float, list, bool)
    plot_g1_signal = pyqtSignal(float, list, bool)
    plot_g2_signal = pyqtSignal(float, list, bool)


    def __init__(self, parent = None):
        super(Am_rx, self).__init__(parent)

        self.recording = False

        self.data = []
        self.end_timestamp = 'inf'

        #self.use_trigger
        #self.pre_trigger
        #self.post_trigger



    def calculate_accel_ft(self, a_test):
        # SEE MPU-6000, 6050 MANUAL PAGE 11
        # DON'T NEGATE Y-AXIS VALUE
        if (a_test == 0):
            return 0
        else:
            exponent = (a_test - 1) / 30
            return (1392.64 * ((0.092 ** exponent) / 0.34))


    def calculate_gyro_ft(self, g_test):
        # SEE MPU-6000, 6050 MANUAL PAGE 10
        # FOR Y-AXIS, NEGATE RETURN VALUE
        if (g_test == 0):
            return 0
        else:
            return (3275 * (1.046 ** (g_test - 1)))


    def self_test(self):
        # GYRO RANGE SHOULD BE +=8g (MPU6050)
        # ACCEL RANGE SHOULD BE +=250dps (MPU6050)
        pass


    def cleanup(self):
        self.message_signal.emit("closing serial connection")
        self.connection.close()

    def tx_byte(self, val):
        self.connection.write(struct.pack('!c', val))
        
    def rx_byte(self):
        val = self.connection.read(1)
        if (len(val) == 0):
            return None
        else:
            return ord(val)

    # READ A PACKAGE FROM SERIAL AND RETURN ITS CONTENTS
    # IF TIMEOUT, RETURN AN EMPTY LIST
    def rx_packet(self):
        message = []
        val = None

        while (val != Am_rx.COM_FLAG):
            val = self.rx_byte()
            if (val == None):
                print "rx packet failed A"
                return []

        val = self.rx_byte()
        if (val == None):
            print "rx packet failed B"
            return []

        if (val == Am_rx.COM_FLAG):
            val = self.rx_byte()
            if (val == None):
                print "rx packet failed E"
                return []

        while (val != Am_rx.COM_FLAG):
            if (val == Am_rx.COM_ESCAPE):
                val = self.rx_byte()
                if (val == None):
                    print "rx packet failed C"
                    return []
                val = val ^ Am_rx.COM_XOR
            message.append(val)
            val = self.rx_byte()
            if (val == None):
                print "rx packet failed D"
                return []

        return message






    @pyqtSlot()
    def run(self):

        self.message_signal.emit("establishing serial connection... ")

        try:
            self.connection = serial.Serial(
                port     = '/dev/ttyACM0' if (os.name == 'posix') else 'COM1',
                baudrate = 115200,
                parity   = serial.PARITY_NONE,
                stopbits = serial.STOPBITS_ONE,
                bytesize = serial.EIGHTBITS,
               #timeout  = None   # block, wait forever
               #timeout  = 0      # non-blocking, return immedietly up to number of requested bytes
                timeout  = 1.0    # 1 second timeout 
            )

        except serial.serialutil.SerialException:
            self.error_signal.emit("FAILED\n")
            self.finished_signal.emit()
            return

        self.message_signal.emit("OK\n")

        self.message_signal.emit("waiting for arduino to reset\n")
        time.sleep(3)

        self.message_signal.emit("initializing imus\n")
        self.tx_byte('i')



        received = []
        while ((len(received) == 0) or (received != [Am_rx.WHO_AM_I, Am_rx.WHO_AM_I])):
            self.message_signal.emit("reading imu whoamis... ")
            self.tx_byte('w')
            received = self.rx_packet()
            if (received == [Am_rx.WHO_AM_I, Am_rx.WHO_AM_I]):
                self.message_signal.emit("OK\n")
            elif (len(received) == 0):
                self.error_signal.emit("FAILED (timeout)\n")
            elif (received != [Am_rx.WHO_AM_I, Am_rx.WHO_AM_I]):
                self.error_signal.emit("FAILED (values read: " + ', '.join(map(str, received)) + ")\n")





        self.message_signal.emit("calculating magnetometer sensitivty adjustment... ")
        self.tx_byte('m')
        received = self.rx_packet()

        if (len(received) == 6):
            for i in (range(0, 3)):
                Am_rx.mag_0_asa[i] = ((float(received[i]     - 128) / 256) + 1) * Am_rx.MAGNETOMETER_SCALE_FACTOR
                Am_rx.mag_1_asa[i] = ((float(received[i + 3] - 128) / 256) + 1) * Am_rx.MAGNETOMETER_SCALE_FACTOR
            self.message_signal.emit("OK\n")
            self.message_signal.emit("mag_0 asa: " + ', '.join(map(str, Am_rx.mag_0_asa)) + "\n")
            self.message_signal.emit("mag_1 asa: " + ', '.join(map(str, Am_rx.mag_1_asa)) + "\n")

        else:
            self.error_signal.emit("FAILED\n")
            self.error_signal.emit("using 1 adjustment\n")


        self.tx_byte('r')
        #self.message_signal.emit("waiting to stabilize\n")
        #for i in range(0, 100):
        #    self.rx_packet()

        self.message_signal.emit("recording data\n")

        # RESET TIMER
        start_time = time.time() * 1000

        sample_index = 0
        self.data = []

        while (self.recording):

            received = self.rx_packet()
            if (len(received) == Am_rx.DATA_LENGTH):
                received = array.array('B', received).tostring()
                # print map(ord, received)
                (id, enc, ax1, ay1, az1, gx1, gy1, gz1, mx1, my1, mz1, ax2, ay2, az2, gx2, gy2, gz2, mx2, my2, mz2) = struct.unpack('!Lhhhhhhhhhhhhhhhhhhh', received)
                timestamp = (time.time() * 1000) - start_time

                # CONVERT
                (ax1, ay1, az1, ax2, ay2, az2) = map(lambda x: float(x) / Am_rx.ACCEL_SENSITIVITY, (ax1, ay1, az1, ax2, ay2, az2))
                (gx1, gy1, gz1, gx2, gy2, gz2) = map(lambda x: float(x) / Am_rx.GYRO_SENSITIVITY,  (gx1, gy1, gz1, gx2, gy2, gz2))
                (mx1, my1, mz1) = [(mx1, my1, mz1)[i] * Am_rx.mag_0_asa[i] for i in range(3)]
                (mx2, my2, mz2) = [(mx2, my2, mz2)[i] * Am_rx.mag_1_asa[i] for i in range(3)]
                enc *= 0.3515625  # 360/1024

                # TO PIPE TO FILE
                #print enc

                #print(' '.join(map(str, [id, enc, ax1, ay1, az1, gx1, gy1, gz1, mx1, my1, mz1, ax2, ay2, az2, gx2, gy2, gz2, mx2, my2, mz2])));
                print('\t'.join(map(str, [mx1, my1, mz1, mx2, my2, mz2])));

                entry = {}
                entry['time']    = timestamp
                entry['encoder'] = enc
                entry['accel1']  = [ax1, ay1, az1]
                entry['gyro1']   = [gx1, gy1, gz1]
                entry['mag1']    = [mx1, my1, mz1]
                entry['accel2']  = [ax2, ay2, az2]
                entry['gyro2']   = [gx2, gy2, gz2]
                entry['mag2']    = [mx2, my2, mz2]

                self.data.append(entry)
                sample_index += 1

                self.timestamp_signal.emit(timestamp)

                #refresh = (sample_index % Am_rx.PLOT_REFRESH_RATE) == 0

                count = sample_index % Am_rx.PLOT_REFRESH_RATE
                self.plot_a1_signal.emit(timestamp, [ax1, ay1, az1],  count == 0)
                self.plot_a2_signal.emit(timestamp, [ax2, ay2, az2],  count == Am_rx.PLOT_REFRESH_RATE * .25)

                self.plot_g1_signal.emit(timestamp, [gx1, gy1, gz1],  count == Am_rx.PLOT_REFRESH_RATE * .5)
                self.plot_g2_signal.emit(timestamp, [gx2, gy2, gz2],  count == Am_rx.PLOT_REFRESH_RATE * .75)

                #self.plot_a1_signal.emit(timestamp, [mx1, my1, mz1],  count == 0)
                #self.plot_a2_signal.emit(timestamp, [mx2, my2, mz2],  count == Am_rx.PLOT_REFRESH_RATE * .25)


        self.tx_byte('s')

        # UNWRAP DATA SO IT CAN BE PROCESSED OR SAVED
        #self.data = self.data[sample_index:] + self.data[:sample_index]

        self.finished_signal.emit()




