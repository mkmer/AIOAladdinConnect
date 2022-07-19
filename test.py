import aiohttp
from AIOAladdinConnect import AladdinConnectClient
import asyncio
import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
CLIENT_ID = 1000
_LOGGER = logging.getLogger(__name__)
async def main():
    async def mycallback():
        _LOGGER.debug("I've been calledback at the top")

    _LOGGER.debug("I've started")
    password = "Your password"
    username = "your username"
    session_x = aiohttp.ClientSession(timeout = aiohttp.ClientTimeout(total=30))
    session = AladdinConnectClient(username,password,session_x,CLIENT_ID)
    try:
        await session.login()
    except aiohttp.ClientConnectionError:
        _LOGGER.debug("I can not connect")
        
    auth = session.auth_token()
    doors = await session.get_doors()
    if doors:
        my_door = doors[0]['door_number']
        my_device = doors[0]['device_id']
        my_serial = doors[0]['serial']
    else:
        await session.close()
        return
    #await session.close()
    session2 = session
    # session2 = AladdinConnectClient(username,password,mycallback)
    # await session2.set_auth_token(auth)
    session2.register_callback(mycallback,my_serial)

    doors = await session2.get_doors()
    _LOGGER.debug(f"status< {doors}")
    x = 0
    c = 0
    while(1):
        doors = await session2.get_doors(my_serial)
        _LOGGER.debug(f"Doors< {doors}")
        if doors:
            door = await session2.async_get_door_status(my_device,my_door)
            if door:
                x=x+1
                _LOGGER.debug(f"status< {door}   Count {x}")
    
            await asyncio.sleep(20)
            #await session._call_back("""{"serial":"F0AD4E03A9FE","device_status":"0"}""")
        c = c + 1
        
    await session2.close()


    


asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())