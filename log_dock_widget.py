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
    QAbstractItemModel,
    QSortFilterProxyModel,
    QModelIndex,
    Qt,
    QUrlQuery
)
from qgis.PyQt.QtWidgets import (
    QApplication,
    QTreeView,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QAction,
    QMenu
)
from qgis.PyQt.QtGui import (
    QBrush,
    QFont,
    QColor,
    QDesktopServices
)
from qgis.PyQt.QtNetwork import (
    QNetworkAccessManager,
    QNetworkRequest,
    QNetworkReply
)
from qgis.gui import (
    QgsDockWidget,
    QgsFilterLineEdit
)
from qgis.core import (
    QgsNetworkAccessManager,
    QgsNetworkReplyContent,
    QgsNetworkRequestParameters
)
from qgis.utils import iface

STATUS_ROLE = Qt.UserRole + 1

PENDING = 'PENDING'
COMPLETE = 'COMPLETE'
ERROR = 'ERROR'
CANCELED = 'CANCELED'


class ActivityTreeItem(object):

    def __init__(self, name, parent=None):
        self.name = name
        self.populated_children = False

        self.parent = parent
        self.children = []
        self.status = COMPLETE
        if parent:
            parent.children.append(self)

    def span(self):
        return False

    def text(self, column):
        return ''

    def tooltip(self, column):
        return self.text(column)

    def createWidget(self):
        return None

    def actions(self):
        return []

    def operation2string(self, operation):
        """ Create http-operation String from Operation

        :param operation: QNetworkAccessManager.Operation
        :return: string
        """
        op = "Custom"
        if operation == QNetworkAccessManager.HeadOperation:
            op = "HEAD"
        elif operation == QNetworkAccessManager.GetOperation:
            op = "GET"
        elif operation == QNetworkAccessManager.PutOperation:
            op = "PUT"
        elif operation == QNetworkAccessManager.PostOperation:
            op = "POST"
        elif operation == QNetworkAccessManager.DeleteOperation:
            op = "DELETE"
        return op


class RootItem(ActivityTreeItem):
    def __init__(self, parent=None):
        super().__init__('', parent)


class RequestParentItem(ActivityTreeItem):

    def __init__(self, request, parent=None):
        super().__init__('', parent)
        self.url = request.request().url()
        self.operation = self.operation2string(request.operation())
        self.headers = []
        self.data = request.content().data().decode('utf-8')
        for header in request.request().rawHeaderList():
            self.headers.append(
                (header.data().decode('utf-8'),
                 request.request().rawHeader(header).data().decode('utf-8')))

        RequestItem(request, self)

        self.status = PENDING

        self.open_url_action = QAction('Open URL')
        self.open_url_action.triggered.connect(self.open_url)

        self.copy_as_curl_action = QAction('Copy as cURL')
        self.copy_as_curl_action.triggered.connect(self.copy_as_curl)

    def span(self):
        return True

    def text(self, column):
        if column == 0:
            return '{} {}'.format(self.operation, self.url.url())
        return ''

    def open_url(self):
        QDesktopServices.openUrl(self.url)

    def copy_as_curl(self):
        """Get url + headers + data and create a full curl command
        Copy that to clipboard
        """
        curl_headers = ''
        for header,value in self.headers:
            curl_headers += "-H '{}: {}' ".format(header, value)
        curl_data = ''
        if self.operation in ('POST', 'PUT'):
            curl_data = "--data '{}' ".format(self.data)
        curl_cmd =  "curl '{}' {} {}--compressed".format(self.url.url(), curl_headers, curl_data)
        QApplication.clipboard().setText(curl_cmd)

    def set_reply(self, reply):
        if reply.error() == QNetworkReply.OperationCanceledError:
            self.status = CANCELED
        elif reply.error() != QNetworkReply.NoError:
            self.status = ERROR
        else:
            self.status = COMPLETE
        ReplyItem(reply, self)

    def actions(self):
        return [self.open_url_action, self.copy_as_curl_action]

class RequestItem(ActivityTreeItem):
    def __init__(self, request, parent=None):
        super().__init__('', parent)

        self.url = request.request().url()
        self.operation = self.operation2string(request.operation())
        query = QUrlQuery(self.url)
        RequestDetailsItem('Operation', self.operation, self)
        RequestDetailsItem('Thread', request.originatingThreadId(), self)
        RequestDetailsItem('Initiator', request.initiatorClassName() if request.initiatorClassName() else 'unknown', self)
        if request.initiatorRequestId():
            RequestDetailsItem('ID', str(request.initiatorRequestId()), self)
        query_items = query.queryItems()
        if query_items:
            RequestQueryItems(query_items, self)
        RequestHeadersItem(request, self)
        if self.operation in ('POST', 'PUT'):
            PostContentItem(request, self)

    def span(self):
        return True

    def text(self, column):
        return 'Request' if column == 0 else ''


