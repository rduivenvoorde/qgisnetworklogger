# -*- coding: utf-8 -*-
"""
 This script initializes the plugin, making it known to QGIS.
"""
import logging
from qgis.core import (
    Qgis
)

"""
The name of logger we use in this plugin.
It is created in the __init__.py and logs to the QgsMessageLog under the 
given LOGGER_NAME tab
"""
LOGGER_NAME = 'QgisNetworkLogger'

class QgisLogHandler(logging.StreamHandler):
    '''
    Some magic to make it possible to use code like:

    import logging
    from . import LOGGER_NAME
    log = logging.getLogger(LOGGER_NAME)

    in all this plugin code, and it will show up in the QgsMessageLog

    '''
    def __init__(self, topic):
        logging.StreamHandler.__init__(self)
        # topic is used both as logger id and for tab
        self.topic = topic

    def emit(self, record):
        msg = self.format(record)
        # Below makes sure that logging of 'self' will show the repr of the object
        # Without this it will not be shown because it is something like
        # <qgisnetworklogger.plugin.QgisNetworkLogger object at 0x7f580dac6b38>
        # which looks like an html element so is not shown in the html panel
        # mm, not needed in qgis218
        #msg = msg.replace('<', '&lt;').replace('>', '&gt;')
        #QgsMessageLog.logMessage('{}'.format(msg), self.topic, Qgis.Info)
        from qgis.core import QgsMessageLog  # we need this... else QgsMessageLog is None after a plugin reload
        QgsMessageLog.logMessage('{}'.format(msg), self.topic, Qgis.Info)

log = logging.getLogger(LOGGER_NAME)
# checking below is needed, else we add this handler every time the plugin
# is reloaded (during development), then the msg is emitted several times
#if not log.hasHandlers():
log.addHandler(QgisLogHandler(LOGGER_NAME))

# set logging level (NOTSET = no, else: DEBUG or INFO)
log.setLevel(logging.DEBUG)


def classFactory(iface):
  """
  Factory method to actually create the plugin by QGIS
  :param iface:
  :return:
  """
  from .plugin import QgisNetworkLogger
  return QgisNetworkLogger(iface)


