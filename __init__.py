# -*- coding: utf-8 -*-
"""
 This script initializes the plugin, making it known to QGIS.
"""

"""
The name of logger we use in this plugin.
It is created in the plugin.py and logs to the QgsMessageLog under the 
given LOGGER_NAME tab
"""
LOGGER_NAME = 'QgisNetworkLogger'


def classFactory(iface):
  """
  Factory method to actually create the plugin by QGIS
  :param iface:
  :return:
  """
  from .plugin import QgisNetworkLogger
  return QgisNetworkLogger(iface)


