# -----------------------------------------------------------
# Copyright (C) 2015 Martin Dobias
# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# ---------------------------------------------------------------------

from qgis.PyQt.QtCore import (
    QModelIndex,
    Qt
)
from qgis.PyQt.QtWidgets import (
    QTreeView,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QAction,
    QMenu
)
from qgis.PyQt.QtGui import (
    QFont
)
from qgis.gui import (
    QgsDockWidget,
    QgsFilterLineEdit
)
from qgis.utils import (
    iface
)

from .model import ActivityProxyModel

# get the logger for this QgisNetworkLogger plugin
import logging
from . import LOGGER_NAME
log = logging.getLogger(LOGGER_NAME)

class ActivityView(QTreeView):
    """
    The actual 'view' of all Request is this QTreeView, backed by
    the ActivityModel(a QAbstractItemModel).
    The model is wrapped in a proxy model to be able to search/filter.
    """

    def __init__(self, logger, parent=None):
        super().__init__(parent)
        self.model = logger
        self.proxy_model = ActivityProxyModel(self.model, self)
        self.setModel(self.proxy_model)

        self.expanded.connect(self.item_expanded)

        self.model.rowsInserted.connect(self.rows_inserted)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

    def item_expanded(self, index):
        """Slot to be called after expanding an ActivityView item.
        If the item is a Request item, open all children (show ALL info of it)
        We want to scroll to last request

        :param index:
        """
        # only expand all children on Request Nodes (which NOT have a valid parent)
        if not index.parent().isValid():
            self.expand_children(index)
            # upon expanding a request row, resize first column to fully readable size:
            #self.setColumnWidth(0, self.sizeHintForColumn(0))
        # make ALL request information visible by scrolling view to it
        self.scrollTo(index)

    def expand_children(self, index):
        """Expand all children of this item defined by index

        :param index: from where to expand all children
        :type index: QModelIndex
        """
        if not index.isValid():
            return
        count = index.model().rowCount(index)
        for i in range(0, count):
            child_index = index.child(i, 0)
            self.expand_children(child_index)
        if not self.isExpanded(index):
            self.expand(index)

    def rows_inserted(self, parent, first, last):
        # always make the last line visible
        self.scrollToBottom()

    def clear(self):
        self.model.clear()

    def pause(self, state):
        self.model.pause(state)

    def set_filter_string(self, string):
        self.proxy_model.set_filter_string(string)

    def show_successful(self, show):
        self.proxy_model.set_show_successful(show)

    def show_timeouts(self, show):
        self.proxy_model.set_show_timeouts(show)

    # do we actually want a 'Clear' context menu item in EVERY node???
    def context_menu(self, point):
        proxy_model_index = self.indexAt(point)
        if self.proxy_model:
            index = self.proxy_model.mapToSource(proxy_model_index)
        else:
            index = proxy_model_index
        if index.isValid():
            menu = QMenu()
            populated = False
            for a in index.internalPointer().actions():
                menu.addAction(a)
                populated = True
            if populated:
                menu.addSeparator()

            clear_action = QAction('Clear')
            clear_action.triggered.connect(self.clear)
            menu.addAction(clear_action)
            menu.exec(self.viewport().mapToGlobal(point))


class NetworkActivityDock(QgsDockWidget):
    """
    The Dock holding the actual treeview.
    Also having some buttons to clear/pause and filter the requests.
    """

    def __init__(self, logger):
        super().__init__()
        self.setWindowTitle('Network Activity')

        self.view = ActivityView(logger)
        font = QFont()
        font.setFamily('Courier')
        font.setPointSize(font.pointSize()-1)
        self.view.setFont(font)
        self.logger = logger

        self.l = QVBoxLayout()
        self.l.setContentsMargins(0, 0, 0, 0)

        self.clear_action = QAction('Clear')
        self.pause_action = QAction('Pause')
        self.pause_action.setCheckable(True)

        self.toolbar = QToolBar()
        self.toolbar.setIconSize(iface.iconSize(True))
        self.toolbar.addAction(self.clear_action)
        self.toolbar.addAction(self.pause_action)

        self.clear_action.triggered.connect(self.view.clear)
        self.pause_action.toggled.connect(self.view.pause)
        self.show_success_action = QAction('Show successful requests')
        self.show_success_action.setCheckable(True)
        self.show_success_action.setChecked(True)
        self.show_success_action.toggled.connect(self.view.show_successful)
        self.show_timeouts_action = QAction('Show timeouts')
        self.show_timeouts_action.setCheckable(True)
        self.show_timeouts_action.setChecked(True)
        self.show_timeouts_action.toggled.connect(self.view.show_timeouts)
        self.show_remove1_action = QAction('Remove One')
        self.show_remove1_action.triggered.connect(self.logger.remove_one)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.show_success_action)
        self.toolbar.addAction(self.show_timeouts_action)
        self.toolbar.addAction(self.show_remove1_action)

        self.filter_line_edit = QgsFilterLineEdit()
        self.filter_line_edit.setShowSearchIcon(True)
        self.filter_line_edit.setPlaceholderText('Filter requests')
        self.filter_line_edit.textChanged.connect(self.view.set_filter_string)
        self.l.addWidget(self.toolbar)
        self.l.addWidget(self.filter_line_edit)
        self.l.addWidget(self.view)
        self.w = QWidget()
        self.w.setLayout(self.l)
        self.setWidget(self.w)
