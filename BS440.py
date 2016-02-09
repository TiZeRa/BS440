from __future__ import print_function
import pygatt.backends
import logging
from ConfigParser import SafeConfigParser
import time
from struct import *
from binascii import hexlify
from BS440decode import *
from BS440mail import *


def processIndication(handle, values):
    '''
    Indication handler
    receives indication and stores values into result Dict
    (see medisanaBLE for Dict definition)
    handle: byte
    value: bytearray
    '''
    if handle == 0x25:
        result = decodePerson(handle, values)
        log.info(str(result))
        persondata.append(result)
    elif handle == 0x1b:
        result = decodeWeight(handle, values)
        log.info(str(result))
        weightdata.append(result)
    elif handle == 0x1e:
        result = decodeBody(handle, values)
        log.info(str(result))
        bodydata.append(result)
    else:
        log.debug('Unhandled Indication encountered')

'''
Main program loop
'''
config = SafeConfigParser()
config.read('BS440.ini')

# set up logging
numeric_level = getattr(logging,
                        config.get('Program', 'loglevel').upper(),
                        None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)
logging.basicConfig(level=numeric_level,
                    format='%(asctime)s %(levelname)-8s %(funcName)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    filename=config.get('Program', 'logfile'),
                    filemode='w')
log = logging.getLogger(__name__)

ble_address = config.get('Scale', 'BLE_address')
conn_timeout = config.getint('Program', 'timeout')
'''
Start BLE comms and run that forever
'''
adapter = pygatt.backends.GATTToolBackend()
adapter.start()
while True:
    while True:
        # wait for scale to wake up and connect to it
        try:
            device = adapter.connect(ble_address, conn_timeout, 'random')
            break
        except pygatt.exceptions.NotConnectedError:
            time.sleep( 5 )
            pass

    persondata = []
    weightdata = []
    bodydata = []
    '''
    subscribe to characteristics and have processIndication
    process the data received.
    '''
    device.subscribe('00008a22-0000-1000-8000-00805f9b34fb',
                     callback=processIndication, indication=True)
    device.subscribe('00008a21-0000-1000-8000-00805f9b34fb',
                     callback=processIndication, indication=True)
    device.subscribe('00008a82-0000-1000-8000-00805f9b34fb',
                     callback=processIndication, indication=True)

    '''
    Send the unix timestamp in little endian order preceded by 02 as bytearray
    to handle 0x23. This will resync the scale's RTC.
    While waiting for a response notification, which will never arrive,
    the scale will emit 30 Indications on 0x1b and 0x1e each.
    '''
    timestamp = bytearray(pack('<I', int(time.time())))
    timestamp.insert(0, 2)
    try:
        device.char_write_handle(0x23, timestamp, wait_for_response=True)
    except pygatt.exceptions.NotificationTimeout:
        pass
    device.disconnect()
    log.info('Done receiving data from scale')
    BS440mail(config, persondata, weightdata, bodydata)