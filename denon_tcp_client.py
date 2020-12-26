import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

class DenonTcpClient(asyncio.Protocol):
    def __init__(self, listener, host, port):
        self.states = {}
        self.commands = {}
        self.queue = []

        self.listener = listener
        self.host = host
        self.port = port
        self.loop = None

    async def start(self, loop):
        if loop != None:
            self.loop = loop
        
        try:
            _LOGGER.debug('Creating connection to %s:%s', self.host, self.port)
            transport, _ = await loop.create_connection(
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
                    on_con_lost = loop.create_future()
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
        asyncio.run(self.start(None))

    def data_received(self, data):
        _LOGGER.debug('Data received: %s', data.decode())
        for token in data.decode().split('\r'):
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
        self.listener(key, value, self)
    
    def get_state(self, key):
        if key in self.states:
            return self.states[key]
        else:
            return ''

    def define_command(self, command, func):
        self.commands[command] = func

    def send_command(self, command, *argv, **kwargs):
        if command in self.commands:
            self.commands[command](*argv, **kwargs)
        else:
            _LOGGER.warning('Command not defined: %s', command)

    def parse(self, data):
        # Parse zone state
        if data.startswith('PW'):
            self.set_state('POWER', data[2:])
        elif data.startswith('CV'):
            self.set_zone_state('ZONE1', data)
        elif data.startswith('SI'):
            self.set_zone_state('ZONE1', data[2:])
        elif data.startswith('Z2'):
            self.set_zone_state('ZONE2', data[2:])
        elif data.startswith('Z3'):
            self.set_zone_state('ZONE3', data[2:])
        # Parse max volume BEFORE main volume
        elif data.startswith('MVMAX'):
            self.set_state('ZONE1_VOL_MAX', data[6:])
        # Parse main zone attributes
        elif data.startswith('MV'):
            self.set_state('ZONE1_VOL', data[2:])
        elif data.startswith('MU'):
            self.set_state('ZONE1_MUTE', data[2:])
        elif data.startswith('ZM'):
            self.set_state('ZONE1', data[2:])
        # Parse Video Select
        elif data.startswith('SV'):
            self.set_state('VIDEO_SELECT', data[2:])

    def set_zone_state(self, key, state):
        # Parse zone state
        if key == 'ON' or key == 'OFF':
            self.set_state(key, state)
        # Parse mute
        if state == 'MUON' or state == 'MUOFF':
            self.set_state(key + '_MUTE', state[2:])
        # Parse quick select
        elif state.startswith('QUICK'):
            self.set_state(key + '_QUICK', state[-1:])
        # Parse channel setting
        elif state.startswith('CS'):
            self.set_zone_state('{0}_CH_SET'.format(key), state[2:])
        # Parse channel volume
        elif state.startswith('CV'):
            if state != 'CVEND' and ' ' in state:
                # Parse channel volume
                self.set_state('{0}_CH_VOL_{1}'.format(key, state[2:].split()[0]), state[2:].split()[1])
        # Parse HPF
        elif state.startswith('HPF'):
            self.set_state('{0}_HPF'.format(key), state[3:])
        # Parse Zone2/3 volume
        elif state.isnumeric() == True:
            self.set_state(key + '_VOL', state)
        # Otherwise this is source
        else:
            self.set_state(key + '_SOURCE', state)

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