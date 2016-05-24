#!/usr/bin/env python

# USE PYTHON 2.6 OR LATER

import sys
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from am_rx import *
from am_plot import *
from am_settings import *
from collections import namedtuple
import time
import h5py


class Am_ui(QWidget):

    # DISPLAYED IN WINDOW HEADER AND SUCH
    APPLICATION_NAME = 'IMU Collect 0.01'

    # SIGNAL TO RESETS ALL THE PLOTS
    clear_plots_signal = pyqtSignal()
    

    def __init__(self, parent = None):
        super(Am_ui, self).__init__(parent)



	########################
        #       VARIABLES      #
	########################

	# HAS THE COLLECTED DATA BEEN SAVED TO FILE?
        self.data_saved = True

	# CURRENTLY RECORDING DATA?
        self.recording = False

	# IF FALSE, RECORD BUTTON TO START AND STOP RECORDING
	# IF TRUE, SECOND CLICK CAPTURES DATA IN RANGE FROM PRE TO POST DELAY.
        self.use_trigger = False
        self.pre_trigger_delay = 10
        self.post_trigger_delay = 10

	# ALL THE BUTTONS IN THE MAIN WINDOW
        self.buttons = {}

	# COLLECTED DATA.
	# WILL CONTAIN 5 LISTS (ACCEL1, ACCEL2, GYRO1, GYRO2, TIME)
        self.data = {}

	# TIMESTAMPS OF COLLECTED DATA.
	# am_rx.py WILL PUT THE SAME DATA IN HERE AND IN self.data['time']
        # KIND OF REDUNDANT, BUT THIS IS REALLY FOR THE PROGRAM TO KEEP TRACK OF
	# TIME, E.G. FOR TRIGGERS, self.data IS STORING IMU DATA FOR SAVING.
        self.timestamps   = []

	# NUMBER OF SAMPLES COLLECTED
        self.num_samples = 0

	# HOLD ALL VISUAL ELEMENTS IN GUI MAIN WINDOW
        top_layout = QGridLayout()



	##################################################
        #   CREATE GUI ELEMENTS AND ADD TO MAIN WINDOW   #
	##################################################
        

	# CREATE BUTTONS AND ADD TO BUTTON LAYOUT

        button_layout = QVBoxLayout()
        self.button_container = QWidget()
        self.button_container.setLayout(button_layout)

        self.buttons['test'] = QPushButton('Test')
        self.buttons['test'].setToolTip('Check communication with arduino and IMUs, run IMU self tests')
        button_layout.addWidget(self.buttons['test'])

        self.buttons['record'] = QPushButton('Record')
        self.buttons['record'].setToolTip('Begin recording samples')
        self.buttons['record'].clicked.connect(self.record_button_slot)
        button_layout.addWidget(self.buttons['record'])

        self.buttons['save'] = QPushButton('Save')
        self.buttons['save'].setToolTip('Save recorded data')
        self.buttons['save'].clicked.connect(self.save_button_slot)
        button_layout.addWidget(self.buttons['save'])
        self.buttons['save'].setEnabled(False)

        self.buttons['settings'] = QPushButton('Settings')
        self.buttons['settings'].clicked.connect(self.settings_button_slot)
        button_layout.addWidget(self.buttons['settings'])

        self.buttons['quit'] = QPushButton('Quit')
        self.buttons['quit'].clicked.connect(self.quit_button_slot)
        button_layout.addWidget(self.buttons['quit'])


        # TEXT DISPLAY

        self.text_window = QTextEdit()
        self.text_window.setReadOnly(True)


        # GRAPHS

        self.plot_a1 = Am_plot()
        self.plot_a2 = Am_plot()
        self.plot_g1 = Am_plot()
        self.plot_g2 = Am_plot()


        # STATUS INFO
	# CURRENTLY THIS IS TEXT APPEARING THE LOWER RIGHT CORNER.

        stats_layout = QGridLayout()
        self.stats_num_samples = QLabel("0")
        self.stats_time = QLabel("0")
        stats_layout.addWidget(QLabel("Samples: "), 1, 1)
        stats_layout.addWidget(QLabel("Time: "), 2, 1)
        stats_layout.addWidget(self.stats_num_samples, 1, 2)
        stats_layout.addWidget(self.stats_time, 2, 2)
        stats_layout.setColumnMinimumWidth(2, 120)


        # ADD WIDGETS TO LAYOUT

        top_layout.addWidget(self.button_container, 1, 3, 2, 1)

        top_layout.addLayout(stats_layout, 3, 3)

        top_layout.addWidget(self.plot_a1, 1, 1)
        top_layout.addWidget(self.plot_g1, 1, 2)
        top_layout.addWidget(self.plot_a2, 2, 1)
        top_layout.addWidget(self.plot_g2, 2, 2)

        top_layout.addWidget(self.text_window, 3, 1, 1, 2)
        

        # GRAPH LABELS

        label = QtGui.QLabel("IMU 1")
        label.setAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignCenter)
        top_layout.addWidget(label, 0, 1)

        label = QtGui.QLabel("IMU 2")
        label.setAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignCenter)
        top_layout.addWidget(label, 0, 2)

        label = QtGui.QLabel("Accel.")
        label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)
        top_layout.addWidget(label, 1, 0)

        label = QtGui.QLabel("Gyro.")
        label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter)
        top_layout.addWidget(label, 2, 0)


        # ADD TOP LEVEL LAYOUT
        self.setLayout(top_layout)


	# SET WINDOW TITLE
        self.setWindowTitle(Am_ui.APPLICATION_NAME) 



	##################################################
        #   SET UP SEPARATE THREAD FOR RECEIVING DATA    #
	##################################################

        self.receiver_thread = QThread()
        self.receiver = Am_rx()
        self.receiver.moveToThread(self.receiver_thread)



	########################
        #    QT CONNECTIONS    #
	########################

        self.clear_plots_signal.connect(self.plot_a1.clear_slot)
        self.clear_plots_signal.connect(self.plot_a2.clear_slot)
        self.clear_plots_signal.connect(self.plot_g1.clear_slot)
        self.clear_plots_signal.connect(self.plot_g2.clear_slot)

        self.receiver.finished_signal.connect(self.receiver_thread.quit)

	# USE TO TEST WITHOUT ARDUINO, RANDOMLY GENERATED DATA
        #self.receiver_thread.started.connect(self.receiver.run_fake)

	# COLLECT DATA FROM Am_rx() i.e. from arduino
        self.receiver_thread.started.connect(self.receiver.run)

        self.receiver_thread.finished.connect(self.receiver_done)

        self.receiver.timestamp_signal.connect(self.timestamp_slot)
        self.receiver.plot_a1_signal.connect(self.plot_a1.data_slot)
        self.receiver.plot_a2_signal.connect(self.plot_a2.data_slot)
        self.receiver.plot_g1_signal.connect(self.plot_g1.data_slot)
        self.receiver.plot_g2_signal.connect(self.plot_g2.data_slot)

        self.receiver.message_signal.connect(self.message_slot)
        self.receiver.error_signal.connect(self.error_slot)



