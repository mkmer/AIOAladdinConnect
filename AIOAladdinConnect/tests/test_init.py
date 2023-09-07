import aiohttp
from AIOAladdinConnect import AladdinConnectClient
import pytest
from unittest.mock import AsyncMock
import json

MESSAGE_TEXT = '{"devices": [{"is_locked": false,"family": 2,"id": 533255,"legacy_id": "F0AD4E03A9FA","ssid": "SSID","doors": [{"desired_door_status_outcome": "success","updated_at": "2022-06-21T10:32:41Z","desired_door_status": "Close","id": 635233,"user_id": 6650,"vehicle_color": "OTHER","door_index": 1,"icon": 1,"link_status": 3,"door_updated_at": "2022-06-21T10:32:41Z","created_at": "2021-12-22T14:57:57Z","desired_status": 99,"status": 4,"fault": 0,"ble_strength": 0,"is_enabled": true,"battery_level": 0,"device_id": 533222,"name": "home","vehicle_type": "OTHER"}],"user_id": 6650,"rssi": -59,"ownership": "owned","description": "","location_name": "Home","updated_at": "2022-06-21T13:18:59Z","is_updating_firmware": false,"timezone": "America/New_York","status": 1,"vendor": "GENIE","created_at": "2021-12-22T14:57:57Z","is_expired": false,"zipcode": "12345","is_enabled": true,"lua_version": "1431","serial": "F0AD4E03A9AE000","legacy_key": "3c07769cd2eac97dcef47668c54caa140d707faa","model": "02","name": "My Door Opener 2","location_id": 3254}]}'
SENT_TOKEN = "asdfjkl"


@pytest.mark.asyncio
async def test_init():
    """Test init"""
    mock = aiohttp.ClientSession
    mock.get = AsyncMock()
    mock.get.return_value.status = 200
    mock.get.return_value.text = AsyncMock(return_value=MESSAGE_TEXT)
    mock.get.return_value.json = AsyncMock(return_value=json.loads(MESSAGE_TEXT))
    mock.get.return_value.content_type = "application/json"

    mock.post = AsyncMock()
    mock.post.return_value.status = 200
    mock.post.return_value.text.return_value = "'access_token':'asdfjkl'"
    mock.post.return_value.content_type = "application/json"
    mock.post.return_value.json = AsyncMock(return_value={"access_token": SENT_TOKEN})

    mock2 = aiohttp.ClientWebSocketResponse
    mock2.ClientSession = AsyncMock()

    session = AladdinConnectClient("test_user", "test_password")
    result = await session.login()
    assert result

    token = session.auth_token()
    assert token == SENT_TOKEN

    await session.get_doors()

    await session.close()
