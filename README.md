

# CarConnectivity Plugin for Homekit
[![GitHub sourcecode](https://img.shields.io/badge/Source-GitHub-green)](https://github.com/tillsteinbach/CarConnectivity-plugin-homekit/)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/tillsteinbach/CarConnectivity-plugin-homekit)](https://github.com/tillsteinbach/CarConnectivity-plugin-homekit/releases/latest)
[![GitHub](https://img.shields.io/github/license/tillsteinbach/CarConnectivity-plugin-homekit)](https://github.com/tillsteinbach/CarConnectivity-plugin-homekit/blob/master/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/tillsteinbach/CarConnectivity-plugin-homekit)](https://github.com/tillsteinbach/CarConnectivity-plugin-homekit/issues)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/carconnectivity-plugin-homekit?label=PyPI%20Downloads)](https://pypi.org/project/carconnectivity-plugin-homekit/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/carconnectivity-plugin-homekit)](https://pypi.org/project/carconnectivity-plugin-homekit/)
[![Donate at PayPal](https://img.shields.io/badge/Donate-PayPal-2997d8)](https://www.paypal.com/donate?hosted_button_id=2BVFF5GJ9SXAJ)
[![Sponsor at Github](https://img.shields.io/badge/Sponsor-GitHub-28a745)](https://github.com/sponsors/tillsteinbach)

[CarConnectivity](https://github.com/tillsteinbach/CarConnectivity) is a python API to connect to various car services. If you want to automatically integrate the data collected from your vehicle into Apple Home this plugin will help you.

<img src="https://raw.githubusercontent.com/tillsteinbach/CarConnectivity-plugin-homekit/main/screenshots/homekit.jpg" width="200"><img src="https://raw.githubusercontent.com/tillsteinbach/CarConnectivity-plugin-homekit/main/screenshots/homekit2.jpg" width="200"><img src="https://raw.githubusercontent.com/tillsteinbach/CarConnectivity-plugin-homekit/main/screenshots/homekit3.jpg" width="200"><img src="https://raw.githubusercontent.com/tillsteinbach/CarConnectivity-plugin-homekit/main/screenshots/homekit4.jpg" width="200">

### Install using PIP
If you want to use the CarConnectivity Plugin for Homekit, the easiest way is to obtain it from [PyPI](https://pypi.org/project/carconnectivity-plugin-homekit/). Just install it using:
```bash
pip3 install carconnectivity-plugin-homekit
```
after you installed CarConnectivity

## Configuration
In your carconnectivity.json configuration add a section for the homekit plugin like this. A documentation of all possible config options can be found [here](https://github.com/tillsteinbach/CarConnectivity-plugin-homekit/tree/main/doc/Config.md).
```
{
    "carConnectivity": {
        "connectors": [
            ...
        ]
        "plugins": [
            {
                "type": "homekit",
                "config": {}
            }
        ]
    }
}
```

## Adding to ios
After CarConnectivity is started the first time with the Homekit plugin enabled it will display a QR-Code and the pin-code in the console. Use the QR code or the pin to add the bridge to the Home app. Afterwards all accessories your car offers are added to the Home app.

## A note to Docker users
CarConnectivity with Homekit will need Host or Macvlan Mode for the container. This is necessary as the bridge mode will not forward multicast which is necessary for Homekit to work. Host mode is not working on macOS. The reson is that the network is still virtualized.
If you do not like to share the host network with CarConnectivity you can use macvlan mode. In macvlan mode CarConnectivity will appear as a seperate computer in the network.

## Updates
If you want to update, the easiest way is:
```bash
pip3 install carconnectivity-plugin-homekit --upgrade
```