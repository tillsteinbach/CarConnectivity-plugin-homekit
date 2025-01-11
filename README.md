

# CarConnectivity Plugin for Homekit
[![GitHub sourcecode](https://img.shields.io/badge/Source-GitHub-green)](https://github.com/tillsteinbach/CarConnectivity-plugin-homekit/)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/tillsteinbach/CarConnectivity-plugin-homekit)](https://github.com/tillsteinbach/CarConnectivity-plugin-homekit/releases/latest)
[![GitHub](https://img.shields.io/github/license/tillsteinbach/CarConnectivity-plugin-homekit)](https://github.com/tillsteinbach/CarConnectivity-plugin-homekit/blob/master/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/tillsteinbach/CarConnectivity-plugin-homekit)](https://github.com/tillsteinbach/CarConnectivity-plugin-homekit/issues)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/carconnectivity-plugin-abrp?label=PyPI%20Downloads)](https://pypi.org/project/carconnectivity-plugin-abrp/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/carconnectivity-plugin-abrp)](https://pypi.org/project/carconnectivity-plugin-abrp/)
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
In your carconnectivity.json configuration add a section for the homekit plugin like this:
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
## Updates
If you want to update, the easiest way is:
```bash
pip3 install carconnectivity-plugin-abrp --upgrade
```