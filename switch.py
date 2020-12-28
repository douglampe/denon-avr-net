"""Support for reading data for a Denon AVR via TCP/IP."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE, EVENT_HOMEASSISTANT_STOP, STATE_ON, STATE_OFF
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SOURCE, CONF_TYPE, CONF_SWITCHES, CONF_ICON
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchEntity

from . import DOMAIN
from . import DenonTcpClient

_LOGGER = logging.getLogger(__name__)

CONF_ZONE = "zone"
CONF_ON_COMMAND = "on_command"
CONF_OFF_COMMAND = "off_command"
CONF_SOURCES = "sources"

DEFAULT_PORT = 23

SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ZONE): cv.positive_int,
        vol.Required(CONF_SOURCE): cv.string,
        vol.Optional(CONF_ICON): cv.string,
    }
)

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ON_COMMAND): cv.string,
        vol.Required(CONF_OFF_COMMAND): cv.string,
        vol.Optional(CONF_ICON): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_SOURCES, default=[]): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
        vol.Optional(CONF_SWITCHES, default=[]): vol.All(cv.ensure_list, [SWITCH_SCHEMA]),
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Denon AVR Switch platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    entities = []

    for source_config in config[CONF_SOURCES]:

        name = source_config[CONF_NAME]
        zone = source_config[CONF_ZONE]
        source = source_config[CONF_SOURCE]
        icon = source_config[CONF_ICON]
        prefix = None

        if zone == 1:
            prefix = "SI"
        else:
            prefix = "Z{0}".format(zone)
        
        on_command = "{0}{1}".format(prefix, source)
        off_command = "{0}?".format(prefix)

        _LOGGER.debug("Switch config found: on command: %s; off command: %s", on_command, off_command)

        switch = DenonNetworkSwitch(
            name,
            host,
            port,
            on_command,
            off_command,
            icon,
            zone,
            source
        )

        entities.append(switch)

    for switch_config in config[CONF_SWITCHES]:
        entities.append(
            DenonNetworkSwitch(
                switch_config[CONF_NAME],
                host,
                port,
                switch_config[CONF_ON_COMMAND],
                switch_config[CONF_OFF_COMMAND],
                switch_config[CONF_ICON],
                None,
                None
            )
        )

    async_add_entities(entities, True)

class DenonNetworkSwitch(SwitchEntity):
    """Representation of a Denon AVR as a Switch via TCP/IP."""

    def __init__(
        self,
        name,
        host,
        port,
        on_command,
        off_command,
        zone,
        source
    ):
        """Initialize the network client."""
        self._name = name
        self._state = None
        self._host = host
        self._port = port
        self._on_command = on_command
        self._off_command = off_command
        self._zone = zone
        self._source = source
        self._network_loop_task = None
        self._attributes = None
        self._client = None

        _LOGGER.debug("Switch configured: on command: %s; off command: %s", self._on_command, self._off_command)
        
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
        if self._source:
            self._client.add_listener(self.client_data_received)
        else:
            self._client.add_raw_listener(self.client_raw_data_received)

    def client_data_received(self, key, value, client):
        if key == "zone{0}_source".format(self._zone):
            if value == self._source:
                self._state = STATE_ON
            else:
                self._state = STATE_OFF
            _LOGGER.debug("State updated (%s): %s", self._name, self._state)
        self.async_write_ha_state()
        
    def client_raw_data_received(self, data, client):
        updated = False
        if data == '':
            return
        if data == self._on_command:
            self._state = STATE_ON
            updated = True
        elif data == self._off_command:
            self._state = STATE_OFF
            updated = True
        if updated:
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
        self._client.send('{0}\r'.format(self._on_command).encode('utf-8'))
    
    def turn_off(self):
        """Turn off the switch"""
        self._client.send('{0}\r'.format(self._off_command).encode('utf-8'))
