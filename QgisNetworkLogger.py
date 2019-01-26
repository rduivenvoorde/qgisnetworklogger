# -*- coding: utf-8 -*-
# -----------------------------------------------------------
# Copyright (C) 2019 Richard Duivenvoorde, Nyall Dawson
# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# ---------------------------------------------------------------------

from qgis.core import (
    QgsNetworkAccessManager,
    QgsNetworkReplyContent,
    QgsNetworkRequestParameters,
    QgsMessageLog,
    Qgis
)
from qgis.PyQt.QtCore import (
    QCoreApplication,
    Qt
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QMessageBox
)
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply

from .log_dock_widget import NetworkActivityDock

import os

class QgisNetworkLogger:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # get the handle of the (singleton?) QgsNetworkAccessManager instance
        self.nam = QgsNetworkAccessManager.instance()
        # TODO put in gui/settings
        self.show_request_headers = True
        self.show_response_headers = True
        self.dock = None
        #import pydevd
        #pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True)

    def initGui(self):
        # Create action that will start plugina
        self.action = QAction(QIcon(os.path.dirname(__file__)+'/icons/icon.png'), '&QGIS Network Logger', self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.show_dialog)
        # Add menu item
        self.iface.addPluginToMenu('QGIS Network Logger', self.action)
        self.dock = NetworkActivityDock()
        self.dock.setObjectName('NetworkActivityDock')
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.log_it()

    def unload(self):
        # Remove the plugin menu item
        self.iface.removePluginMenu('QGIS Network Logger',self.action)

        try:
            self.nam.requestTimedOut[QgsNetworkRequestParameters].disconnect(self.request_timed_out)
        except:
            self.show("Unloading plugin, disconnecting 'requestTimedOut'-signal failed, probably not connected.")
        self.iface.removeDockWidget(self.dock)

    def log_it(self):
        self.nam.requestTimedOut[QgsNetworkRequestParameters].connect(self.request_timed_out)

    def show_dialog(self):
        QMessageBox.information(
            self.iface.mainWindow(),
            QCoreApplication.translate('QGISNetworkLogger', 'QGIS Network Logger'),
            QCoreApplication.translate('QGISNetworkLogger', 'See LogMessages Panel.\n\n'
                                                            'Note that not ALL messages are seen here...\n\n'
                                                            'Only listening to the requestAboutToBeCreated and requestTimedOut signals.\n\n'
                                                            'if you want more: see code'))
        return

    def show(self, msg):
        QgsMessageLog.logMessage(msg, "QGIS Network Logger...", Qgis.Info)

    # request_params = QgsNetworkRequestParameters
    def request_timed_out(self, request_params):
        url = request_params.request().url().url()
        thread_id = request_params.originatingThreadId()
        request_id = request_params.requestId()
        #self.show('Timeout or abort: <a href="{}">{}</a>'.format(url, url))
        self.show('Timeout or abort {} in thread {}'.format(request_id, thread_id))
