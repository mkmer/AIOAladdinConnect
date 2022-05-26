# AIOAladdinConnect
Python module that allows interacting with Genie Aladdin Connect devices via AIOHttp

Note that shared doors are not currently supported, only doors that are owned by your account can be controlled

## Usage
```
from AIOAladdinConnect import AladdinConnectClient

# Create session using aladdin connect credentials
client = AladdinConnectClient(email, password, callback)
await client.login("username","password",callback)
or
await client.login("username","password",None)

# Get list of available doors and their status
doors = await client.get_doors()
my_door = doors[0]

# Issue commands for doors
await client.close_door(my_door['device_id'], my_door['door_number'])
await client.open_door(my_door['device_id'], my_door['door_number'])

# Get door status from internal structure.  Must call client.get_doors() to update structure
# Door status also updates on state change from the web socket without calling client.get_doors
await client.get_door_status(my_door['device_id'], my_door['door_number'])

# Get Doorlink statys from internal structure. Mst call client.get_doors() to update structure
await client.get_door_link_status(my_door['device_id'], my_door['door_number'])

# Get Door Batery status from internal structure. Must call client.get_doors() to update structure
await client.get_battery_status(my_door['device_id'], my_door['door_number'])

```


