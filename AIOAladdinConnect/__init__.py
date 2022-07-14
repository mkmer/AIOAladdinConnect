import logging
import json
from sre_constants import SRE_FLAG_DOTALL
from typing import Callable

import aiohttp
from AIOAladdinConnect.session_manager import SessionManager
from AIOAladdinConnect.eventsocket import EventSocket
_LOGGER = logging.getLogger(__name__)
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

    def __init__(self, email:str, password:str, session):
        self._session = SessionManager(email, password, session)
        self._eventsocket = None
        self._doors = {'device_id':'0' , 'status':'closed'},{}
        self._attr_changed :dict(int,Callable) = {}
        self._first_door = None
    
    def register_callback(self,update_callback:Callable,door_number:int):
        self._attr_changed.update({door_number:update_callback})
        _LOGGER.info("Registered callback")
 
    async def login(self):
        _LOGGER.info("Logging in")
        # if there is an error, trying to log back needs to stop the eventsocket
        if self._eventsocket:
            await self._eventsocket.stop()
        status = await self._session.login()
        if status:
            _LOGGER.info("Logged in")

            await self.get_doors()
            _LOGGER.info("Got initial door status")
            
            self._eventsocket = EventSocket(self._session.auth_token(),self._call_back)
            await self._eventsocket.start()
            _LOGGER.info("Started Socket")
           
        return status
    
    async def close(self):
        await self._session.close()
        if self._eventsocket:
            await self._eventsocket.stop()
        return True

    async def get_doors(self,door_number:int = None):
        """Get all doors status and store values 
            This function should be called intermittently to update all door information"""
        if door_number and self._first_door is None:
            self._first_door = door_number # only update on the first door registered.

        if self._first_door or door_number is None:
            devices = await self._get_devices()
        doors = []
        if devices:
            for device in devices:
                doors += device['doors']
            
        if self._eventsocket and door_number:        
            for door,orig_door in zip(doors,self._doors):
                if door['status'] !=  orig_door['status']:
                    # The socket has failed to keep us up to date...
                    await self._eventsocket.stop()
                    await self._eventsocket.start()
        self._doors = doors
        
        return self._doors

    async def _get_devices(self):
        """Get list of devices, i.e., Aladdin Door Controllers"""
        devices = []
        attempts = 0
        while attempts < 2: # if the key expires, log in and try this again
            try:
                response = await self._session.get(self.CONFIGURATION_ENDPOINT)
                    
                for device in response["devices"]:
                    doors = []
                    for door in device["doors"]:
                        doors.append({
                            'device_id': device["id"],
                            'door_number': door["door_index"],
                            'name': door["name"],
                            'status': self.DOOR_STATUS[door.get("status",0)],
                            'link_status': self.DOOR_LINK_STATUS[door.get("link_status",0)],
                            'battery_level': door.get("battery_level",0),
                            'rssi': device.get('rssi',0),
                            'serial': device["serial"][:-3],
                            'vendor': device.get("vendor",""),
                            'model' : device.get("model",""),
                            'ble_strength' : door.get("ble_strength",0),

                        })
                    devices.append({
                        'device_id': device["id"],
                        'doors': doors
                    }
                )
                return devices
            except (KeyError) as ex:
                _LOGGER.error("Aladdin Connect - Unable to retrieve configuration %s", ex)
                return None

            except (aiohttp.ClientConnectionError) as ccer:
                _LOGGER.error("%s",ccer)
                await self.login()
                attempts +=1
        return None            
            
    async def close_door(self, device_id:int, door_number:int):
        """Command to close the door"""
        return await self._set_door_status(device_id, door_number, self.DOOR_STATUS_CLOSED)

    async def open_door(self, device_id:int, door_number:int):
        """Command to open the door"""
        return await self._set_door_status(device_id, door_number, self.DOOR_STATUS_OPEN)

    async def _set_door_status(self, device_id:int, door_number:int, requested_door_status:DOOR_STATUS):
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
                _LOGGER.error("Aladdin Connect - Unable to set door status %s", ex)
                return False

        return True

    async def async_get_door_status(self, device_id:int, door_number:int):
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

    async def _call_back(self,msg)-> bool:
        """Call back from AIO HTTP web socket with door status information"""
        # Opening and Closing only are sent if the WEB API called the open/close event
        # pressing the local button only results in a state change of open or close.
        _LOGGER.info(f"Got the callback {json.loads(msg)}")
        json_msg = json.loads(msg)
        
        for door in self._doors:
            if all(key in json_msg for key in ('device_status','serial')):
                # Server is reporting state change disconnection.  Need to restart web socket
                if json_msg['serial'] == door['serial'] and json_msg['device_status'] == 0:
                    _LOGGER.info(f"Reconnecting because we Received socket disconnect message {json_msg}")
                    return False

            # There are multiple messages from the websocket for the same value - filter this off
            if all(key in json_msg for key in ('serial','door','door_status')):
                if json_msg['serial'] == door['serial'] and json_msg['door'] == door['door_number'] and self.DOOR_STATUS[json_msg['door_status']] != door['status']:
                    door.update({'status': self.DOOR_STATUS[json_msg["door_status"]]})
                    _LOGGER.info(f"Status Updated {self.DOOR_STATUS[json_msg['door_status']]}")
                    if self._attr_changed: # There is a callback 
                        for door_key in self._attr_changed:  
                            if json_msg['door'] == door_key: #the door is registered as a callback 
                                await self._attr_changed[json_msg['door']]() # callback the door triggered
                else:
                    _LOGGER.info(f"Status NOT updated {self.DOOR_STATUS[json_msg['door_status']]}")
        return True

    def auth_token(self):
        return self._session.auth_token()

    async def set_auth_token(self,auth_token):
        self._session.set_auth_token(auth_token)
        if self._eventsocket is None:
            self._eventsocket = EventSocket(self._session.auth_token(),self._call_back) 
        if self._eventsocket:
            await self._eventsocket.set_auth_token(auth_token)



# Web server errors seen:
# 500 server error
# 401 when logging in and server error is going on
