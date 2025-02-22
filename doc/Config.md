

# CarConnectivity Plugin for Homekit Config Options
The configuration for CarConnectivity is a .json file.
## General format
The general format is a `carConnectivity` section, followed by a list of connectors and plugins.
In the `carConnectivity` section you can set the global `log_level`.
Each connector or plugin needs a `type` attribute and a `config` section.
The `type` and config options specific to your connector or plugin can be found on their respective project page.
```json
{
    "carConnectivity": {
        "log_level": "error", // set the global log level, you can set individual log levels in the connectors and plugins
        "connectors": [
            {
                "type": "skoda", // Definition for a MySkoda account
                "config": {
                    "interval": 600, // Interval in which the server is checked in seconds
                    "username": "test@test.de", // Username of your MySkoda Account
                    "password": "testpassword123" // Password of your MySkoda Account
                }
            },
            {
                "type": "volkswagen", // Definition for a Volkswagen account
                "config": {
                    "interval": 300, // Interval in which the server is checked in seconds
                    "username": "test@test.de", // Username of your Volkswagen Account
                    "password": "testpassword123" // Username of your Volkswagen Account
                }
            }
        ],
        "plugins": [
            {
                "type": "homekit", //Minimal definition for Homekit
                "config": {}
            }
        ]
    }
}
```
### Homekit Plugin Options
These are the valid options for the Homekit plugin
```json
{
    "carConnectivity": {
        "connectors": [],
        "plugins": [
            {
                "type": "homekit", // Definition for the Homekit plugin
                "disabled": false, // You can disable plugins without removing them from the config completely
                "config": {
                    "log_level": "error", // The log level for the plugin. Otherwise uses the global log level
                    "address": "0.0.0.0", // IP interface address the homekit service should listen on
                    "port": 51234, // Port the homekit service should listen on
                    "pincode": "123-45-678", // Pincode for the accessory, if left out random pin will be displayed on console
                    "accessory_state_file": "~/.carconnectivity/homekit-accessory.state", // File for homekit to store pairing and other information
                    "accessory_config_file": "~/.carconnectivity/homekit-accessory.config", // File for homekit to store current configuration of services
                    "ignore_vins":["WZWXYZ3CZME181225", "TTGHT9NY8SF025348"], //Do not create Homekit Accessories for these VINs
                    "ignore_accessory_types": ["Climatization", "Charging"], //Do not create Homekti Accessories of tese types
                }
            }
        ]
    }
}
```

### Connector Options
Valid Options for connectors can be found here:
* [CarConnectivity-connector-skoda Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-skoda/tree/main/doc/Config.md)
* [CarConnectivity-connector-volkswagen Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-volkswagen/tree/main/doc/Config.md)
* [CarConnectivity-connector-seatcupra Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-seatcupra/tree/main/doc/Config.md)
* [CarConnectivity-connector-tronity Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-tronity/tree/main/doc/Config.md)
