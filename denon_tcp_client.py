import asyncio
import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

class DenonTcpClient(asyncio.Protocol):
    def __init__(self, host, port):
        self.states = {}
        self.commands = {}
        self.queue = []

        self.listeners = []
        self.raw_listeners = []
        self.host = host
        self.port = port
        self.loop = None

    async def async_added_to_hass(self, hass):
        """Handle when an entity is about to be added to Home Assistant."""
        self.loop = hass.loop
        self._network_loop_task = hass.loop.create_task(
            self.start()
        )
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop_network_read)

    @callback
    def stop_network_read(self, event):
        """Close resources."""
        if self._network_loop_task:
            self._network_loop_task.cancel()

    async def start(self):
        try:
            _LOGGER.debug('Creating connection to %s:%s', self.host, self.port)
            transport, _ = await self.loop.create_connection(
                lambda: self,
                self.host,
                self.port,
            )
        except Exception as exc:
            _LOGGER.exception(
                "Unable to connect to the device at address %s:%s. Will retry. Error: %s",
                self.host,
                self.port,
                exc,
            )
            await self._handle_error()
        else:
            while True:
                try:
                    on_con_lost = self.loop.create_future()
                    self.request_status()
                    await on_con_lost
                except Exception as exc:
                    _LOGGER.exception(
                        "Error while reading device at address %s:%s. Error: %s", 
                        self.host, 
                        self.port, 
                        exc
                    )
                    await self._handle_error()
                    break
                finally:
                    transport.close()
    
    def add_listener(self, listener):
        self.listeners.append(listener)

    def add_raw_listener(self, listener):
        self.raw_listeners.append(listener)

    async def _handle_error(self):
        """Handle error for TCP/IP connection."""
        await asyncio.sleep(5)
        
    def connection_made(self, transport):
        _LOGGER.debug('Connection established at %s:%s: %s', self.host, self.port, transport)

        self.transport = transport
        
        while self.queue:
            self.send(self.queue.pop(0))

    def connection_lost(self, exc):
        _LOGGER.exception("Connection lost. Attempting to reconnect. Error: %s", exc)
        self.loop.create_task(
            self.start()
        )

    def data_received(self, data):
        _LOGGER.debug('Data received: %s', data.decode())
        for token in data.decode().split('\r'):
            for listener in self.raw_listeners:
                try:
                    listener(token, self)
                except Exception as err:
                    _LOGGER.error('Error invoking raw listener: %s', err)

            if token != '':
                self.set_state('raw_command', token)
            
            self.parse(token)

    def send(self, data):
        if hasattr(self, 'transport'):
            self.transport.write(data)
        else:
            _LOGGER.debug('No transport available. Queueing data: %s', repr(data))
            self.queue.append(data)

    def set_state(self, key, value):
        self.states[key] = value
        _LOGGER.debug('STATE SET: %s = %s', key, value)
        for listener in self.listeners:
            try:
                listener(key, value, self)
            except Exception as err:
                _LOGGER.error('Error invoking raw listener: %s', err)
    
    def get_state(self, key):
        if key in self.states:
            return self.states[key]
        else:
            return ''

    def parse(self, data):
        # Parse zone state
        if data.startswith('PW'):
            self.set_state('power', data[2:])
        elif data.startswith('CV'):
            self.set_zone_state('zone1', data)
        elif data.startswith('SI'):
            self.set_zone_state('zone1', data[2:])
        elif data.startswith('Z2'):
            self.set_zone_state('zone2', data[2:])
        elif data.startswith('Z3'):
            self.set_zone_state('zone3', data[2:])
        # Parse max volume BEFORE main volume
        elif data.startswith('MVMAX'):
            self.set_state('zone1_vol_max', data[6:])
        # Parse main zone attributes
        elif data.startswith('MV'):
            self.set_state('zone1_vol', data[2:])
        elif data.startswith('MU'):
            self.set_state('zone1_mute', data[2:])
        elif data.startswith('ZM'):
            self.set_state('zone1', data[2:])
        # Parse Video Select
        elif data.startswith('SV'):
            self.set_state('video_select', data[2:])
        
    def set_zone_state(self, key, state):
        # Parse zone state
        if state == 'ON' or state == 'OFF':
            self.set_state(key, state)
        # Parse mute
        elif state == 'MUON' or state == 'MUOFF':
            self.set_state('{0}_mute'.format(key), state[2:])
        # Parse quick select
        elif state.startswith('QUICK'):
            self.set_state('{0}_quick'.format(key), state[-1:])
        # Parse channel setting
        elif state.startswith('CS'):
            self.set_zone_state('{0}_ch_set'.format(key), state[2:])
        # Parse channel volume
        elif state.startswith('CV'):
            if state != 'CVEND' and ' ' in state:
                # Parse channel volume
                self.set_state('{0}_ch_vol_{1}'.format(key, state[2:].split()[0]), state[2:].split()[1])
        # Parse HPF
        elif state.startswith('HPF'):
            self.set_state('{0}_hpf'.format(key), state[3:])
        # Parse Zone2/3 volume
        elif state.isnumeric() == True:
            self.set_state(key + '_vol', state)
        # Otherwise this is source
        else:
            self.set_state(key + '_source', state)

    def request_status(self):
        self.send(b'PW?\r')
        self.send(b'MV?\r')
        self.send(b'CV?\r')
        self.send(b'MU?\r')
        self.send(b'SI?\r')
        self.send(b'ZM?\r')
        self.send(b'SR?\r')
        self.send(b'SD?\r')
        self.send(b'DC?\r')
        self.send(b'SV?\r')
        self.send(b'SLP?\r')
        self.send(b'MS?\r')
        self.send(b'Z2?\r')
        self.send(b'Z2MU?\r')
        self.send(b'Z2CS?\r')
        self.send(b'Z2CV?\r')
        self.send(b'Z2HPF?\r')
        self.send(b'Z2QUICK ?\r')
        self.send(b'Z3?\r')
        self.send(b'Z3MU?\r')
        self.send(b'Z3CS?\r')
        self.send(b'Z3CV?\r')
        self.send(b'Z3HPF?\r')
        self.send(b'Z3QUICK ?\r')
        self.send(b'SSSPC ?\r')
        self.send(b'PSCLV ?\r')
        self.send(b'PSSWL ?\r')
        self.send(b'SSLEV ?\r')