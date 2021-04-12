"""The denon_avr_net component."""
import logging
import json
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SWITCHES

from .denon_tcp_client import DenonTcpClient

DOMAIN = 'denon_avr_net'

ATTR_HOST = 'host'
ATTR_COMMAND = 'command'
DEFAULT_HOST = 'none'
DEFAULT_COMMAND = 'SI?'

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):

    def handle_raw_command(call):
        host = call.data.get(ATTR_HOST, DEFAULT_HOST)

        if host != DEFAULT_HOST:
            command = call.data.get(ATTR_COMMAND, DEFAULT_COMMAND)
            client = hass.data[DOMAIN][host]['client']
            client.send('{0}\r'.format(command).encode('utf-8'))

    await hass.services.async_register(DOMAIN, "raw_command", handle_raw_command)
    
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
                asyncio.get_event_loop().run_until_complete(client.async_added_to_hass(hass))

        _LOGGER.info('Data: %s', hass.data[DOMAIN])

    return True