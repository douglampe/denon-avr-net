"""Support for reading data for a Denon AVR via TCP/IP."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

#from denon_tcp_client import DenonTcpClient

_LOGGER = logging.getLogger(__name__)

CONF_HOST = "host"
CONF_PORT = "port"

DEFAULT_NAME = "Denon AVR TCP/IP Sensor"
DEFAULT_PORT = 23

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Denon AVR sensor platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    sensor = DenonNetworkSensor(
        name,
        host,
        port,
    )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.stop_network_read)
    async_add_entities([sensor], True)


class DenonNetworkSensor(Entity):
    """Representation of a Denon AVR as a sensor via TCP/IP."""

    def __init__(
        self,
        name,
        host,
        port,
    ):
        """Initialize the network sensor."""
        self._name = name
        self._state = None
        self._host = host
        self._port = port
        self._network_loop_task = None
        self._attributes = {}
        self._client = DenonTcpClient(self.client_data_received, host, port)

    async def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        self._network_loop_task = self.hass.loop.create_task(
            self.start_read(
                self.hass.loop,
            )
        )

    async def start_read(
        self,
        loop,
    ):
        """Read the data from the connection."""
        await self._client.start(loop)

    def client_data_received(self, key, value, client):
        _LOGGER.debug("Data updated: %s = %s", key, value)
        if key == "ZONE1":
            self._state = value.lower()
        else:
            self._attributes[key] = value
        self.async_write_ha_state()

    @callback
    def stop_network_read(self, event):
        """Close resources."""
        if self._network_loop_task:
            self._network_loop_task.cancel()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the attributes of the entity (if any JSON present)."""
        return self._attributes

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state


class DenonTcpClient(asyncio.Protocol):
    def __init__(self, listener, host, port):
        self.states = {}
        self.commands = {}
        self.queue = []

        self.listener = listener
        self.host = host
        self.port = port
        self.loop = None

    async def start(self, loop):
        if loop != None:
            self.loop = loop
        
        try:
            _LOGGER.debug('Creating connection to %s:%s', self.host, self.port)
            transport, _ = await loop.create_connection(
                lambda: self,
                self.host,
                self.port,
            )
        except Exception as exc:
            _LOGGER.exception(
                "Unable to connect to the device at address %s:%s. Will retry. Error: %s",
                self.host,
                self.port,
                exc,
            )
            await self._handle_error()
        else:
            while True:
                try:
                    on_con_lost = loop.create_future()
                    self.request_status()
                    await on_con_lost
                except Exception as exc:
                    _LOGGER.exception(
                        "Error while reading device at address %s:%s. Error: %s", 
                        self.host, 
                        self.port, 
                        exc
                    )
                    await self._handle_error()
                    break
                finally:
                    transport.close()
    
    async def _handle_error(self):
        """Handle error for TCP/IP connection."""
        await asyncio.sleep(5)
        
    def connection_made(self, transport):
        _LOGGER.debug('Connection established at %s:%s: %s', self.host, self.port, transport)

        self.transport = transport
        
        while self.queue:
            self.send(self.queue.pop(0))

    def connection_lost(self, exc):
        _LOGGER.exception("Connection lost. Attempting to reconnect. Error: %s", exc)
        asyncio.run(self.start())

    def data_received(self, data):
        _LOGGER.debug('Data received: %s', data.decode())
        self.parse(data.decode())

    def send(self, data):
        if hasattr(self, 'transport'):
            self.transport.write(data)
        else:
            _LOGGER.debug('No transport available. Queueing data: %s', repr(data))
            self.queue.append(data)

    def set_state(self, key, value):
        self.states[key] = value
        _LOGGER.debug('STATE SET: %s = %s', key, value)
        self.listener(key, value, self)
    
    def get_state(self, key):
        if key in self.states:
            return self.states[key]
        else:
            return ''

    def define_command(self, command, func):
        self.commands[command] = func

    def send_command(self, command, *argv, **kwargs):
        if command in self.commands:
            self.commands[command](*argv, **kwargs)
        else:
            _LOGGER.warning('Command not defined: %s', command)

    def parse(self, data):
        # Parse zone state
        if data.startswith('SI'):
            self.set_zone_state('ZONE1', data[2:])
        elif data.startswith('Z2'):
            self.set_zone_state('ZONE2', data[2:])
        elif data.startswith('Z3'):
            self.set_zone_state('ZONE3', data[2:])
        # Parse max volume BEFORE main volume
        elif data.startswith('MVMAX'):
            self.set_state('ZONE1_VOL_MAX', data[4:])
        # Parse main zone attributes
        elif data.startswith('MV'):
            self.set_state('ZONE1_VOL', data[2:])
        elif data.startswith('MU'):
            self.set_state('ZONE1_MUTE', data[2:])
        elif data.startswith('ZM'):
            self.set_state('ZONE1', data[2:])
        # Parse Video Select
        elif data.startswith('SV'):
            self.set_state('VIDEO_SELECT', data[2:])

    def set_zone_state(self, key, state):
        # Parse zone state
        if key == 'ON' or key == 'OFF':
            self.set_state(key, state)
        # Parse mute Zone2/3 mute
        if state == 'MUON' or state == 'MUOFF':
            self.set_state(key + '_MUTE', state[2:])
        # Parse Zone2/3 volume
        elif state.isnumeric() == True:
            self.set_state(key + '_VOL', state)
        # Otherwise this is the Zone2/3 source
        else:
            self.set_state(key + '_SOURCE', state)

    def request_status(self):
        self.send(b'SI?\r')
        self.send(b'MV?\r')
        self.send(b'ZM?\r')
        self.send(b'MU?\r')
        self.send(b'Z2?\r')
        self.send(b'Z2MU?\r')
        self.send(b'Z3?\r')
        self.send(b'Z3MU?\r')