Experimental QGIS plugin to be able to see the request QGIS is firing to for example OGC services

Current limitations:
- not all requests are shown
- Only listening to the requestAboutToBeCreated and requestTimedOut signals
- no gui to connect to other signals

To use:
- install plugin
- open the messagelog panel and view panel named "QGIS Network Logger..."

For Example:

![Example Log](/img/examplelog.png)