"oas""Support for reading data for a Denon AVR via TCP/IP."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS, ATTR_BRIGHTNESS, ATTR_BRIGHTNESS, VALID_BRIGHTNESS
from homeassistant.const import CONF_NAME, STATE_ON, STATE_OFF, SERVICE_TURN_ON
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_LIGHTS, CONF_ICON
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform, service

from . import DOMAIN
from .switch import DenonNetworkSwitch

_LOGGER = logging.getLogger(__name__)

CONF_ZONE = "zone"
CONF_ON_COMMAND = "on_command"
CONF_OFF_COMMAND = "off_command"
CONF_LEVEL_PREFIX = "level_prefix"
CONF_MIN = "min"
CONF_MAX = "max"

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
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_LIGHTS, default=[]): vol.All(cv.ensure_list, [LIGHT_SCHEMA]),
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
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

async def denon_avr_light_brightness(entity, service_call):
    await entity.set_brightness(service_call.data['brightness'])

class DenonNetworkLight(DenonNetworkSwitch):
    """Representation of a Denon AVR as a Switch via TCP/IP."""

    def __init__(
        self,
        name,
        host,
        port,
        on_command,
        off_command,
        level_prefix,
        min,
        max,
        icon,
    ):
        """Initialize the network client."""
        self._state = None
        self._host = host
        self._port = port
        self._level_prefix = level_prefix
        self._min = min
        self._max = max
        self._network_loop_task = None
        self._attributes = None
        self._client = None
        self._brightness = None
        self._attributes = {}

        DenonNetworkSwitch.__init__(self, name, host, port, on_command, off_command, icon, None, None)

        _LOGGER.debug("Switch configured: on command: %s; off command: %s", self.on_command, self.off_command)
        
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
        if data == self.on_command:
            self._state = STATE_ON
            updated = True
        elif data == self.off_command:
            self._state = STATE_OFF
            updated = True
        elif data.startswith(self._level_prefix):
            level_str = data[len(self._level_prefix):]
            if level_str.isnumeric() == True:
                raw_value = int(level_str)
                self.set_brightness(int(255 * (raw_value - self._min) / (self._max - self._min)))
                updated = True
        if updated:
            _LOGGER.debug("State updated (%s): %s brightness = %s", self.name, self._state, self._brightness)
            self.async_write_ha_state()

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Retrun brightness"""
        return self._brightness

    @property
    def device_state_attributes(self):
        """Return the attributes of the entity (if any JSON present)."""
        return self._attributes

    def turn_on(self, **kwargs):
        DenonNetworkSwitch.turn_on(self)
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        if brightness != self._brightness:
            self.set_brightness(brightness)
            raw_value = int(self._brightness * (self._max - self._min) / 255 + self._min)
            _LOGGER.debug('Sending command %s%s', self._level_prefix, raw_value)
            self._client.send('{0}{1}\r'.format(self._level_prefix, raw_value).encode('utf-8'))

    def set_brightness(self, brightness):
        _LOGGER.debug('Setting brightness to %s', brightness)
        self._brightness = brightness
        self._attributes = {
            ATTR_BRIGHTNESS: brightness
        }
