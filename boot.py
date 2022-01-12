# Complete project details at https://RandomNerdTutorials.com

try:
  import usocket as socket
except:
  import socket

import network
from machine import Pin

import esp
esp.osdebug(None)

import gc
gc.collect()

ssid = 'bbb'
password = '0987654321'

station = network.WLAN(network.STA_IF)

#station.active(True)
#station.connect(ssid, password)

#while station.isconnected() == False:
 # pass

#print('Connection successful')
#print(station.ifconfig())
exec(open("lora_main.py").read(), globals())
