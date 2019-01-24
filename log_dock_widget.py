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
    QModelIndex,
    Qt
)
from qgis.PyQt.QtWidgets import (
    QTreeView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    qApp
)
from qgis.PyQt.QtGui import (
    QPen,
    QColor
)
from qgis.PyQt.QtNetwork import (
    QNetworkAccessManager,
    QNetworkRequest,
    QNetworkReply
)
from qgis.gui import QgsDockWidget
from qgis.core import (
    QgsNetworkAccessManager,
    QgsNetworkReplyContent,
    QgsNetworkRequestParameters
)

STATUS_ROLE = Qt.UserRole + 1

PENDING = 'PENDING'
COMPLETE = 'COMPLETE'
ERROR = 'ERROR'


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


class RootItem(ActivityTreeItem):
    def __init__(self, parent=None):
        super().__init__('', parent)


class RequestParentItem(ActivityTreeItem):

    def __init__(self, request, parent=None):
        super().__init__('', parent)
        self.url = request.request().url()
        RequestItem(request, self)

        self.status = PENDING

    def span(self):
        return True

    def text(self, column):
        if column == 0:
            return self.url.url()
        return ''

    def set_reply(self, reply):
        if reply.error() != QNetworkReply.NoError:
            self.status = ERROR
        else:
            self.status = COMPLETE
        ReplyItem(reply, self)


class RequestItem(ActivityTreeItem):
    def __init__(self, request, parent=None):
        super().__init__('', parent)

        self.url = request.request().url()

        operation = request.operation()
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

        RequestDetailsItem('Operation', op, self)
        RequestDetailsItem('Thread', request.originatingThreadId(), self)
        RequestHeadersItem(request, self)

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


class ItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        val = index.data(Qt.DisplayRole)
        if not val:
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # original command that would draw the whole thing with default style
        #style.drawControl(QStyle.CE_ItemViewItem, opt, painter)

        style = qApp.style()
        painter.save()
        painter.setClipRect(opt.rect)

        # background
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, opt, painter, None)

        text_margin = style.pixelMetric(QStyle.PM_FocusFrameHMargin, None, None) + 1
        text_rect = opt.rect.adjusted(text_margin, 0, -text_margin, 0) # remove width padding

        # variable name
        painter.save()
        if index.data(STATUS_ROLE) == PENDING:
            color = QColor(0,0,0,100)
        elif index.data(STATUS_ROLE) == ERROR:
            color = QColor(235, 10, 10)
        else:
            color = QColor(0,0,0)

        painter.setPen(QPen(color))
        used_rect = painter.drawText(text_rect, Qt.AlignLeft, str(val))
        painter.restore()

        painter.restore()

class NetworkActivityModel(QAbstractItemModel):
    def __init__(self, root_item, parent=None):
        super().__init__(parent)
        self.root_item = root_item

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


class ActivityView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = NetworkActivityModel(RootItem(), self)
        self.setModel(self.model)

        self.model.rowsInserted.connect(self.rows_inserted)
        self.setItemDelegate(ItemDelegate(self))

    def rows_inserted(self, parent, first, last):
        # silly qt API - this shouldn't be so hard!
        for r in range(first, last + 1):
            this_index = self.model.index(r, 0, parent)
            if this_index.internalPointer().span():
                self.setFirstColumnSpanned(r, parent, True)
            for i in range(self.model.rowCount(this_index)):
                self.rows_inserted(this_index, i, i)

            w = this_index.internalPointer().createWidget()
            if w:
                self.setIndexWidget(this_index, w)


class NetworkActivityDock(QgsDockWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Network Activity')
        self.view = ActivityView()
        self.setWidget(self.view)
