
import dioda
import buczek
from machine import Timer
import machine
import time

def brak_zas(timer):
  dioda.zasieg()
  print('brak_zas')
  machine.reset()


def receive(lora):
    print("LoRa Receiver")
    time.sleep(3)
    dioda.on_boot()
    timer = Timer(0)
    timer.init(period=120000, mode=Timer.PERIODIC, callback=brak_zas) #czas na odebranie pakietu

    while True:
      if lora.received_packet():
        #try:
        timer.init(period=120000, mode=Timer.PERIODIC, callback=brak_zas)
        #except KeyboardInterrupt:
          #timer.deinit()
        print('odbiera')
        payload = lora.read_payload()
        print(payload)
        if (payload==b'ok'):
          print('peyload=ok')
          #buczek.sound(10)
          dioda.ok()
        elif (payload==b'awaria'):
          print('peyload=awaria')
          buczek.awaria()
        else:
          #buczek.sound(100)
          dioda.zasieg()
          print('blad odbioru')
        print(lora.packet_rssi())
        print(lora.packet_snr())

