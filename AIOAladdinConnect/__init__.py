from gc import callbacks
import logging
import json
from AIOAladdinConnect.session_manager import SessionManager
from AIOAladdinConnect.eventsocket import EventSocket
#from session_manager import SessionManager

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

    def __init__(self, email, password):
        self._session = SessionManager(email, password)
        self._eventsocket = None
        self._user_email = email
        self._device_portal = {}
        self._doors = {'device_id':0}
    
    async def login(self):
        self._LOGGER.debug("Logging in")
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
        return await self._session.close()

    async def get_doors(self):
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
        except ValueError as ex:
            self._LOGGER.error("Aladdin Connect - Unable to retrieve configuration %s", ex)
            return None

    async def close_door(self, device_id, door_number):
        await self._set_door_status(device_id, door_number, self.DOOR_STATUS_CLOSED)

    async def open_door(self, device_id, door_number):
        await self._set_door_status(device_id, door_number, self.DOOR_STATUS_OPEN)

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

    async def get_door_status(self, device_id, door_number):
        for door in self._doors:
            if door["device_id"] == device_id and door["door_number"] == door_number:
                return door["status"]
    

    async def _call_back(self,msg):
        self._LOGGER.info(f"Got the callback {json.loads(msg)}")
        json_msg = json.loads(msg)
        for door in self._doors:
            if json_msg['door'] == door['door_number']:
                door.update({'status': self.DOOR_STATUS[json_msg["door_status"]]})
                self._LOGGER.info(f"Status Updated {self.DOOR_STATUS[json_msg['door_status']]}")
