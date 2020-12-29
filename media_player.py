"""Support for reading data for a Denon AVR via TCP/IP."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE, EVENT_HOMEASSISTANT_STOP, STATE_ON, STATE_OFF
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SOURCE, CONF_TYPE, CONF_ICON
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import MediaPlayerEntity, SUPPORT_SELECT_SOURCE, SUPPORT_TURN_ON, SUPPORT_TURN_OFF
from homeassistant.components.media_player import SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP

from . import DOMAIN
from . import DenonTcpClient

_LOGGER = logging.getLogger(__name__)

CONF_ON_COMMAND = "on_command"
CONF_OFF_COMMAND = "off_command"
CONF_MUTE_ON_COMMAND = "mute_on_command"
CONF_MUTE_OFF_COMMAND = "mute_off_command"
CONF_VOL_UP_COMMAND = "vol_up_command"
CONF_VOL_DOWN_COMMAND = "vol_down_command"
CONF_VOL_PREFIX = "vol_prefix"
CONF_SOURCE_PREFIX = "source_prefix"
CONF_ZONES = "zones"
CONF_SOURCES = "sources"
CONF_MIN = "min"
CONF_MAX = "max"

DEFAULT_PORT = 23

SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SOURCE): cv.string,
    }
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ON_COMMAND): cv.string,
        vol.Required(CONF_OFF_COMMAND): cv.string,
        vol.Required(CONF_MUTE_ON_COMMAND): cv.string,
        vol.Required(CONF_MUTE_OFF_COMMAND): cv.string,
        vol.Required(CONF_VOL_UP_COMMAND): cv.string,
        vol.Required(CONF_VOL_DOWN_COMMAND): cv.string,
        vol.Required(CONF_VOL_PREFIX): cv.string,
        vol.Required(CONF_SOURCE_PREFIX): cv.string,
        vol.Optional(CONF_MIN, default=0): cv.positive_int,
        vol.Optional(CONF_MAX, default=99): cv.positive_int,
        vol.Optional(CONF_SOURCES, default=[]): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_ZONES, default=[]): vol.All(cv.ensure_list, [ZONE_SCHEMA]),
        vol.Optional(CONF_SOURCES, default=[]): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Denon AVR Switch platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    sources = {}
    entities = []

    for source_config in config[CONF_SOURCES]:
        name = source_config[CONF_NAME]
        source = source_config[CONF_SOURCE]
        sources[name] = source

    for zone_config in config[CONF_ZONES]:
        zone_sources = {}
        zone_source_config = zone_config[CONF_SOURCES]
        if len(zone_source_config) == 0:
            zone_sources = sources
        else:
            for source_config in zone_source_config:
                name = source_config[CONF_NAME]
                source = source_config[CONF_SOURCE]
                zone_sources[name] = source

        entities.append(
            DenonNetworkMediaPlayer(
                zone_config[CONF_NAME],
                host,
                port,
                zone_config[CONF_ON_COMMAND],
                zone_config[CONF_OFF_COMMAND],
                zone_config[CONF_MUTE_ON_COMMAND],
                zone_config[CONF_MUTE_OFF_COMMAND],
                zone_config[CONF_VOL_UP_COMMAND],
                zone_config[CONF_VOL_DOWN_COMMAND],
                zone_config[CONF_VOL_PREFIX],
                zone_config[CONF_SOURCE_PREFIX],
                zone_config[CONF_MIN],
                zone_config[CONF_MAX],
                zone_config[CONF_ICON] if CONF_ICON in zone_config else None,
                zone_sources,
            )
        )

    async_add_entities(entities, True)

class DenonNetworkMediaPlayer(MediaPlayerEntity):
    """Representation of a Denon AVR as a Switch via TCP/IP."""

    def __init__(
        self,
        name,
        host,
        port,
        on_command,
        off_command,
        mute_on_command,
        mute_off_command,
        vol_up_command,
        vol_down_command,
        vol_prefix,
        source_prefix,
        min,
        max,
        icon,
        sources,
    ):
        """Initialize the network client."""
        self._name = name
        self._host = host
        self._port = port
        self._on_command = on_command
        self._off_command = off_command
        self._mute_on_command = mute_on_command
        self._mute_off_command = mute_off_command
        self._vol_up_command = vol_up_command
        self._vol_down_command = vol_down_command
        self._vol_prefix = vol_prefix
        self._source_prefix = source_prefix
        self._min = min
        self._max = max
        self._icon = icon
        self._sources = sources
        self._source_list = []
        self._network_loop_task = None
        self._client = None
        self._state = None
        self._volume = None
        self._mute = None
        self._source = None

        for source in self._sources:
            _LOGGER.debug('Adding source to list: %s', source)
            self._source_list.append(source)

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
        self._client.add_raw_listener(self.client_raw_data_received)

    def client_raw_data_received(self, data, client):
        updated = False
        if data == '':
            return
        if data == self._on_command:
            self._state = STATE_ON
            updated = True
            _LOGGER.debug('%s: Power on', self._name)
        elif data == self._off_command:
            self._state = STATE_OFF
            updated = True
            _LOGGER.debug('%s: Power off', self._name)
        elif data == self._mute_on_command:
            self._mute = True
            updated = True
            _LOGGER.debug('%s: Mute on', self._name)
        elif data == self._mute_off_command:
            self._mute = False
            updated = True
            _LOGGER.debug('%s: Mute off', self._name)
        elif data.startswith(self._vol_prefix):
            raw_value = data[len(self._source_prefix):]
            if raw_value.isnumeric() == True:
                self.set_volume((int(raw_value) - self._min) / (self._max - self._min))
                updated = True
                _LOGGER.debug('%s Volume: %s', self._name, self._volume)
        elif data.startswith(self._source_prefix) and updated == False:
            raw_value = data[len(self._source_prefix):]
            for source in self._sources:
                if self._sources[source] == raw_value and source != self._source:
                    _LOGGER.debug('%s Set source: %s', self._name, source)
                    self._source = source
                    updated = True
                    break

        if updated:
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
    def supported_features(self):
        return SUPPORT_SELECT_SOURCE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP
        
    @property
    def state(self):
        """Return the state of the switch."""
        return self._state

    @property
    def is_on(self):
        """Return True if switch is on."""
        return self._state == STATE_ON

    @property
    def is_volume_muted(self):
        return self._mute

    @property
    def volume_level(self):
        return self._volume

    def volume_up(self):
        self._client.send('{0}\r'.format(self._vol_up_command).encode('utf-8'))

    def volume_down(self):
        self._client.send('{0}\r'.format(self._vol_down_command).encode('utf-8'))

    def set_volume_level(self, volume):
        raw_value = int(self._volume * (self._max - self._min) + self._min)
        self._client.send('{0}{1:02d}\r'.format(self._source_prefix, raw_value).encode('utf-8'))

    @property
    def icon(self):
        return self._icon

    @property
    def source(self):
        return self._source
    
    @property
    def source_list(self):
        return self._source_list

    def turn_on(self):
        """Turn on the switch"""
        self._client.send('{0}\r'.format(self._on_command).encode('utf-8'))
    
    def turn_off(self):
        """Turn off the switch"""
        self._client.send('{0}\r'.format(self._off_command).encode('utf-8'))
    
    def set_volume(self, volume):
        self._volume = volume

    def mute_volume(self, mute):
        if mute == True:
            self._client.send('{0}\r'.format(self._mute_on_command).encode('utf-8'))
        else:
            self._client.send('{0}\r'.format(self._mute_off_command).encode('utf-8'))

    def select_source(self, source):
        self._client.send('{0}{1}\r'.format(self._source_prefix, self._sources[source] if source in self._sources else '?').encode('utf-8'))