############################################
#              BUTTON SLOTS                #
############################################

    def quit_button_slot(self):
        result = (QMessageBox.question(self,
                                       Am_ui.APPLICATION_NAME,
                                       'Really quit?',
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.Yes))

        if (result == QMessageBox.Yes):
            self.stop_recording()
            time.sleep(.2)  # let thread finish
            self.message_slot("exiting")
            self.close()


    def record_button_slot(self):
        if (self.recording):
            if (self.use_trigger):
                self.stop_recording_time = self.timestamps[-1] + (self.post_trigger_delay * 1000)
            else:
                self.stop_recording_time = self.timestamps[-1]
        else:
            if (not self.data_saved):
                result = (QMessageBox.question(self,
                                               'Message',
                                               'Overwrite recorded data without saving?',
                                               QMessageBox.Yes | QMessageBox.No,
                                               QMessageBox.No))

            if (self.data_saved or (result == QMessageBox.Yes)):
                self.num_samples = 0
                self.stop_recording_time = float("inf")
                self.record()


    def save_button_slot(self):
        filename = QFileDialog.getSaveFileName(self, 'Save recorded data', '', '*.hdf5')
        if filename:
            if ( (len(filename) < 5) or (filename[-5:].toLower() != '.hdf5') ):
                filename += '.hdf5'

            datafile = h5py.File(str(filename), 'w')
            save_data = datafile.create_group("data")
            save_data.create_dataset('t',      data=self.data['time'])
            save_data.create_dataset('Accel',  data=self.data['accel1'])
            save_data.create_dataset('Accel2', data=self.data['accel2'])
            save_data.create_dataset('Gyro',   data=self.data['gyro1'])
            save_data.create_dataset('Gyro2',  data=self.data['gyro2'])
            datafile.close()

            self.message_slot("data saved to  " + filename)
            self.data_saved = True
            #self.buttons['save'].setEnabled(False)


    def settings_button_slot(self):
        settings = Am_settings(self)
        settings.show()



