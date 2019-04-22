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

# https://doc.qt.io/qt-5/qtwidgets-itemviews-editabletreemodel-example.html#design


import time

from qgis.PyQt.QtCore import (
    QAbstractItemModel,
    QSortFilterProxyModel,
    QModelIndex,
    Qt,
    QUrlQuery
)
from qgis.PyQt.QtWidgets import (
    QApplication,
    QAction
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
from qgis.core import (
    QgsNetworkAccessManager,
    QgsNetworkReplyContent,
    QgsNetworkRequestParameters
)

import logging
from . import LOGGER_NAME
log = logging.getLogger(LOGGER_NAME)

STATUS_ROLE = Qt.UserRole + 1

PENDING = 'PENDING'
COMPLETE = 'COMPLETE'
ERROR = 'ERROR'
TIMEOUT = 'TIMEOUT'
CANCELED = 'CANCELED'


class NetworkActivityLogger(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_item = RootItem()

        self.is_paused = False

        nam = QgsNetworkAccessManager.instance()

        nam.requestAboutToBeCreated[QgsNetworkRequestParameters].connect(self.request_about_to_be_created)
        nam.finished[QgsNetworkReplyContent].connect(self.request_finished)
        nam.requestTimedOut[QgsNetworkRequestParameters].connect(self.request_timed_out)
        nam.downloadProgress.connect(self.download_progress)
        nam.requestEncounteredSslErrors.connect(self.ssl_errors)

        self.requests_items = {}

    def request_about_to_be_created(self, request_params):
        child_count = len(self.root_item.children)
        self.beginInsertRows(QModelIndex(), child_count, child_count)
        self.requests_items[request_params.requestId()] = RequestParentItem(request_params, self.root_item)
        self.endInsertRows()

        NODES2RETAIN = 45  # put in some settings dialog?
        if child_count > (NODES2RETAIN*1.2):  # 20% more as buffer
            self.pop_nodes(child_count-NODES2RETAIN)

    def request_finished(self, reply):
        if not reply.requestId() in self.requests_items:
            return
        request_item = self.requests_items[reply.requestId()]
        # find the row: the position of the RequestParentItem in the rootNode
        request_index = self.createIndex(request_item.position(), 0, request_item)
        self.beginInsertRows(request_index, len(request_item.children), len(request_item.children))
        request_item.set_reply(reply)
        self.endInsertRows()

        self.dataChanged.emit(request_index, request_index)

    def request_timed_out(self, reply):
        if not reply.requestId() in self.requests_items:
            return
        request_item = self.requests_items[reply.requestId()]
        request_index = self.createIndex(request_item.position(), 0, request_item)
        request_item.set_timed_out()

        self.dataChanged.emit(request_index, request_index)

    def ssl_errors(self, requestId, errors):
        if not requestId in self.requests_items:
            return
        request_item = self.requests_items[requestId]
        request_index = self.createIndex(request_item.position(), 0, request_item)
        self.beginInsertRows(request_index, len(request_item.children), len(request_item.children))
        request_item.set_ssl_errors(errors)
        self.endInsertRows()

        self.dataChanged.emit(request_index, request_index)

    def download_progress(self, requestId, received, total):
        if not requestId in self.requests_items:
            return
        request_item = self.requests_items[requestId]
        request_index = self.createIndex(request_item.position(), 0, request_item)
        request_item.set_progress(received, total)

        self.dataChanged.emit(request_index, request_index, [Qt.ToolTipRole])

    def columnCount(self, parent):
        return 1

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
            if isinstance(item, RequestParentItem) and item.ssl_errors or isinstance(item, SslErrorsItem) \
                    or isinstance(index.parent().internalPointer(), SslErrorsItem):
                color = QColor(180, 65, 210)
            elif item.status in (PENDING, CANCELED):
                color = QColor(0, 0, 0, 100)
            elif item.status == ERROR:
                color = QColor(235, 10, 10)
            elif item.status == TIMEOUT:
                color = QColor(235, 10, 10)
            else:
                color = QColor(0, 0, 0)
            return QBrush(color)

        elif role == Qt.FontRole:
            f = QFont()
            if item.status == CANCELED:
                f.setStrikeOut(True)
            return f

    # not sure why this raises exceptions but commenting for now
    # is it used?
    # def flags(self, index):
    #     if not index.isValid():
    #         return 0
    #     return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def index(self, row, column, parent_index):

        if not self.hasIndex(row, column, parent_index):
            return QModelIndex()

        parent_item = self.root_item if not parent_index.isValid() else parent_index.internalPointer()
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
        self.endResetModel()

    def pause(self, state):
        log.debug('NetworkLogger.pause, state: {}'.format(state))
        if state == self.is_paused:
            return

        self.is_paused = state
        if self.is_paused:
            QgsNetworkAccessManager.instance().requestAboutToBeCreated[QgsNetworkRequestParameters].disconnect(
                self.request_about_to_be_created)
        else:
            QgsNetworkAccessManager.instance().requestAboutToBeCreated[QgsNetworkRequestParameters].connect(
                self.request_about_to_be_created)

    def remove_one(self):
        log.debug('Remove 1')
        self.beginRemoveRows(QModelIndex(), 0, 0)
        if len(self.root_item.children)>0:
            self.root_item.children.pop(0)
        self.endRemoveRows()

    def pop_nodes(self, count):
        log.debug('Removing {} Request nodes.'.format(count))
        self.beginRemoveRows(QModelIndex(), 0, count-1)
        if len(self.root_item.children) > 0:
            self.root_item.children = self.root_item.children[count:]
        self.endRemoveRows()




class ActivityProxyModel(QSortFilterProxyModel):

    def __init__(self, source_model, parent=None):

        super().__init__(parent)
        self.source_model = source_model
        self.setSourceModel(self.source_model)
        self.filter_string = ''
        self.show_successful = True
        self.show_timeouts = True

    def set_filter_string(self, string):
        self.filter_string = string
        self.invalidateFilter()

    def set_show_successful(self, show):
        self.show_successful = show
        self.invalidateFilter()

    def set_show_timeouts(self, show):
        self.show_timeouts = show
        self.invalidateFilter()

    def filterAcceptsRow(self, sourceRow, sourceParent):
        item = self.source_model.index(sourceRow, 0, sourceParent).internalPointer()
        if isinstance(item, RequestParentItem):
            if item.status in (COMPLETE, CANCELED) and not self.show_successful:
                return False
            elif item.status == TIMEOUT and not self.show_timeouts:
                return False

            return self.filter_string.lower() in item.url.url().lower()
        else:
            return True



class ActivityTreeItem(object):

    def __init__(self, parent=None):
        self.parent = parent
        self.children = []
        if parent:
           parent.children.append(self)

        self.status = COMPLETE

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

    def position(self):
        # return the place of myself in the list of children of my parent
        # (this to be able to let the model know my 'row')
        if self.parent and self in self.parent.children:
            return self.parent.children.index(self)
        return 0


class RootItem(ActivityTreeItem):
    def __init__(self, parent=None):
        super().__init__(parent)


class RequestParentItem(ActivityTreeItem):

    def __init__(self, request, parent=None):
        super().__init__(parent)
        self.url = request.request().url()
        self.id = request.requestId()
        self.operation = self.operation2string(request.operation())
        self.time = time.time()
        self.http_status = -1
        self.content_type = ''
        self.progress = None
        self.headers = []
        self.replies = 0
        self.data = request.content().data().decode('utf-8')
        for header in request.request().rawHeaderList():
            self.headers.append(
                (header.data().decode('utf-8'),
                 request.request().rawHeader(header).data().decode('utf-8')))

        RequestItem(request, self)

        self.status = PENDING
        self.ssl_errors = False

        self.open_url_action = QAction('Open URL')
        self.open_url_action.triggered.connect(self.open_url)

        self.copy_as_curl_action = QAction('Copy as cURL')
        self.copy_as_curl_action.triggered.connect(self.copy_as_curl)

    def span(self):
        return True

    def text(self, column):
        if column == 0:
            # id is the NAM id
            return '{} {} {}'.format(self.id, self.operation, self.url.url())
        return ''

    def open_url(self):
        QDesktopServices.openUrl(self.url)

    def copy_as_curl(self):
        """Get url + headers + data and create a full curl command
        Copy that to clipboard
        """
        curl_headers = ''
        for header, value in self.headers:
            curl_headers += "-H '{}: {}' ".format(header, value)
        curl_data = ''
        if self.operation in ('POST', 'PUT'):
            curl_data = "--data '{}' ".format(self.data)
        curl_cmd = "curl '{}' {} {}--compressed".format(self.url.url(), curl_headers, curl_data)
        QApplication.clipboard().setText(curl_cmd)

    def set_reply(self, reply):
        if reply.error() == QNetworkReply.OperationCanceledError:
            self.status = CANCELED
        elif reply.error() != QNetworkReply.NoError:
            self.status = ERROR
        else:
            self.status = COMPLETE
        self.time = int((time.time() - self.time) * 1000)
        self.http_status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        self.content_type = reply.rawHeader(b'Content-Type').data().decode('utf-8')
        ReplyItem(reply, self)

    def set_timed_out(self):
        self.status = TIMEOUT

    def set_progress(self, received, total):
        self.replies += 1
        self.progress = (received, total)

    def set_ssl_errors(self, errors):
        self.ssl_errors = errors
        SslErrorsItem(errors, self)

    def actions(self):
        return [self.open_url_action, self.copy_as_curl_action]

    def tooltip(self, column):
        bytes = 'unknown'
        if self.progress:
            rec, tot = self.progress
            if rec > 0 and rec < tot:
                bytes = '{}/{}'.format(rec, tot)
            elif rec > 0 and rec == tot:
                bytes = '{}'.format(tot)
        # ?? adding <br/> instead of \n after (very long) url seems to break url up
        # COMPLETE, Status: 200 - text/xml; charset=utf-8 - 2334 bytes - 657 milliseconds
        return "{}<br/>{} - Status: {} - {} - {} bytes - {} msec - {} replies" \
            .format(self.url.url(), self.status, self.http_status, self.content_type, bytes, self.time, self.replies)


class RequestItem(ActivityTreeItem):
    def __init__(self, request, parent=None):
        super().__init__(parent)

        self.url = request.request().url()
        self.operation = self.operation2string(request.operation())
        query = QUrlQuery(self.url)
        RequestDetailsItem('Operation', self.operation, self)
        RequestDetailsItem('Thread', request.originatingThreadId(), self)
        RequestDetailsItem('Initiator', request.initiatorClassName() if request.initiatorClassName() else 'unknown',
                           self)
        if request.initiatorRequestId():
            RequestDetailsItem('ID', str(request.initiatorRequestId()), self)

        RequestDetailsItem('Cache (control)', self.cache_control_to_string(
            request.request().attribute(QNetworkRequest.CacheLoadControlAttribute)), self)
        RequestDetailsItem('Cache (save)', 'Can store result in cache' if request.request().attribute(
            QNetworkRequest.CacheSaveControlAttribute) else 'Result cannot be stored in cache', self)

        query_items = query.queryItems()
        if query_items:
            RequestQueryItems(query_items, self)
        RequestHeadersItem(request, self)
        if self.operation in ('POST', 'PUT'):
            PostContentItem(request, self)

    @staticmethod
    def cache_control_to_string(cache_control_attribute):
        if cache_control_attribute == QNetworkRequest.AlwaysNetwork:
            return 'Always load from network, do not check cache'
        elif cache_control_attribute == QNetworkRequest.PreferNetwork:
            return 'Load from the network if the cached entry is older than the network entry'
        elif cache_control_attribute == QNetworkRequest.PreferCache:
            return 'Load from cache if available, otherwise load from network'
        elif cache_control_attribute == QNetworkRequest.AlwaysCache:
            return 'Only load from cache, error if no cached entry available'
        return None

    def span(self):
        return True

    def text(self, column):
        return 'Request' if column == 0 else ''


class RequestDetailsItem(ActivityTreeItem):
    def __init__(self, description, value, parent=None):
        super().__init__(parent)

        self.description = description
        self.value = value

    def text(self, column):
        if column == 0:
            #return self.description
            return '{:30}: {}'.format(self.description, self.value)
        else:
            return self.value


class RequestHeadersItem(ActivityTreeItem):
    def __init__(self, request, parent=None):
        super().__init__(parent)

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
        super().__init__(parent)

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
        super().__init__(parent)

        # maybe should be &amp?
        # for p in request.content().data().decode('utf-8').split('&'):
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
        super().__init__(parent)

        # self.description, self.value = part.split('=')
        self.data = part

    def text(self, column):
        if column == 0:
            #return 'Data'
            return '{:30}: {}'.format('Data', self.data)
        else:
            return self.data


class ReplyItem(ActivityTreeItem):
    def __init__(self, reply, parent=None):
        super().__init__(parent)
        ReplyDetailsItem('Status', reply.attribute(QNetworkRequest.HttpStatusCodeAttribute), self)
        if reply.error() != QNetworkReply.NoError:
            ReplyDetailsItem('Error Code', reply.error(), self)
            ReplyDetailsItem('Error', reply.errorString(), self)

        RequestDetailsItem('Cache (result)', 'Used entry from cache' if reply.attribute(
            QNetworkRequest.SourceIsFromCacheAttribute) else 'Read from network', self)

        ReplyHeadersItem(reply, self)

    def span(self):
        return True

    def text(self, column):
        return 'Reply' if column == 0 else ''


class ReplyHeadersItem(ActivityTreeItem):
    def __init__(self, reply, parent=None):
        super().__init__(parent)

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
        super().__init__(parent)

        self.description = description
        self.value = value

    def text(self, column):
        if column == 0:
            #return self.description
            return '{:30}: {}'.format(self.description, self.value)
        else:
            return self.value


class SslErrorsItem(ActivityTreeItem):
    def __init__(self, errors, parent=None):
        super().__init__(parent)
        for error in errors:
            ReplyDetailsItem('Error',
                             error.errorString(), self)

    def text(self, column):
        if column == 0:
            return 'SSL errors'
        else:
            return ''

    def span(self):
        return True
