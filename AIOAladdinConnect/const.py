"""Aladdin Connect Constants."""
import logging
from enum import StrEnum

_LOGGER = logging.getLogger(__name__)

# Event Socket constants
WSURI = "wss://event-caster.st1.gdocntl.net/updates"
WS_STATUS_GOING_AWAY = 1001
WS_STATUS_UNAUTHORIZED = 3000

RECONNECT_COUNT = 3
RECONNECT_LONG_DELAY = 60
CLIENT_ID = "27iic8c3bvslqngl3hso83t74b"
CLIENT_SECRET = "7bokto0ep96055k42fnrmuth84k7jdcjablestb7j53o8lp63v5"

HEADER_CONTENT_TYPE_URLENCODED = "application/x-www-form-urlencoded"
API_BASE_URL = "https://api.smartgarage.systems"
RPC_URL = API_BASE_URL

class DoorStatus(StrEnum):
    """Aladdin Connect door status."""

    OPEN = "open"
    CLOSED = "closed"
    OPENING = "opening"
    CLOSING = "closing"
    UNKNOWN = "unknown"
    TIMEOUT_CLOSE = "open"  # If it timed out opening, it's still closed?
    TIMEOUT_OPEN = "closed"  # If it timed out closing, it's still open?
    CONNECTED = "Connected"
    NOT_CONFIGURED = "NotConfigured"

class DoorCommand(StrEnum):
    """Aladdin Connect Door commands."""

    CLOSE = "CLOSE_DOOR"
    OPEN = "OPEN_DOOR"
