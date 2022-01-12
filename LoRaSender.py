from machine import Pin
from time import sleep


def send(lora):
    #counter = 0
    print("LoRa Sender")
    p4 = Pin(4,Pin.IN,Pin.PULL_UP)

    while True:
        #payload = 'Hello ({0})'.format(counter)
        if (p4.value()==1):
          payload = 'ok'
        else:
          payload='awaria'
        print("Sending packet: \n{}\n".format(payload))
        lora.println(payload)

        #counter += 1
        sleep(3)
