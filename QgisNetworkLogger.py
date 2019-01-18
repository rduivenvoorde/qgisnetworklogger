# -*- coding: utf-8 -*-
# Import the PyQt and QGIS libraries
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *

from qgis.PyQt.QtNetwork import QNetworkRequest

import os

class QgisNetworkLogger:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # get the handle of the (singleton?) QgsNetworkAccessManager instance
        self.nam = QgsNetworkAccessManager.instance()

    def initGui(self):
        # Create action that will start plugina
        self.action = QAction(QIcon(os.path.dirname(__file__)+'/icons/icon.png'), '&QGIS Network Logger', self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.show_dialog)

        # Add menu item
        self.iface.addPluginToMenu('QGIS Network Logger', self.action)

        self.log_it()

    def unload(self):
        # Remove the plugin menu item
        self.iface.removePluginMenu('QGIS Network Logger',self.action)
        self.nam.requestAboutToBeCreated.connect(self.request_about_to_be_created)
        self.nam.requestCreated.connect(self.request_created)
        self.nam.requestTimedOut.connect(self.request_timeout)
        self.nam.request_finished.connect(self.request_finished)


    def show_dialog(self):
        QMessageBox.information(
            self.iface.mainWindow(),
            QCoreApplication.translate('QGISNetworkLogger', 'QGIS Network Logger'),
            QCoreApplication.translate('QGISNetworkLogger', 'See LogMessages Panel.\n\n'
                                                            'Note that not ALL messages are seen here...\n\n'
                                                            'Only listening to the requestAboutToBeCreated and requestTimedOut signals.\n\n'
                                                            'if you want more: see code'))
        return

    def log_it(self):
        self.nam.requestAboutToBeCreated.connect(self.request_about_to_be_created)
        #self.nam.requestCreated.connect(self.request_created)
        self.nam.requestTimedOut.connect(self.request_timeout)
        #self.nam.finished.connect(self.request_finished)

    def show(self, msg):
        #print(msg)
        QgsMessageLog.logMessage(msg, "QGIS Network Logger...", Qgis.MessageLevel.Info)

    def request_about_to_be_created(self, operation, request, data):
        op = "Custom"
        if operation == 1: op = "HEAD"
        elif operation == 2: op = "GET"
        elif operation == 3: op = "PUT"
        elif operation == 4: op = "POST"
        elif operation == 5: op = "DELETE"
        # PyQt5.QtNetwork.QNetworkRequest
        url = request.url().url()
        self.show('Requesting: {} <a href="{}">{}</a>'.format(op, url, url))
        if data is not None:
            self.show("- Request data: {}".format(data))


    def request_timeout(self, reply):
        url = reply.url().url()
        self.show('# Timeout or abort: <a href="{}">{}</a>'.format(url, url))

    def request_created(self, reply):
        if reply is not None:
            self.show('# Request created: "{}"'.format(reply.url()))

    def request_finished(self, reply):
        url = reply.url().url()
        self.show('Finished: - <a href="{}">{}</a>'.format(url, url))
        self.show('- ContentType={} ContentLength={} finished={} running={}'.format(
            reply.header(QNetworkRequest.ContentTypeHeader),
            reply.header(QNetworkRequest.ContentLengthHeader),
            reply.isFinished(),
            reply.isRunning()))
        if reply.header(QNetworkRequest.LocationHeader) is not None:
            self.show('- LocationHeader:{}'.format(reply.header(QNetworkRequest.LocationHeader)))
        #print("headerlist: ", reply.rawHeaderList())

