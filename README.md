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

## Media Player
The Media Player supports turn on/off, mute on/off, volume up/down, volume level, and source select. Sources can be
defined at the platform or zone level. Zone level source config completely replaces the platform level config for
models which do not support all inputs in all zones. A Media Player entity will be created for each configured zone.

For each source, specify the `source` value to match the code to be sent via the API and use the `name` attribute to
specify the friendly name to display to users. For each zone, you must specify commands for on/off, mute on/off,
and volume up/down. You must also supply the prefix for setting the volume level and setting the source.

```
media_player:
  - platform: denon_avr_net
    host: my.local.ip.address
    sources:
      - name: XBox
        source: GAME
      - name: Fire TV
        source: SAT/CBL
      - name: Blue-ray
        source: BD
      - name: Projector
        source: AUX1
      - name: Bluetooth
        source: NET
    zones:
      - name: Test Main Zone
        on_command: ZMON
        off_command: ZMOFF
        mute_on_command: MUON
        mute_off_command: MUOFF
        vol_up_command: MVUP
        vol_down_command: MVDOWN
        vol_prefix: MV
        source_prefix: SI
      - name: Test Zone 2
        on_command: Z2ON
        off_command: Z2OFF
        mute_on_command: Z2MUON
        mute_off_command: Z2MUOFF
        vol_up_command: Z2UP
        vol_down_command: Z2DOWN
        vol_prefix: Z2
        source_prefix: Z2
      - name: Test Zone 3
        on_command: Z3ON
        off_command: Z3OFF
        mute_on_command: Z3MUON
        mute_off_command: Z3MUOFF
        vol_up_command: Z3UP
        vol_down_command: Z3DOWN
        vol_prefix: Z3
        source_prefix: Z3
        sources:
          - name: Projector
            source: AUX1
          - name: Bluetooth
            source: NET
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
works great for zone volume. Some commands require a space between the command and the level. Set the value of the
`space_after_prefix` config to `true` to send a space between the command and the level value.

```
light:
  - platform: denon_avr_net
    host: my.local.ip.address
    lights:
      - name: Test Main Zone Power and Volume
        icon: hass:speaker-multiple
        on_command: ZMON
        off_command: ZMOFF
        level_prefix: MV
        min: 0
        max: 99
      - name: Test Zone 2 Power and Volume
        icon: hass:speaker-multiple
        on_command: Z2ON
        off_command: Z2OFF
        level_prefix: Z2
        min: 0
        max: 99
      - name: Test Zone 3 Power and Volume
        icon: hass:speaker-multiple
        on_command: Z3ON
        off_command: Z3OFF
        level_prefix: Z3
        min: 0
        max: 99
      - name: Test Zone 3 power and center channel volume
        icon: hass:speaker
        on_command: ZMON
        off_command: ZMOFF
        level_prefix: CVC
        space_after_prefix: true
        min: 38
        max: 62

```

## Sensor
This integration also supports a sensor which has a state matching the main power/standby status of the AVR. Additional
supported data is returned as attributes for the sensor. This is a somewhat experimental integration so, it is 
recommended to setup the sensor first. This will allow you to determine the codes for sources and commands for 
switches. The latest command processed by the AVR is stored in the attribute `raw_command`.

```
sensor:
  - platform: denon_avr_net
    name: Denon AVR Net Sensor
    host: my.local.ip.address
```

## Service
This integration provides a single service named `raw_command`. This service sends a raw command to the AVR and appends
`\r` to the command. Se below for an example service call which turns the main zone power on:

service: denon_avr_net.raw_command
data:
  host: 192.168.1.34
  command: ZMON