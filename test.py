import aiohttp
from AIOAladdinConnect import AladdinConnectClient
import asyncio
import logging
from AIOAladdinConnect.session_manager import InvalidPasswordError

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.DEBUG)
CLIENT_ID = 1000
_LOGGER = logging.getLogger(__name__)


async def main():
    async def mycallback():
        _LOGGER.debug("I've been calledback at the top")

    _LOGGER.debug("I've started")
    password = "Your Password"
    username = "Your Username"
    session_x = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    session = AladdinConnectClient(username, password, session_x, CLIENT_ID)

    try:
        await session.login()
    except aiohttp.ClientConnectionError as er:
        _LOGGER.debug("I can not connect:  %s", er)
        await session.close()
        await session_x.close()
        return

    except InvalidPasswordError as er:
        _LOGGER.debug("Bad password:  %s", er)
        await session.close()
        await session_x.close()
        return

    auth = session.auth_token()
    doors = await session.get_doors()
    if doors:
        my_door = doors[0]["door_number"]
        my_device = doors[0]["device_id"]
        my_serial = doors[0]["serial"]
    else:
        await session.close()
        return
    # await session.close()
    # session2 = AladdinConnectClient(username,password,mycallback)
    # await session2.set_auth_token(auth)
    session.register_callback(mycallback, my_serial, my_door)

    doors = await session.get_doors()
    _LOGGER.debug(f"status< {doors}")
    x = 0
    c = 0
    while c < 2:
        doors = await session.get_doors(my_serial)
        _LOGGER.debug(f"Doors< {doors}")
        if doors:
            door = await session.async_get_door_status(my_device, my_door)
            if door:
                x = x + 1
                _LOGGER.debug(f"status< {door}   Count {x}")

            await asyncio.sleep(20)
            # await session._call_back("""{"serial":"F0AD4E03A9FE","device_status":"0"}""")
        c = c + 1

    _LOGGER.debug(f"Raw Door< {session.doors}")
    
    await session.close()
    await session_x.close()


asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
