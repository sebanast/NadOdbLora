import buczek
from machine import Timer

def brak_zas(timer):
  buczek.sound(2000)
  print('brak_zas')


def receive(lora):
    print("LoRa Receiver")
    timer = Timer(0)
    timer.init(period=16000, mode=Timer.PERIODIC, callback=brak_zas)

    while True:
      if lora.received_packet():
        #try:
        timer.init(period=16000, mode=Timer.PERIODIC, callback=brak_zas)
        #except KeyboardInterrupt:
          #timer.deinit()
        print('odbiera')
        payload = lora.read_payload()
        print(payload)
        if (payload==b'ok'):
          print('peyload=ok')
          buczek.sound(10)
        elif (payload==b'awaria'):
          print('peyload=awaria')
          buczek.awaria()
        else:
          buczek.sound(100)
          print('blad odbioru')
        print(lora.packet_rssi())
