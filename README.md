# AIOAladdinConnect
Python module that allows interacting with Genie Aladdin Connect devices via AIOHttp

Note that shared doors are not currently supported, only doors that are owned by your account can be controlled

## Usage
```
from AIOAladdinConnect import AladdinConnectClient

# Create session using aladdin connect credentials
client_id = 1000
client_session = aiohttp.ClientSession(timeout = aiohttp.ClientTimeout(total=30))
client = AladdinConnectClient(email, password, client_session, client_id)
await client.login()

# Get list of available doors and their status
doors = await client.get_doors()
my_door = doors[0]

# Issue commands for doors
await client.close_door(my_door['device_id'], my_door['door_number'])
await client.open_door(my_door['device_id'], my_door['door_number'])

# Get door status from internal structure.  Must call client.get_doors() to update structure
# Door status also updates on state change from the web socket without calling client.get_doors
await client.async_get_door_status(my_door['device_id'], my_dooregister_callbackr['door_number'])
client.get_door_status(my_door['device_id'], my_door['door_number'])

# Get Doorlink statys from internal structure. Must call client.get_doors() to update structure
await client.async_get_door_link_status(my_door['device_id'], my_door['door_number'])
client.get_door_link_status(my_door['device_id'], my_door['door_number'])

# Get Door Batery status from internal structure. Must call client.get_doors() to update structure
client.get_battery_status(my_door['device_id'], my_door['door_number'])
client.get_rssi_status(my_door['device_id'], my_door['door_number'])
client.get_ble_strength(my_door['device_id'], my_door['door_number'])

ble_strength and battery_status are utilized with the retrofit devices (ALKT1-RB) where the door 
position sensor has a BLE connection and battery level reported.  Other devices (actual door openers)
tend to report 0 for these values.


Async versions by appending async (example):
await client.async_get_battery_status(my_door['device_id'], my_door['door_number'])
await client.async_get_rssi_status(my_door['device_id'], my_door['door_number'])
await client.aycn_get_ble_strength(my_door['device_id'], my_door['door_number'])


#assign callback for event based status updates:
client.register_callback(your_callback_function)

#Close the sockets at the end of a session:
client.close()

#Get the authtoken after login
token = client.auth_token()

#Set the authtoken if known (can skip login)
client.set_auth_token(token)

```