############################################
#               OTHER SLOTS                #
############################################

    # CALLED WHEN REVEIVER THREAD FINISHES
    def receiver_done(self):
        self.recording = False
        self.buttons['record'].setText('Record')
        self.buttons['record'].setToolTip('Begin recording samples')
        self.buttons['save'].setEnabled(len(self.timestamps) > 0)
        self.buttons['settings'].setEnabled(True)
        self.buttons['test'].setEnabled(True)


    # CALLED BY am_rx.py FOR EVERY SAMPLE
    def timestamp_slot(self, timestamp):

        self.timestamps.append(timestamp)

        self.stats_time.setText('%.1f' % (timestamp))

        self.num_samples += 1
        self.stats_num_samples.setText(str(self.num_samples))

        if (timestamp >= self.stop_recording_time):
            self.stop_recording()


    # CONVENIENCE FUNCTION TO CALL MESSAGE_SLOT WITH RED TEXT
    def error_slot(self, the_string):
        self.message_slot(the_string, True)


    # CALLED BY ANYONE TO DISPLAY TEXT IN TEXT WINDOW
    def message_slot(self, the_string, red=False):
        self.text_window.setTextColor(QtGui.QColor(120, 120, 120))
        self.text_window.insertPlainText("\n" + time.strftime("%c") + "    ")

        if (red):
            self.text_window.setTextColor(QtGui.QColor(255,0,0))
        else:
            self.text_window.setTextColor(QtGui.QColor(0,0,0))
        self.text_window.insertPlainText(the_string)
        sb = self.text_window.verticalScrollBar();
        sb.setValue(sb.maximum());



############################################
#         OTHER FUNCTIONS (NOT SLOTS)      #
############################################


    # START RECORDING DATA
    def record(self):
        self.recording = True
        self.receiver.recording = True
        self.data_saved = False

        if (self.use_trigger):
            self.buttons['record'].setText('Trigger')
        else:
            self.buttons['record'].setText('Stop')

        self.buttons['record'].setToolTip('Stop recording samples')

        self.buttons['save'].setEnabled(False)
        self.buttons['settings'].setEnabled(False)
        self.buttons['test'].setEnabled(False)

        self.timestamps  = []
        self.data_accel1 = []
        self.data_accel2 = []
        self.data_gyro1  = []
        self.data_gyro2  = []

        self.clear_plots_signal.emit()

        self.receiver_thread.start()


    # STOP RECORDING DATA
    # THE QUIT BUTTON SLOT CALLS THIS FUNCTION
    # THIS FUNCTION SETS A FLAG, CAUSING THE am_rx.py PROCESS TO HALT
    # THAT WILL CAUSE THE receiver_done SLOT TO EXECUTE,
    # WHICH WILL FINISH UP STOP RECORDING DUTIES.
    def stop_recording(self):
        self.data = self.receiver.data
        self.receiver.recording = False

                                          
def main():
    app = QApplication(sys.argv)
    ex = Am_ui()
    ex.show()
    sys.exit(app.exec_())
          
if __name__ == '__main__':
    main()
