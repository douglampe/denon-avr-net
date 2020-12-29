"""The denon_avr_net component."""
import logging
import json
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SWITCHES

from .denon_tcp_client import DenonTcpClient

DOMAIN = 'denon_avr_net'

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
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