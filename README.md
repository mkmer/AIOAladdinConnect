# aladdin-connect
Python module that allows interacting with Genie Aladdin Connect devices via AIOHttp

Note that shared doors are not currently supported, only doors that are owned by your account can be controlled

## Usage
```
from aladdin_connect import AladdinConnectClient

# Create session using aladdin connect credentials
client = AladdinConnectClient(email, password)
await client.login()

# Get list of available doors
doors = await client.get_doors()
my_door = doors[0]

# Issue commands for doors
await client.close_door(my_door['device_id'], my_door['door_number'])
await client.open_door(my_door['device_id'], my_door['door_number'])

# Get updated door status
await client.get_door_status(my_door['device_id'], my_door['door_number'])
```
