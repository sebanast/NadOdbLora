from sx127x import SX127x
import LoRaSender
import LoRaReceiver

#import config_lora
from machine import Pin, SPI

device_pins = {
    'miso':12,
    'mosi':13,
    'ss':5,
    'sck':14,
    'dio_0':10,
    'reset':9,
}

device_spi = SPI(1,baudrate = 10000000, polarity = 0, phase = 0)
device_spi.init(baudrate=10000000)

lora = SX127x(device_spi, pins=device_pins)


LoRaSender.send(lora)
#LoRaReceiver.receive(lora)
