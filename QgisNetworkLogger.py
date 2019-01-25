# -*- coding: utf-8 -*-
# Import the PyQt and QGIS libraries
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsNetworkAccessManager,
    QgsNetworkReplyContent,
    QgsNetworkRequestParameters
)
from qgis.PyQt.QtNetwork import (
    QNetworkAccessManager,
    QNetworkRequest
)

import os

class QgisNetworkLogger:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # get the handle of the (singleton?) QgsNetworkAccessManager instance
        self.nam = QgsNetworkAccessManager.instance()
        # TODO put in gui/settings
        self.show_request_headers = False
        self.show_response_headers = False

    def initGui(self):
        # Create action that will start plugin
        self.action = QAction(QIcon(os.path.dirname(__file__)+'/icons/icon.png'), '&QGIS Network Logger', self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.show_dialog)
        # Add menu item
        self.iface.addPluginToMenu('QGIS Network Logger', self.action)
        #import pydevd
        #pydevd.settrace('localhost', port=5678, stdoutToServer = True, stderrToServer = True)
        self.log_it()

    def unload(self):
        # Remove the plugin menu item
        self.iface.removePluginMenu('QGIS Network Logger',self.action)
        # cannot find a way to check IF we are listening to a signal, so dirty way: just do try catch
        try:
            self.nam.requestAboutToBeCreated[QgsNetworkRequestParameters].disconnect(self.request_about_to_be_created)
        except:
            self.show("Unloading plugin, disconnecting 'requestAboutToBeCreated'-signal failed, probably not connected.")
        try:
            self.nam.finished[QgsNetworkReplyContent].disconnect(self.request_finished)
        except:
            self.show("Unloading plugin, disconnecting 'finished'-signal failed, probably not connected.")
        try:
            self.nam.requestTimedOut[QgsNetworkRequestParameters].disconnect(self.request_timed_out)
        except:
            self.show("Unloading plugin, disconnecting 'requestTimedOut'-signal failed, probably not connected.")

    def log_it(self):
        self.nam.requestAboutToBeCreated[QgsNetworkRequestParameters].connect(self.request_about_to_be_created)
        self.nam.finished[QgsNetworkReplyContent].connect(self.request_finished)
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
        QgsMessageLog.logMessage(msg, "QGIS Network Logger...", Qgis.MessageLevel.Info)

    # request_params = QgsNetworkRequestParameters with QNetworkRequest
    def request_about_to_be_created(self, request_params):
        operation = request_params.operation()
        initiator = request_params.initiatorClassName()
        initiator_id = request_params.initiatorRequestId()
        op = "Custom"
        if operation == QNetworkAccessManager.HeadOperation: op = "HEAD"
        elif operation == QNetworkAccessManager.GetOperation: op = "GET"
        elif operation == QNetworkAccessManager.PutOperation: op = "PUT"
        elif operation == QNetworkAccessManager.PostOperation: op = "POST"
        elif operation == QNetworkAccessManager.DeleteOperation: op = "DELETE"
        url = request_params.request().url().url()
        thread_id = request_params.originatingThreadId()
        request_id = request_params.requestId()
        headers = ''
        if self.show_request_headers:
            for header in request_params.request().rawHeaderList():
                headers+='<br/>'+header.data().decode('utf-8')+' =  '+request_params.request().rawHeader(header).data().decode('utf-8')
        self.show('Request {} in thread {} by {} ({}) <br/>{} <a href="{}">{}</a> <span style="color:gray;">{}</span>'.format(request_id, thread_id, initiator, initiator_id, op, url, url, headers))
        if operation == QNetworkAccessManager.PostOperation or operation == QNetworkAccessManager.PutOperation:
            # duh.... most POST data is xml which is NOT viewable in html IF NOT ESCAPED.....
            import html
            self.show('Request {} POST data: <span style="color:gray;">{}</span>'.format(request_id, html.escape(request_params.content().data().decode('utf-8'))))

    # reply is a QgsNetworkReplyContent
    def request_finished(self, reply):
        request = reply.request()
        request_id = reply.requestId()
        status =  reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) # QNetworkRequest::HttpStatusCodeAttribute = 0
        headers = ''
        if self.show_response_headers:
            for header in reply.rawHeaderList():
                headers+='<br/>'+header.data().decode('utf-8')+' =  '+reply.rawHeader(header).data().decode('utf-8')
        error = ''
        # Note: When the HTTP protocol returns a redirect no error will be reported. You can check if there is a redirect with the QNetworkRequest::RedirectionTargetAttribute attribute.
        # TODO check for QNetworkRequest::RedirectionTargetAttribute ?
        if reply.error():   # QNetworkReply::NoError = 0 == False
            # http://doc.qt.io/qt-5/qnetworkreply.html#NetworkError-enum
            link = 'http://doc.qt.io/qt-5/qnetworkreply.html#NetworkError-enum'
            error = ' with error: {} ( see <a href="{}">{}</a> )'.format(reply.error(), link, 'Qt Network Error codes')
        self.show('Finished {} with status {} {} <span style="color:gray;">{}</span>'.format(request_id, status, error, headers))


    # request_params = QgsNetworkRequestParameters
    def request_timed_out(self, request_params):
        url = request_params.request().url().url()
        thread_id = request_params.originatingThreadId()
        request_id = request_params.requestId()
        #self.show('Timeout or abort: <a href="{}">{}</a>'.format(url, url))
        self.show('Timeout or abort {} in thread {}'.format(request_id, thread_id))
