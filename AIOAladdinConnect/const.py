"""Aladdin Connect Constants."""
import logging

_LOGGER = logging.getLogger(__name__)

# Event Socket constants
WSURI = "wss://event-caster.st1.gdocntl.net/updates"
# WSURI_ACK = "wss://app.apps.st1.gdocntl.net/monitor"
WS_STATUS_GOING_AWAY = 1001
WS_STATUS_UNAUTHORIZED = 3000

RECONNECT_COUNT = 3
RECONNECT_LONG_DELAY = 60
