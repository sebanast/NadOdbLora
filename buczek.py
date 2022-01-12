from machine import Pin
import time

p2 = Pin(4, Pin.OUT)

def sound(t):
  p2.on()
  time.sleep_ms(t) 
  p2.off()

def awaria():
  for i in range(3):
    p2.on()
    time.sleep_ms(300)
    p2.off()
    time.sleep_ms(100) 
