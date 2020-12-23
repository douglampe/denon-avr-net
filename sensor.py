"""Support for reading data for a Denon AVR via TCP/IP."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from denon_tcp_client import DenonTcpClient

_LOGGER = logging.getLogger(__name__)

CONF_HOST = "host"
CONF_PORT = "port"

DEFAULT_NAME = "Denon AVR TCP/IP Sensor"
DEFAULT_PORT = 23

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
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
        self._attributes = None
        self._client = DenonTcpClient(self.client_data_received, host, port)

    async def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        self._network_loop_task = self.hass.loop.create_task(
            self.start_read(
                self.hass.loop,
                self._client,
                self._host,
                self._port,
            )
        )

    async def start_read(
        self,
        loop,
        client,
        host,
        port,
    ):
        """Read the data from the connection."""
        on_con_lost = None
        while True:
            try:
                on_con_lost = loop.create_future()
                transport, protocol = await loop.create_connection(
                    client,
                    host,
                    port,
                )
            except Exception as exc:
                _LOGGER.exception(
                    "Unable to connect to the device at address %s:%s. Will retry. Error: %s",
                    host,
                    port,
                    exc,
                )
                await self._handle_error()
            else:
                _LOGGER.info("Network device %s:%s connected", host, port)
                while True:
                    try:
                        await on_con_lost
                    finally:
                        transport.close()
                    except Exception as exc:
                        _LOGGER.exception(
                            "Error while reading device at address %s:%s. Error: %s", 
                            host, 
                            port, 
                            exc
                        )
                        await self._handle_error()
                        break

    def client_data_received(self, key, value, client):
        _LOGGER.debug("Data updated: %s = %s", key, value)
        if key == "ZONE1":
            self._state = value.lowercase()
        else:
            self._attributes[key] = value
    
    async def _handle_error(self):
        """Handle error for TCP/IP connection."""
        self._state = None
        self._attributes = None
        self.async_write_ha_state()
        await asyncio.sleep(5)

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