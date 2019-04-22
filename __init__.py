# -*- coding: utf-8 -*-
"""
 This script initializes the plugin, making it known to QGIS.
"""

LOGGER_NAME = 'QgisNetworkLogger'

def classFactory(iface):
  from .plugin import QgisNetworkLogger
  return QgisNetworkLogger(iface)


