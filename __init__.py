"""The denon_avr_net component."""
import asyncio
import json
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SWITCHES
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .denon_tcp_client import DenonTcpClient

DOMAIN = 'denon_avr_net'

ATTR_HOST = 'host'
ATTR_COMMAND = 'command'
DEFAULT_HOST = 'none'
DEFAULT_COMMAND = 'SI?'

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    @callback
    def handle_raw_command(call) -> None:
        host = call.data.get(ATTR_HOST, DEFAULT_HOST)

        if host != DEFAULT_HOST:
            command = call.data.get(ATTR_COMMAND, DEFAULT_COMMAND)
            client = hass.data[DOMAIN][host]['client']
            client.send(f"{command}\r".encode('utf-8'))

    hass.services.async_register(DOMAIN, "raw_command", handle_raw_command)
    
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in config:
        for entry in config[DOMAIN]:
            if CONF_HOST in entry:
                host = entry[CONF_HOST]
                if CONF_PORT in entry:
                    port = entry[CONF_PORT]
                else:
                    port = 23
                _LOGGER.info('Setting up %s on host: %s:', DOMAIN, host)
                client = DenonTcpClient(host, port)
                
                hass.data[DOMAIN][host] = {
                    'client': client
                }
                await client.async_added_to_hass(hass)

        _LOGGER.info('Data: %s', hass.data[DOMAIN])

    return True