class RequestDetailsItem(ActivityTreeItem):
    def __init__(self, description, value, parent=None):
        super().__init__('', parent)

        self.description = description
        self.value = value

    def text(self, column):
        if column == 0:
            return self.description
        else:
            return self.value


class RequestHeadersItem(ActivityTreeItem):
    def __init__(self, request, parent=None):
        super().__init__('Headers', parent)

        for header in request.request().rawHeaderList():
            RequestDetailsItem(header.data().decode('utf-8'),
                               request.request().rawHeader(header).data().decode('utf-8'), self)

    def text(self, column):
        if column == 0:
            return 'Headers'
        else:
            return ''

    def span(self):
        return True

class RequestQueryItems(ActivityTreeItem):
    def __init__(self, query_items, parent=None):
        super().__init__('Query', parent)

        for item in query_items:
            RequestDetailsItem(item[0], item[1], self)

    def text(self, column):
        if column == 0:
            return 'Query'
        else:
            return ''

    def span(self):
        return True

class PostContentItem(ActivityTreeItem):
    # request = QgsNetworkRequestParameters
    def __init__(self, request, parent=None):
        super().__init__('Content', parent)

        # maybe should be &amp?
        #for p in request.content().data().decode('utf-8').split('&'):
        #    PostDetailsItem(p, self)

        data = request.content().data().decode('utf-8')
        PostDetailsItem(data, self)

    def text(self, column):
        if column == 0:
            return 'Content'
        else:
            return ''

    def span(self):
        return True

class PostDetailsItem(ActivityTreeItem):
    def __init__(self, part, parent=None):
        super().__init__('', parent)

        #self.description, self.value = part.split('=')
        self.data = part

    def text(self, column):
        if column == 0:
            return 'Data'
        else:
            return self.data


class ReplyItem(ActivityTreeItem):
    def __init__(self, reply, parent=None):
        super().__init__('', parent)
        ReplyDetailsItem('Status', reply.attribute(QNetworkRequest.HttpStatusCodeAttribute), self)
        if reply.error() != QNetworkReply.NoError:
            ReplyDetailsItem('Error Code', reply.error(), self)
            ReplyDetailsItem('Error', reply.errorString(), self)

        ReplyHeadersItem(reply, self)

    def span(self):
        return True

    def text(self, column):
        return 'Reply' if column == 0 else ''


class ReplyHeadersItem(ActivityTreeItem):
    def __init__(self, reply, parent=None):
        super().__init__('Headers', parent)

        for header in reply.rawHeaderList():
            ReplyDetailsItem(header.data().decode('utf-8'),
                             reply.rawHeader(header).data().decode('utf-8'), self)

    def text(self, column):
        if column == 0:
            return 'Headers'
        else:
            return ''

    def span(self):
        return True


class ReplyDetailsItem(ActivityTreeItem):
    def __init__(self, description, value, parent=None):
        super().__init__('', parent)

        self.description = description
        self.value = value

    def text(self, column):
        if column == 0:
            return self.description
        else:
            return self.value


class NetworkActivityModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_item = RootItem()

        self.is_paused = False

        nam = QgsNetworkAccessManager.instance()

        nam.requestAboutToBeCreated[QgsNetworkRequestParameters].connect(self.request_about_to_be_created)
        nam.finished[QgsNetworkReplyContent].connect(self.request_finished)
        nam.requestTimedOut[QgsNetworkRequestParameters].connect(self.request_timed_out)

        self.requests_items = {}
        self.request_indices = {}

    def request_about_to_be_created(self, request_params):
        self.beginInsertRows(QModelIndex(), len(self.root_item.children), len(self.root_item.children))
        self.requests_items[request_params.requestId()] = RequestParentItem(request_params, self.root_item)
        self.endInsertRows()
        self.request_indices[request_params.requestId()] = self.index(len(self.requests_items)-1,0,QModelIndex())

    def request_finished(self, reply):
        if not reply.requestId() in self.requests_items:
            return

        request_index = self.request_indices[reply.requestId()]
        request_item = self.requests_items[reply.requestId()]

        self.beginInsertRows(request_index, len(request_item.children), len(request_item.children))
        request_item.set_reply(reply)
        self.endInsertRows()

        self.dataChanged.emit(request_index,request_index)

    def request_timed_out(self, request_params):
        # TODO
        pass
        # url = request_params.request().url().url()
        # thread_id = request_params.originatingThreadId()
        # request_id = request_params.requestId()
        ##self.show('Timeout or abort: <a href="{}">{}</a>'.format(url, url))
        # self.show('Timeout or abort {} in thread {}'.format(request_id, thread_id))

    def columnCount(self, parent):
        return 2

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        parent_item = self.root_item if not parent.isValid() else parent.internalPointer()
        return len(parent_item.children)

    def data(self, index, role):
        if not index.isValid():
            return

        item = index.internalPointer()
        if role == Qt.DisplayRole:
            return item.text(index.column())
        elif role == Qt.ToolTipRole:
            return item.tooltip(index.column())
        elif role == STATUS_ROLE:
            return item.status
        elif role == Qt.ForegroundRole:
            if item.status in (PENDING, CANCELED):
                color = QColor(0, 0, 0, 100)
            elif item.status == ERROR:
                color = QColor(235, 10, 10)
            else:
                color = QColor(0, 0, 0)
            return QBrush(color)

        elif role == Qt.FontRole:
            f = QFont()
            if item.status == CANCELED:
                f.setStrikeOut(True)
            return f

    def flags(self, index):
        if not index.isValid():
            return 0
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self.root_item if not parent.isValid() else parent.internalPointer()
        child_item = parent_item.children[row]
        return self.createIndex(row, column, child_item)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        parent_item = index.internalPointer().parent
        if parent_item.parent is None:
            return QModelIndex()

        parent_index_in_grandparent = parent_item.parent.children.index(parent_item)
        return self.createIndex(parent_index_in_grandparent, 0, parent_item)

    def headerData(self, section, orientation, role):
        if section == 0 and orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return "Requests"

    def clear(self):
        self.beginResetModel()
        self.root_item = RootItem()
        self.requests_items = {}
        self.request_indices = {}
        self.endResetModel()

    def pause(self, state):
        if state == self.is_paused:
            return

        self.is_paused = state
        if self.is_paused:
            QgsNetworkAccessManager.instance().requestAboutToBeCreated[QgsNetworkRequestParameters].disconnect(self.request_about_to_be_created)
        else:
            QgsNetworkAccessManager.instance().requestAboutToBeCreated[QgsNetworkRequestParameters].connect(self.request_about_to_be_created)


class ActivityProxyModel(QSortFilterProxyModel):

    def __init__(self, source_model, parent = None):

        super().__init__(parent)
        self.source_model = source_model
        self.setSourceModel(self.source_model)
        self.filter_string = ''

    def set_filter_string(self, string):
        self.filter_string = string
        self.invalidateFilter()

    def filterAcceptsRow(self, sourceRow, sourceParent):
        item = self.source_model.index(sourceRow,0,sourceParent).internalPointer()
        if isinstance(item,RequestParentItem):
            return self.filter_string.lower() in item.url.url().lower()
        else:
            return True


class ActivityView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = NetworkActivityModel(self)
        self.proxy_model = ActivityProxyModel(self.model, self)
        self.setModel(self.proxy_model)
        self.expanded.connect(self.item_expanded)

        self.model.rowsInserted.connect(self.rows_inserted)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

        # not working
        self.setWordWrap(True);

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
            self.setColumnWidth(0, self.sizeHintForColumn(0))
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
        # silly qt API - this shouldn't be so hard!
        for r in range(first, last + 1):
            this_index = self.model.index(r, 0, parent)
            if this_index.internalPointer().span():
                proxy_index = self.proxy_model.mapFromSource(self.model.index(r, 0, parent))
                self.setFirstColumnSpanned(proxy_index.row(),proxy_index.parent(), True)
            for i in range(self.model.rowCount(this_index)):
                self.rows_inserted(this_index, i, i)

            w = this_index.internalPointer().createWidget()
            if w:
                self.setIndexWidget(this_index, w)
        # always make the last line visible
        self.scrollToBottom()

    def clear(self):
        self.model.clear()

    def pause(self, state):
        self.model.pause(state)

    def set_filter_string(self, string):
        self.proxy_model.set_filter_string(string)

    def context_menu(self, point):
        proxy_model_index = self.indexAt(point)
        index = self.proxy_model.mapToSource(proxy_model_index)
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

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Network Activity')
        self.view = ActivityView()

        l = QVBoxLayout()
        l.setContentsMargins(0,0,0,0)

        self.clear_action = QAction('Clear')
        self.pause_action = QAction('Pause')
        self.pause_action.setCheckable(True)

        self.toolbar = QToolBar()
        self.toolbar.setIconSize(iface.iconSize(True))
        self.toolbar.addAction(self.clear_action)
        self.toolbar.addAction(self.pause_action)
        self.clear_action.triggered.connect(self.view.clear)
        self.pause_action.toggled.connect(self.view.pause)

        self.filter_line_edit = QgsFilterLineEdit()
        self.filter_line_edit.setShowSearchIcon(True)
        self.filter_line_edit.setPlaceholderText('Filter requests')
        self.filter_line_edit.textChanged.connect(self.view.set_filter_string)
        l.addWidget(self.toolbar)
        l.addWidget(self.filter_line_edit)
        l.addWidget(self.view)
        w = QWidget()
        w.setLayout(l)
        self.setWidget(w)


