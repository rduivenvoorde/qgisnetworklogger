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


from qgis.PyQt.QtCore import (
    QCoreApplication,
    Qt
)
from qgis.PyQt.QtGui import (
    QIcon,
    QKeySequence
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QMessageBox,
    QShortcut
)

from .ui import NetworkActivityDock
from .model import ActivityModel

import os

# Create the logger for this QgisNetworkLogger plugin
import logging
from . import LOGGER_NAME
log = logging.getLogger(LOGGER_NAME)

class QgisNetworkLogger:
    '''
    The Actual QgisNetworkLogger plugin
    '''

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface

        # don't wait for GUI to start logging...
        self.logger = ActivityModel()
        self.dock = None

    def initGui(self):
        # Create action that will start the plugin
        self.action = QAction(QIcon(os.path.dirname(__file__) + '/icons/icon.png'), '&QGIS Network Logger',
                              self.iface.mainWindow())
        # connect the action to the run method
        #self.action.triggered.connect(self.show_dialog)
        self.action.triggered.connect(self.toggle_dock)
        # Add menu item
        self.iface.addPluginToMenu('QGIS Network Logger', self.action)
        self.iface.addToolBarIcon(self.action)

        # Create a shortcut (not working after reload ??)
        self.f12 = QKeySequence("F12")
        self.show_dock_shortcut = QShortcut(self.f12, self.iface.mainWindow())
        self.show_dock_shortcut.activated.connect(self.toggle_dock)

    def unload(self):
        # Remove the plugin menu item and button
        self.iface.removePluginMenu('QGIS Network Logger', self.action)
        self.iface.removeToolBarIcon(self.action)

        # trying to remove shortcut...
        self.show_dock_shortcut.activated.disconnect(self.toggle_dock)
        del self.show_dock_shortcut

        if self.dock:
            self.iface.removeDockWidget(self.dock)

    def toggle_dock(self):
        # show/hide the dock with the Treeview
        if not self.dock:
            self.dock = NetworkActivityDock(self.logger)
            self.dock.setObjectName('NetworkActivityDock')
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        else:
            self.dock.toggleUserVisible()

    def show_dialog(self):
        # this was a warning, not sure if we want to show it...
        QMessageBox.information(
            self.iface.mainWindow(),
            QCoreApplication.translate('QGISNetworkLogger', 'QGIS Network Logger'),
            QCoreApplication.translate('QGISNetworkLogger', 'See LogMessages Panel.\n\n'
                                                            'Note that not ALL messages are seen here...\n\n'
                                                            'Only listening to the requestAboutToBeCreated and requestTimedOut signals.\n\n'
                                                            'if you want more: see code'))
        self.toggle_dock()
        return
