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

    def connection_made(self, transport):
        _LOGGER.debug('Connection established: %s', transport)

        self.transport = transport
        
        while self.queue:
            self.send(self.queue.pop(0))

    def connection_lost(self, exc):
        _LOGGER.exception("Connection lost. Attempting to reconnect. Error: %s", exc)
        self.start()

    def data_received(self, data):
        _LOGGER.debug('Data received: %s', data.decode())
        self.parse(data.decode())

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
            print('Command not defined: ', command)

    def parse(self, data):
        # Parse zone state
        if data.startswith('SI'):
            self.set_zone_state('ZONE1', data[2:])
        elif data.startswith('Z2'):
            self.set_zone_state('ZONE2', data[2:])
        elif data.startswith('Z3'):
            self.set_zone_state('ZONE3', data[2:])
        # Parse max volume BEFORE main volume
        elif data.startswith('MVMAX'):
            self.set_state('ZONE1_VOL_MAX', data[4:])
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
        # Parse mute Zone2/3 mute
        if state == 'MUON' or state == 'MUOFF':
            self.set_state(key + '_MUTE', state[2:])
        # Parse Zone2/3 volume
        elif state.isnumeric() == True:
            self.set_state(key + '_VOL', state)
        # Otherwise this is the Zone2/3 source
        else:
            self.set_state(key + '_SOURCE', state)

    def request_status(self):
        self.send(b'SI?\r')
        self.send(b'MV?\r')
        self.send(b'ZM?\r')
        self.send(b'MU?\r')
        self.send(b'Z2?\r')
        self.send(b'Z2MU?\r')
        self.send(b'Z3?\r')
        self.send(b'Z3MU?\r')