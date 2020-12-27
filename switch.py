"""Support for reading data for a Denon AVR via TCP/IP."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE, EVENT_HOMEASSISTANT_STOP, STATE_ON, STATE_OFF
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchEntity

from . import DOMAIN
from . import DenonTcpClient

_LOGGER = logging.getLogger(__name__)

CONF_HOST = "host"
CONF_PORT = "port"
CONF_ZONE = "zone"
CONF_SOURCE = "source"

DEFAULT_PORT = 23
DEFAULT_ZONE = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_ZONE, default=DEFAULT_ZONE): cv.positive_int,
        vol.Required(CONF_SOURCE): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Denon AVR Switch platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    zone = config.get(CONF_ZONE)
    source = config.get(CONF_SOURCE)

    switch = DenonNetworkSwitch(
        name,
        host,
        port,
        zone,
        source
    )

    async_add_entities([switch], True)

class DenonNetworkSwitch(SwitchEntity):
    """Representation of a Denon AVR as a Switch via TCP/IP."""

    def __init__(
        self,
        name,
        host,
        port,
        zone,
        source
    ):
        """Initialize the network client."""
        self._name = name
        self._state = None
        self._host = host
        self._port = port
        self._zone = zone
        self._source = source
        self._network_loop_task = None
        self._attributes = None
        self._client = None
        
        if self._zone == 1:
            self._prefix = "SI"
        else:
            self._prefix = "Z{0}".format(self._zone)
        
        self._on_command = "{0}{1}\r".format(self._prefix, self._source).encode('utf-8')
        self._off_command = "{0}?\r".format(self._prefix).encode('utf-8')

    async def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        if DOMAIN not in self.hass.data:
            _LOGGER.error("Integration %s is not configured.", DOMAIN)
            return False
        if self._host not in self.hass.data[DOMAIN]:
            _LOGGER.error("Host %s not configured for integration %s.", self._host, DOMAIN)
            return False
        if 'client' not in self.hass.data[DOMAIN][self._host]:
            _LOGGER.error("Client not configured for host %s and integration %s.", self._host, DOMAIN)
            return False

        self._client = self.hass.data[DOMAIN][self._host]['client']
        self._client.add_listener(self.client_data_received)

    def client_data_received(self, key, value, client):
        if key == "zone{0}_source".format(self._zone):
            if value == self._source:
                self._state = STATE_ON
            else:
                self._state = STATE_OFF
            _LOGGER.debug("State updated (%s): %s", self._name, self._state)
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the switch."""
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
        """Return the state of the switch."""
        return self._state

    @property
    def is_on(self):
        """Return True if switch is on."""
        return self._state == STATE_ON

    def turn_on(self):
        """Turn on the switch"""
        self._client.send(self._on_command)
    
    def turn_off(self):
        """Turn off the switch"""
        self._client.send(self._off_command)
