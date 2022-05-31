import logging
import json
from typing import Callable
from AIOAladdinConnect.session_manager import SessionManager
from AIOAladdinConnect.eventsocket import EventSocket

class AladdinConnectClient:
    CONFIGURATION_ENDPOINT = "/configuration"

    DOOR_STATUS_OPEN = 'open'
    DOOR_STATUS_CLOSED = 'closed'
    DOOR_STATUS_OPENING = 'opening'
    DOOR_STATUS_CLOSING = 'closing'
    DOOR_STATUS_UNKNOWN = 'unknown'

    DOOR_COMMAND_CLOSE = "CloseDoor"
    DOOR_COMMAND_OPEN = "OpenDoor"

    DOOR_STATUS = {
        0: DOOR_STATUS_UNKNOWN,  # Unknown
        1: DOOR_STATUS_OPEN,  # open
        2: DOOR_STATUS_OPENING,  # opening
        3: DOOR_STATUS_UNKNOWN,  # Timeout Opening
        4: DOOR_STATUS_CLOSED,  # closed
        5: DOOR_STATUS_CLOSING,  # closing
        6: DOOR_STATUS_UNKNOWN,  # Timeout Closing
        7: DOOR_STATUS_UNKNOWN  # Not Configured
    }

    REQUEST_DOOR_STATUS_COMMAND = {
        DOOR_STATUS_CLOSED: DOOR_COMMAND_CLOSE,
        DOOR_STATUS_OPEN: DOOR_COMMAND_OPEN
    }

    STATUS_CONNECTED = 'Connected'
    STATUS_NOT_CONFIGURED = 'NotConfigured'

    DOOR_LINK_STATUS = {
        0: 'Unknown',
        1: STATUS_NOT_CONFIGURED,
        2: 'Paired',
        3: STATUS_CONNECTED
    }

    CONTROLLER_STATUS = {
        0: 'Offline',
        1: STATUS_CONNECTED
    }

    _LOGGER = logging.getLogger(__name__)

    def __init__(self, email:str, password:str,attr_changed:Callable):
        self._session = SessionManager(email, password)
        self._eventsocket = None
        self._doors = {'device_id':0}
        self._attr_changed = attr_changed
    
    def register_callback(self,update_callback:Callable):
        self._attr_changed = update_callback
        self._LOGGER.debug("Registered callback")
 
    async def login(self):
        self._LOGGER.debug("Logging in")
        # if there is an error, trying to log back needs to stop the eventsocket
        if self._eventsocket:
            await self._eventsocket.stop()

        status = await self._session.login()
        if status:
            self._LOGGER.debug("Logged in")

            await self.get_doors()
            self._LOGGER.debug("Got initial door status")
            
            self._eventsocket = EventSocket(self._session.auth_token(),self._call_back)
            await self._eventsocket.start()
            self._LOGGER.debug("Started Socket")
            
        return status
    
    async def close(self):
        await self._session.close()
        if self._eventsocket:
            await self._eventsocket.stop()
        return True

    async def get_doors(self):
        """Get all doors status and store values 
            This function should be called intermittently to update all door information"""
        devices = await self._get_devices()

        doors = []

        if devices:
            for device in devices:
                doors += device['doors']
        self._doors = doors
        return doors

    async def _get_devices(self):
        """Get list of devices, i.e., Aladdin Door Controllers"""

        try:

            response = await self._session.get(self.CONFIGURATION_ENDPOINT)
            devices = []
            for device in response["devices"]:
                doors = []
                for door in device["doors"]:
                    doors.append({
                        'device_id': device["id"],
                        'door_number': door["door_index"],
                        'name': door["name"],
                        'status': self.DOOR_STATUS[door["status"]],
                        'link_status': self.DOOR_LINK_STATUS[door["link_status"]],
                        'battery_level': door["battery_level"],
                        'rssi': device['rssi']
                    })
                devices.append({
                    'device_id': device["id"],
                    'doors': doors
                })
            return devices
        except (ValueError,KeyError) as ex:
            self._LOGGER.error("Aladdin Connect - Unable to retrieve configuration %s", ex)
            return None

    async def close_door(self, device_id, door_number):
        """Command to close the door"""
        return await self._set_door_status(device_id, door_number, self.DOOR_STATUS_CLOSED)

    async def open_door(self, device_id, door_number):
        """Command to open the door"""
        return await self._set_door_status(device_id, door_number, self.DOOR_STATUS_OPEN)

    async def _set_door_status(self, device_id, door_number, requested_door_status):
        """Set door state"""
        payload = {"command_key": self.REQUEST_DOOR_STATUS_COMMAND[requested_door_status]}

        try:
            await self._session.call_rpc(f"/devices/{device_id}/door/{door_number}/command", payload)
        except ValueError as ex:
            # Ignore "Door is already open/closed" errors to maintain backwards compatibility
            error = str(ex.args[0])
            should_ignore = error.endswith(
                f'{{"code":400,"error":"Door is already {requested_door_status}"}}')
            if not should_ignore:
                self._LOGGER.error("Aladdin Connect - Unable to set door status %s", ex)
                return False

        return True

    async def async_get_door_status(self, device_id, door_number):
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["status"]
    
    def get_door_status(self, device_id, door_number):
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["status"]

    async def async_get_door_link_status(self,device_id,door_number):
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["link_status"]

    def get_door_link_status(self,device_id,door_number):
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["link_status"]

    async def async_get_battery_status(self,device_id,door_number):
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["battery_level"]

    def get_battery_status(self,device_id,door_number):
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["battery_level"]

    async def async_get_rssi_status(self,device_id,door_number):
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["rssi"]

    def get_rssi_status(self,device_id,door_number):
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["rssi"]

    async def _call_back(self,msg):
        """Call back from AIO HTTP web socket with door status information"""
        # Opening and Closing only are sent if the WEB API called the open/close event
        # pressing the local button only results in a state change of open or close.
        self._LOGGER.debug(f"Got the callback {json.loads(msg)}")
        json_msg = json.loads(msg)
        for door in self._doors:
            # There are multiple messages from the websocket for the same value - filter this off
            if json_msg['door'] == door['door_number'] and self.DOOR_STATUS[json_msg['door_status']] != door['status']:
                door.update({'status': self.DOOR_STATUS[json_msg["door_status"]]})
                self._LOGGER.debug(f"Status Updated {self.DOOR_STATUS[json_msg['door_status']]}")
                if self._attr_changed:
                    await self._attr_changed()
            else:
                self._LOGGER.debug(f"Status NOT updated {self.DOOR_STATUS[json_msg['door_status']]}")

    def auth_token(self):
        return self._session.auth_token()

    def set_auth_token(self,auth_token):
        self._session.set_auth_token(auth_token)
