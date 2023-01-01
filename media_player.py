"""Media Player Entity for a Denon AVR via TCP/IP."""
import asyncio
import logging
from typing import List

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.media_player import (SUPPORT_SELECT_SOURCE,
                                                   SUPPORT_TURN_OFF,
                                                   SUPPORT_TURN_ON,
                                                   SUPPORT_VOLUME_MUTE,
                                                   SUPPORT_VOLUME_SET,
                                                   SUPPORT_VOLUME_STEP,
                                                   MediaPlayerEntity)
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_ICON, CONF_NAME, CONF_PORT,
                                 CONF_SOURCE, CONF_TYPE, CONF_VALUE_TEMPLATE,
                                 EVENT_HOMEASSISTANT_STOP, STATE_OFF, STATE_ON)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, ServiceCall

from . import DOMAIN, DenonTcpClient

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
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_ZONES, default=[]): vol.All(cv.ensure_list, [ZONE_SCHEMA]),
        vol.Optional(CONF_SOURCES, default=[]): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    }
)

async def async_setup_platform(
    hass: HomeAssistant, 
    config: ConfigType, 
    async_add_entities: AddEntitiesCallback, 
    discovery_info: DiscoveryInfoType | None = None
) -> None:
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
    _name : str
    _host: str
    _port: int
    _on_command: str
    _off_command: str
    _mute_on_command: str
    _mute_off_command: str
    _vol_up_command: str
    _vol_down_command: str
    _vol_prefix: str
    _source_prefix: str
    _min: int
    _max: int
    _icon: str
    _sources: dict
    _source_list: List
    _network_loop_task: any
    _client: any
    _state: str
    _volume: int
    _mute: bool
    _source: str

    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        on_command: str,
        off_command: str,
        mute_on_command: str,
        mute_off_command: str,
        vol_up_command: str,
        vol_down_command: str,
        vol_prefix: str,
        source_prefix: str,
        min: int,
        max: int,
        icon: str,
        sources: str
    ) -> None:
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

    async def async_added_to_hass(self) -> bool | None:
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

    def client_raw_data_received(self, data: str, client: DenonTcpClient) -> None:
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
                int_value = int(raw_value) if len(raw_value) == 2 else int(raw_value) / 10
                self.set_volume((int_value - self._min) / (self._max - self._min))
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
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def supported_features(self) -> any:
        return SUPPORT_SELECT_SOURCE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP
        
    @property
    def state(self) -> str:
        """Return the state of the switch."""
        return self._state

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return self._state == STATE_ON

    @property
    def is_volume_muted(self) -> bool:
        return self._mute

    @property
    def volume_level(self) -> int:
        return self._volume

    def volume_up(self) -> None:
        self._client.send(f"{self._vol_up_command}\r".encode('utf-8'))

    def volume_down(self) -> None:
        self._client.send(f"{self._vol_down_command}\r".encode('utf-8'))

    def set_volume_level(self, volume: int) -> None:
        raw_value = int(volume * (self._max - self._min) + self._min)
        if raw_value > self._max:
            raw_value = self._max
        elif raw_value < self._min:
            raw_value = self._min
        self._client.send(f"{self._vol_prefix}{raw_value:02d}\r".encode('utf-8'))

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def source(self) -> str:
        return self._source
    
    @property
    def source_list(self) -> List:
        return self._source_list

    def turn_on(self) -> None:
        """Turn on the switch"""
        self._client.send(f"{self._on_command}\r".encode('utf-8'))
    
    def turn_off(self) -> None:
        """Turn off the switch"""
        self._client.send(f"{self._off_command}\r".encode('utf-8'))
    
    def set_volume(self, volume: int) -> None:
        self._volume = volume

    def mute_volume(self, mute: bool) -> None:
        if mute == True:
            self._client.send(f"{self._mute_on_command}\r".encode('utf-8'))
        else:
            self._client.send(f"{self._mute_off_command}\r".encode('utf-8'))

    def select_source(self, source: str) -> None:
        self._client.send(f"{self._source_prefix}{self._sources[source] if source in self._sources else '?'}\r".encode('utf-8'))