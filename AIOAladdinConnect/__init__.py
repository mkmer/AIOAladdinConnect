import logging
import json
from sre_constants import SRE_FLAG_DOTALL
from typing import Callable

import aiohttp
from AIOAladdinConnect.session_manager import SessionManager
from AIOAladdinConnect import session_manager
from AIOAladdinConnect.eventsocket import EventSocket

_LOGGER = logging.getLogger(__name__)


class AladdinConnectClient:
    """Aladdin Connect Client Class"""

    CONFIGURATION_ENDPOINT = "/configuration"
    DEVICE_ENDPOINT = "/devices"

    DOOR_STATUS_OPEN = "open"
    DOOR_STATUS_CLOSED = "closed"
    DOOR_STATUS_OPENING = "opening"
    DOOR_STATUS_CLOSING = "closing"
    DOOR_STATUS_UNKNOWN = "unknown"
    DOOR_STATUS_TIMEOUT_CLOSE = "open"  # If it timed out opening, it's still closed?
    DOOR_STATUS_TIMEOUT_OPEN = "closed"  # If it timed out closing, it's still open?
    DOOR_COMMAND_CLOSE = "CloseDoor"
    DOOR_COMMAND_OPEN = "OpenDoor"

    DOOR_STATUS = {
        0: DOOR_STATUS_UNKNOWN,  # Unknown
        1: DOOR_STATUS_OPEN,  # open
        2: DOOR_STATUS_OPENING,  # opening
        3: DOOR_STATUS_TIMEOUT_OPEN,  # Timeout Opening
        4: DOOR_STATUS_CLOSED,  # closed
        5: DOOR_STATUS_CLOSING,  # closing
        6: DOOR_STATUS_TIMEOUT_CLOSE,  # Timeout Closing
        7: DOOR_STATUS_UNKNOWN,  # Not Configured
    }

    REQUEST_DOOR_STATUS_COMMAND = {
        DOOR_STATUS_CLOSED: DOOR_COMMAND_CLOSE,
        DOOR_STATUS_OPEN: DOOR_COMMAND_OPEN,
    }

    STATUS_CONNECTED = "Connected"
    STATUS_NOT_CONFIGURED = "NotConfigured"

    DOOR_LINK_STATUS = {
        0: "Unknown",
        1: STATUS_NOT_CONFIGURED,
        2: "Paired",
        3: STATUS_CONNECTED,
    }

    CONTROLLER_STATUS = {0: "Offline", 1: STATUS_CONNECTED}

    def __init__(self, email: str, password: str, session, client_id: str):
        self._session_id = session
        self._session = SessionManager(email, password, session, client_id)
        self._eventsocket = None
        self._doors = {"device_id": "0", "status": "closed", "serial": "0000000000"}, {}
        self._attr_changed: dict(str, Callable) = {}
        self._first_door = None
        self._reset_time = None

    def register_callback(self, update_callback: Callable, serial: str, door: int):
        """Register a callback function for events"""
        key = f"{serial}-{door}"
        self._attr_changed.update({key: update_callback})
        _LOGGER.info("Registered callback %s", key)

    def unregister_callback(self, serial: str, door: int):
        """Remove a registered callback from events"""
        key = f"{serial}-{door}"
        if self._attr_changed:
            try:
                del self._attr_changed[key]
                _LOGGER.info("Unregistered callback %s", key)
            except KeyError:
                _LOGGER.error("Unregistered callback %s Not found", key)

    async def login(self):
        """Login to AladdinConnect Service and get initial door status"""
        _LOGGER.info("Logging in")
        # if there is an error, trying to log back needs to stop the eventsocket

        status = await self._session.login()

        if status:
            _LOGGER.info("Logged in")

            await self.get_doors()
            _LOGGER.info("Got initial door status")

            if not self._eventsocket:  # if first time login in....
                self._eventsocket = EventSocket(
                    self._session.auth_token(), self._call_back, self._session_id
                )
                await self._eventsocket.start()
            else:
                await self._eventsocket.set_auth_token(
                    self._session.auth_token()
                )  # set the new auth token

            _LOGGER.info("Started Socket")

        return status

    async def close(self):
        """Close the connection and stop the event socket."""
        if self._eventsocket:
            await self._eventsocket.stop()
        return True

    async def get_doors(self, serial: str = None):
        """Get all doors status and store values.
        This function should be called intermittently to update all door information."""
        if serial and self._first_door is None:
            self._first_door = serial  # only update on the first door registered.

        if self._first_door or serial is None:
            devices = await self._get_devices()
        doors = []
        if devices:
            for device in devices:
                doors += device["doors"]

        if self._eventsocket and serial:
            for door, orig_door in zip(doors, self._doors):
                if door["status"] != orig_door["status"]:
                    # The socket has failed to keep us up to date...
                    await self._eventsocket.stop()
                    await self._eventsocket.start()
                    break
        self._doors = doors

        return self._doors

    async def _get_devices(self):
        """Get list of devices, i.e., Aladdin Door Controllers."""
        devices = []
        attempts = 0

        while attempts < 2:  # if the key expires, log in and try this again
            try:
                response = await self._session.get(self.DEVICE_ENDPOINT)

                for device in response["devices"]:
                    doors = []
                    for door in device["doors"]:
                        doors.append(
                            {
                                "device_id": device["id"],
                                "door_number": door["door_index"],
                                "name": door["name"],
                                "status": self.DOOR_STATUS[door.get("status", 0)],
                                "link_status": self.DOOR_LINK_STATUS[
                                    door.get("link_status", 0)
                                ],
                                "battery_level": door.get("battery_level", 0),
                                "rssi": device.get("rssi", 0),
                                "serial": device["serial"][0:12],
                                "vendor": device.get("vendor", ""),
                                "model": device.get("model", ""),
                                "ble_strength": door.get("ble_strength", 0),
                            }
                        )
                    devices.append({"device_id": device["id"], "doors": doors})
                return devices
            except (KeyError) as ex:
                _LOGGER.error(
                    "Aladdin Connect - Unable to retrieve configuration %s", ex
                )
                return None

            except (aiohttp.ClientError, session_manager.ConnectionError) as ex:
                _LOGGER.info("Client connection: %s", ex)
                await self.login()
                attempts += 1
        return None

    async def get_device(self, device_id):
        """Get list of devices, i.e., Aladdin Door Controllers"""
        devices = []
        attempts = 0

        while attempts < 2:  # if the key expires, log in and try this again
            try:
                response = await self._session.get(
                    self.DEVICE_ENDPOINT + "/" + str(device_id)
                )
                _LOGGER.debug("Device only: %s", response)

                doors = []
                for door in response["doors"]:
                    doors.append(
                        {
                            "device_id": device_id,
                            "door_number": door["door_index"],
                            "name": door["name"],
                            "status": self.DOOR_STATUS[door.get("status", 0)],
                            "link_status": self.DOOR_LINK_STATUS[
                                door.get("link_status", 0)
                            ],
                            "battery_level": door.get("battery_level", 0),
                            "rssi": response.get("rssi", 0),
                            "serial": response["serial"][0:12],
                            "vendor": response.get("vendor", ""),
                            "model": response.get("model", ""),
                            "ble_strength": door.get("ble_strength", 0),
                        }
                    )
                devices.append({"device_id": device_id, "doors": doors})
                return devices
            except (KeyError) as ex:
                _LOGGER.error(
                    "Aladdin Connect - Unable to retrieve configuration %s", ex
                )
                return None

            except (aiohttp.ClientError, session_manager.ConnectionError) as ex:
                _LOGGER.error("%s", ex)
                await self.login()
                attempts += 1
        return None

    async def close_door(self, device_id: int, door_number: int):
        """Command to close the door."""
        return await self._set_door_status(
            device_id, door_number, self.DOOR_STATUS_CLOSED
        )

    async def open_door(self, device_id: int, door_number: int):
        """Command to open the door."""
        return await self._set_door_status(
            device_id, door_number, self.DOOR_STATUS_OPEN
        )

    async def _set_door_status(
        self, device_id: int, door_number: int, requested_door_status: DOOR_STATUS
    ):
        """Set door state."""
        payload = {
            "command_key": self.REQUEST_DOOR_STATUS_COMMAND[requested_door_status]
        }

        try:
            await self._session.call_rpc(
                f"/devices/{device_id}/door/{door_number}/command", payload
            )
        except ValueError as ex:
            # Ignore "Door is already open/closed" errors to maintain backwards compatibility
            should_ignore = (
                f'{{"code":400,"error":"Door is already {requested_door_status}"}}'
                in str(ex.args[0])
            )
            if not should_ignore:
                _LOGGER.error("Aladdin Connect - Unable to set door status %s", ex)
                return False

        return True

    async def async_get_door_status(self, device_id: int, door_number: int):
        """Async call to get the door status."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["status"]

    def get_door_status(self, device_id, door_number):
        """Get the door status."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["status"]

    async def async_get_door_link_status(self, device_id, door_number):
        """Async call to get the door link status for door."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["link_status"]

    def get_door_link_status(self, device_id, door_number):
        """Get the door link status for door."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["link_status"]

    async def async_get_battery_status(self, device_id, door_number):
        """Async call to get battery status for door."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["battery_level"]

    def get_battery_status(self, device_id, door_number):
        """Get battery status for door."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["battery_level"]

    async def async_get_rssi_status(self, device_id, door_number):
        """Async call to get rssi status for door."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["rssi"]

    def get_rssi_status(self, device_id, door_number):
        """Get rssi status for door."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["rssi"]

    async def async_get_ble_strength(self, device_id, door_number):
        """Async call to get BLE signal strength for door."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["ble_strength"]

    def get_ble_strength(self, device_id, door_number):
        """Get BLE signal strength for door."""
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["ble_strength"]

    async def _call_back(self, msg) -> bool:
        """Call back from AIO HTTP web socket with door status information."""
        # Opening and Closing only are sent if the WEB API called the open/close event
        # pressing the local button only results in a state change of open or close.

        if msg is None:  # the socket was closed - update via polling
            _LOGGER.info("Got reset message")
            await self.get_doors()
            for serial in self._attr_changed:
                self._attr_changed[
                    serial
                ]()  # Notify all doors that there has been an update
            return False

        _LOGGER.info("Got the callback %s", json.loads(msg))
        json_msg = json.loads(msg)

        for door in self._doors:
            if all(key in json_msg for key in ("device_status", "serial")):
                # Server is reporting state change disconnection.  Need to restart web socket
                if (
                    json_msg["serial"][0:12] == door["serial"]
                    and json_msg["device_status"] == 0
                ):
                    _LOGGER.info(
                        "Reconnecting because we Received socket disconnect message %s",
                        json_msg,
                    )
                    return False

            # There are multiple messages from the websocket for the same value - filter this off
            if all(key in json_msg for key in ("serial", "door", "door_status")):
                if (
                    json_msg["serial"][0:12] == door["serial"]
                    and json_msg["door"] == door["door_number"]
                    and self.DOOR_STATUS[json_msg["door_status"]] != door["status"]
                ):
                    door.update({"status": self.DOOR_STATUS[json_msg["door_status"]]})
                    _LOGGER.info(
                        "Status Updated %s", self.DOOR_STATUS[json_msg["door_status"]]
                    )
                    if self._attr_changed:  # There is a callback
                        for serial in self._attr_changed:
                            lookup = f"{json_msg['serial']}-{json_msg['door']}"
                            if lookup == serial:  # the door is registered as a callback
                                self._attr_changed[
                                    lookup
                                ]()  # callback the door triggered
                else:
                    _LOGGER.info(
                        "Status NOT updated %s ",
                        self.DOOR_STATUS[json_msg["door_status"]],
                    )
        return True

    def auth_token(self):
        """Current auth token."""
        return self._session.auth_token()

    async def set_auth_token(self, auth_token):
        """Set new auth token."""
        self._session.set_auth_token(auth_token)
        if self._eventsocket is None:
            self._eventsocket = EventSocket(
                self._session.auth_token(), self._call_back, self._session_id
            )
        if self._eventsocket:
            await self._eventsocket.set_auth_token(auth_token)


# Web server errors seen:
# 500 server error
# 401 when logging in and server error is going on
