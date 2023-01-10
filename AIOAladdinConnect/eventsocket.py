import aiohttp
import asyncio
import logging
import socket

from typing import Callable

# < WSMessage(type=<WSMsgType.TEXT: 1>, data='{"serial":"F0AD4E03A9FE","door":1,"door_status":4,"fault":0}', extra='')DEBUG:waiting for event message
# WSMessage(type=<WSMsgType.TEXT: 1>, data='{"serial":"F0AD4E03A9FE","door":1,"door_status":4}', extra='')
# DEBUG:waiting for event message

_LOGGER = logging.getLogger(__name__)

WSURI = "wss://event-caster.st1.gdocntl.net/updates"
# WSURI_ACK = "wss://app.apps.st1.gdocntl.net/monitor"
WS_STATUS_GOING_AWAY = 1001
WS_STATUS_UNAUTHORIZED = 3000

RECONNECT_COUNT = 3
RECONNECT_LONG_DELAY = 60


class EventSocket:
    def __init__(
        self,
        access_token,
        msg_listener: Callable[[str], None],
        session: aiohttp.ClientSession,
    ):
        self._access_token = access_token
        self._msg_listener = msg_listener
        self._running = False
        self._websocket: aiohttp.ClientWebSocketResponse = session
        self._run_future = None
        self._timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_connect=60)
        self._reconnect_tries = RECONNECT_COUNT

    async def _run(self):
        if not self._running:
            return
        _LOGGER.info("Started the web socket")
        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            async with aiohttp.ClientSession(
                timeout=self._timeout, headers=headers
            ) as session:
                async with session.ws_connect(
                    WSURI, timeout=self._timeout  # ,  heartbeat=20
                ) as ws:
                    self._websocket = ws
                    _LOGGER.info(f"Opened the web socket with header {headers}")

                    self._reconnect_tries = RECONNECT_COUNT

                    while not ws.closed:
                        _LOGGER.info("waiting for message")
                        msg = await ws.receive()
                        if not msg:
                            continue
                        _LOGGER.debug(f"event message received< {msg}")
                        if msg.type == aiohttp.WSMsgType.ERROR:
                            _LOGGER.error("Socket message error")
                            break
                        if msg.type == aiohttp.WSMsgType.PING:
                            _LOGGER.info(
                                f"Stopping receiving. Message type: {str(msg.type)}"
                            )
                            await ws.pong()
                            break
                        if msg.type == aiohttp.WSMsgType.CLOSE:
                            _LOGGER.info(
                                f"Stopping receiving. Message type: {str(msg.type)}"
                            )
                            await ws.close()
                            break
                        if msg.type in [
                            aiohttp.WSMsgType.CLOSING,
                            aiohttp.WSMsgType.CLOSED,
                        ]:
                            _LOGGER.info(
                                f"Stopping receiving. Message type: {str(msg.type)}"
                            )
                            break
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            _LOGGER.error(
                                f"Socket message type is invalid: {str(msg.type)}"
                            )
                            continue

                        if not await self._msg_listener(msg.data):
                            # The message listener received a disconnect message or other failure
                            _LOGGER.info(
                                "Restarting Websocket due to device status message"
                            )
                            await self._msg_listener(
                                None
                            )  # tell message listener to read the door status
                            break
        except (
            aiohttp.ClientConnectionError,
            aiohttp.ClientError,
            asyncio.TimeoutError,
            socket.gaierror,
        ) as er:
            _LOGGER.error("Web socket could not connect {er}")
        self._websocket = None

        if self._running:
            # Just keep reconnecting - The AladdinConect app just reconnects forever.
            self._reconnect_tries -= 1
            if self._reconnect_tries < 0:
                self._reconnect_tries = 0
                _LOGGER.info(
                    f"Waiting to reconnect long delay {RECONNECT_LONG_DELAY} seconds"
                )
                await asyncio.sleep(RECONNECT_LONG_DELAY)

            _LOGGER.info("Reconnecting...")
            self._run_future = asyncio.get_event_loop().create_task(self._run())

    async def set_auth_token(self, access_token):
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
        if self._websocket is not None:
            await self._websocket.close()
        self._websocket = None
        if self._run_future:
            await self._run_future
        self._run_future = None
