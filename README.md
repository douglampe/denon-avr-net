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
In order to reduce the number of sockets used, a single client is created for each connected AVR. Therefore, you must
configure each AVR as follows:

## Platform
```
denon_avr_net:
  - host: my.local.ip.address
```
## Switches
There are two types of switches you can configure: source and command. Source switches are used to easily select a 
source for a specified zone. Source switches are mutually exclusive and turning on any one will turn off all others
for the same zone. Command switches send a command for on and off and the command must also match the status data
in order for the switch to be updated. This works for most on/off commands such as `ZMON`/`ZMOFF` for which the
return data matches the command data. The below example shows the configuration for both types of switches:

```
switch:
  - platform: denon_avr_net
    name: 'Test Denon Net'
    host: my.local.ip.address
    sources:
      - name: Test Zone3 CD
        zone: 3
        source: CD
      - name: Test Zone3 Aux1
        zone: 3
        source: AUX1
    switches:
      - name: Test Zone3 Power Toggle
        on_command: Z3ON
        off_command: Z3OFF
```

## Light
For integer values with a min/max level, you can configure a light and use the brightness to control the level. This
works great for zone volume.

```
light:
  - platform: denon_avr_net
    name: 'Test Denon Net'
    host: my.local.ip.address
    lights:
      - name: Test Zone3 Power and Volume
        on_command: Z3ON
        off_command: Z3OFF
        level_prefix: Z3
        min: 0
        max: 99
```

## Sensor
This integration also supports a sensor which has a state matching the main power/standby status of the AVR. Additional
supported data is returned as attributes for the sensor. This is a somewhat experimental integration so, it is 
recommended to setup the sensor first. This will allow you to determine the codes for sources and commands for 
switches.

```
sensor:
  - platform: denon_avr_net
    host: my.local.ip.address
```