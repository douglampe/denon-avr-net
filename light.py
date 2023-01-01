"""Light Entity for a Denon AVR via TCP/IP."""
import asyncio
import logging

import voluptuous as vol
from homeassistant.components.light import (ATTR_BRIGHTNESS, PLATFORM_SCHEMA,
                                            SUPPORT_BRIGHTNESS,
                                            VALID_BRIGHTNESS)
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (CONF_HOST, CONF_ICON, CONF_LIGHTS, CONF_NAME,
                                 CONF_PORT, SERVICE_TURN_ON, STATE_OFF,
                                 STATE_ON)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform, service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, ServiceCall

from . import DOMAIN, DenonTcpClient
from .switch import DenonNetworkSwitch

_LOGGER = logging.getLogger(__name__)

CONF_ZONE = "zone"
CONF_ON_COMMAND = "on_command"
CONF_OFF_COMMAND = "off_command"
CONF_LEVEL_PREFIX = "level_prefix"
CONF_MIN = "min"
CONF_MAX = "max"
CONF_SPACE_AFTER_PREFIX = "space_after_prefix"

DEFAULT_PORT = 23

LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ON_COMMAND): cv.string,
        vol.Required(CONF_OFF_COMMAND): cv.string,
        vol.Required(CONF_LEVEL_PREFIX): cv.string,
        vol.Optional(CONF_ICON): cv.string,
        vol.Required(CONF_MIN): cv.positive_int,
        vol.Required(CONF_MAX): cv.positive_int,
        vol.Optional(CONF_SPACE_AFTER_PREFIX): cv.boolean,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_LIGHTS, default=[]): vol.All(cv.ensure_list, [LIGHT_SCHEMA]),
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
    entities = []

    for light_config in config[CONF_LIGHTS]:
        entities.append(
            DenonNetworkLight(
                light_config[CONF_NAME],
                host,
                port,
                light_config[CONF_ON_COMMAND],
                light_config[CONF_OFF_COMMAND],
                light_config[CONF_LEVEL_PREFIX],
                light_config[CONF_MIN],
                light_config[CONF_MAX],
                light_config[CONF_ICON] if CONF_ICON in light_config else None,
                light_config[CONF_SPACE_AFTER_PREFIX] if CONF_SPACE_AFTER_PREFIX in light_config else False
            )
        )

    platform = entity_platform.current_platform.get()

    # This will call Entity.set_sleep_timer(sleep_time=VALUE)
    platform.async_register_entity_service(
        SERVICE_TURN_ON,
        {
            vol.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
        },
        "set_brightness",
    )

    async_add_entities(entities, True)

async def denon_avr_light_brightness(entity: SwitchEntity, service_call: ServiceCall) -> None:
    await entity.set_brightness(service_call.data['brightness'])

class DenonNetworkLight(DenonNetworkSwitch):
    """Representation of a Denon AVR as a Switch via TCP/IP."""
    _state: str
    _host: str
    _port: int
    _level_prefix: str
    _min: int
    _max: int
    _network_loop_task: any
    _client: any
    _brightness: int
    _attributes: dict
    _space_after_prefix: bool

    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        on_command: str,
        off_command: str,
        level_prefix: str,
        min: int,
        max: int,
        icon: str,
        space_after_prefix: bool
    ) -> None:
        """Initialize the switch."""
        self._state = None
        self._host = host
        self._port = port
        self._level_prefix = level_prefix
        self._min = min
        self._max = max
        self._network_loop_task = None
        self._client = None
        self._brightness = None
        self._attributes = {}
        self._space_after_prefix = space_after_prefix

        DenonNetworkSwitch.__init__(self, name, host, port, on_command, off_command, icon, None, None)

        _LOGGER.debug("Switch configured: on command: %s; off command: %s", self.on_command, self.off_command)
        
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
        if data == self.on_command:
            self._state = STATE_ON
            updated = True
        elif data == self.off_command:
            self._state = STATE_OFF
            updated = True
        elif data.startswith(self._level_prefix):
            level_str = data[len(self._level_prefix) + (1 if self._space_after_prefix else 0):]
            if level_str.isnumeric() == True:
                raw_value = int(level_str)
                self.set_brightness(int(255 * (raw_value - self._min) / (self._max - self._min)))
                updated = True
        if updated:
            _LOGGER.debug("State updated (%s): %s brightness = %s", self.name, self._state, self._brightness)
            self.async_write_ha_state()

    @property
    def supported_features(self) -> any:
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self) -> int:
        """Retrun brightness"""
        return self._brightness

    @property
    def device_state_attributes(self) -> dict:
        """Return the attributes of the entity (if any JSON present)."""
        return self._attributes

    def turn_on(self, **kwargs) -> None:
        DenonNetworkSwitch.turn_on(self)
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        if brightness != self._brightness:
            self.set_brightness(brightness)
            raw_value = int(self._brightness * (self._max - self._min) / 255 + self._min)
            _LOGGER.debug('Sending command %s%s%s', self._level_prefix, ' ' if self._space_after_prefix else '', raw_value)
            self._client.send(f"{self._level_prefix}{' ' if self._space_after_prefix else ''}{raw_value:02d}\r".encode('utf-8'))

    def set_brightness(self, brightness: int) -> None:
        _LOGGER.debug('Setting brightness to %s', brightness)
        self._brightness = brightness
        self.update()
    
    def update(self) -> None:
        _attributes = {
            ATTR_BRIGHTNESS: self._brightness
        }