"""Sensor for reading data for a Denon AVR via TCP/IP."""
import asyncio
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_VALUE_TEMPLATE,
                                 EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import (ConfigType, DiscoveryInfoType,
                                          ServiceCall)

from . import DOMAIN, DenonTcpClient

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

async def async_setup_platform(
    hass: HomeAssistant, 
    config: ConfigType, 
    async_add_entities: AddEntitiesCallback, 
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Denon AVR sensor platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    sensor = DenonNetworkSensor(
        name,
        host,
        port,
    )

    async_add_entities([sensor], True)

class DenonNetworkSensor(Entity):
    """Representation of a Denon AVR as a sensor via TCP/IP."""
    _name: str
    _state: str
    _host: str
    _port: int
    _network_loop_task: any
    _attributes: dict

    def __init__(
        self,
        name: str,
        host: str,
        port: int,
    ) -> None:
        """Initialize the network sensor."""
        self._name = name
        self._state = None
        self._host = host
        self._port = port
        self._network_loop_task = None
        self._attributes = {}

    async def async_added_to_hass(self) -> None:
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

        self.hass.data[DOMAIN][self._host]['client'].add_listener(self.client_data_received)

    def client_data_received(self, key: str, value: str, client: DenonTcpClient) -> None:
        _LOGGER.debug("Data updated: %s = %s", key, value)
        if key == "power":
            self._state = value.lower()
        else:
            self._attributes[key] = value
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self) -> dict:
        """Return the attributes of the entity (if any JSON present)."""
        return self._attributes

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state
