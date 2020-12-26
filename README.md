Home Assistant Denon AVR Integration using TCP/IP

# What This is:
This is a custom component to allow control of Denon AVRs using the AVR-3312CI/AVR-3312 application model (or similar).
Since the TCP/IP interface is a low-level interface, it is unlikely to be impacted by firmware changes and also has
better performance than HTTP-based APIs.

# What It Does
Central to the integration is a sensor which listens for status data from the AVR and updates a series of attributes.
The state of the sensor follows the power on/standby status of the AVR. In addition to the sensor, switches may be
configured to enable any input source for any supported zone. Turning the switch on will set the input to the 
specified value.

# Installation
To use this custom component, add it to the `config/custom_components` folder of your installation.

```
git clone https://github.com/douglampe/denon-avr-net.git
```

# Configuration
This is a somewhat experimental integration so, it is recommended to setup the sensor first:

```
sensor:
  - platform: denon_avr_net
    host: your.local.ip.address
```