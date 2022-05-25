import aiohttp
import asyncio
import logging
import json

from typing import Callable

#< WSMessage(type=<WSMsgType.TEXT: 1>, data='{"serial":"F0AD4E03A9FE","door":1,"door_status":4,"fault":0}', extra='')DEBUG:waiting for event message
# WSMessage(type=<WSMsgType.TEXT: 1>, data='{"serial":"F0AD4E03A9FE","door":1,"door_status":4}', extra='')
#DEBUG:waiting for event message

LOGGER = logging.getLogger(__name__)

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
        LOGGER.debug("Started the web socket")
        headers = {
            "Authorization": f'Bearer {self._access_token}'}
        async with aiohttp.ClientSession(timeout=self._timeout, headers=headers) as session:
            async with session.ws_connect(
                WSURI,  heartbeat=20
            ) as ws:
                self._websocket = ws
                LOGGER.debug("Opened the web socket")
                while not ws.closed:
                    LOGGER.debug("waiting for message")
                    msg = await ws.receive()
                    LOGGER.debug(f"event message received< {json.loads(msg.data)}")
                    if not msg:
                        continue
                    if msg.type == aiohttp.WSMsgType.ERROR:
                        LOGGER.error("Socket message error")
                        break
                    if msg.type in [
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.CLOSED,
                    ]:
                        LOGGER.debug(
                            f"Stopping receiving. Message type: {str(msg.type)}"
                        )
                        break
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        LOGGER.error(f"Socket message type is invalid: {str(msg.type)}")
                        continue
                    
                    await self._msg_listener(msg.data)

        self._websocket = None

        if self._running:
            # Just keep reconnecting - The AladdinConect app just reconnects forever.
            LOGGER.info("Reconnecting...")
            self._run_future = asyncio.get_event_loop().create_task(self._run())

    async def start(self):
        self._running = True
        self._run_future = asyncio.get_event_loop().create_task(self._run())

    async def stop(self):
        self._running = False
        if not self._websocket:
            return
        await self._websocket.close()
        self._websocket = None

        await self._run_future