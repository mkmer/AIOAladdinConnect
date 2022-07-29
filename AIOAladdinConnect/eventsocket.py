import aiohttp
import asyncio
import logging
import json

from typing import Callable

#< WSMessage(type=<WSMsgType.TEXT: 1>, data='{"serial":"F0AD4E03A9FE","door":1,"door_status":4,"fault":0}', extra='')DEBUG:waiting for event message
# WSMessage(type=<WSMsgType.TEXT: 1>, data='{"serial":"F0AD4E03A9FE","door":1,"door_status":4}', extra='')
#DEBUG:waiting for event message

_LOGGER = logging.getLogger(__name__)

WSURI = "wss://event-caster.st1.gdocntl.net/updates"
#WSURI = "wss://app.apps.st1.gdocntl.net/monitor"

class EventSocket:
    def __init__(self, access_token, msg_listener: Callable[[str], None]):
        self._access_token = access_token
        self._msg_listener = msg_listener
        self._running = False
        self._websocket: aiohttp.ClientWebSocketResponse = None
        self._run_future = None
        self._timeout = aiohttp.ClientTimeout(total=None)
       

    async def _run(self):
        if not self._running:
            return
        _LOGGER.info("Started the web socket")
        headers = {
            "Authorization": f'Bearer {self._access_token}'}
        async with aiohttp.ClientSession(timeout=self._timeout, headers=headers) as session:
            async with session.ws_connect(
                WSURI,  heartbeat=20
            ) as ws:
                self._websocket = ws
                _LOGGER.info("Opened the web socket")
                while not ws.closed:
                    _LOGGER.info("waiting for message")
                    msg = await ws.receive() 
                    if not msg:
                        continue
                    _LOGGER.debug(f"event message received< {msg}")
                    if msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error("Socket message error")
                        break
                    if msg.type in [
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.CLOSED,
                    ]:
                        _LOGGER.info(
                            f"Stopping receiving. Message type: {str(msg.type)}"
                        )
                        await self._msg_listener(None) # tell message listener to read the door status
                        break
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        _LOGGER.error(f"Socket message type is invalid: {str(msg.type)}")
                        continue
                    
                    if not await self._msg_listener(msg.data):
                        # The message listener received a disconnect message or other failure
                        _LOGGER.info("Restarting Websocket due to device status message")
                        await self._msg_listener(None) # tell message listener to read the door status
                        break

        self._websocket = None

        if self._running:
            # Just keep reconnecting - The AladdinConect app just reconnects forever.
            _LOGGER.info("Reconnecting...")
            self._run_future = asyncio.get_event_loop().create_task(self._run())

    async def set_auth_token(self,access_token):
        self._access_token = access_token
        await self.stop()
        await self.start()

    async def start(self):
        if self._running is False:
            _LOGGER.info("Starting the event service")
            self._running = True
            self._run_future = asyncio.get_event_loop().create_task(self._run())
        else:
            _LOGGER.info("Trying to start an already running event service")

    async def stop(self):
        _LOGGER.info("Stopping the event service")
        self._running = False
        if not self._websocket:
            return
        await self._websocket.close()
        self._websocket = None
        self._run_future.cancel()
        self._run_future = None