from time import sleep
from machine import SPI, Pin
import gc

FifoTxBaseAddr = 0x00
# FifoTxBaseAddr = 0x80

# modes
MODE_LONG_RANGE_MODE = 0x80  # bit 7: 1 => LoRa mode
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX = 0x03
MODE_RX_CONTINUOUS = 0x05
MODE_RX_SINGLE = 0x06

# IRQ masks
IRQ_TX_DONE_MASK = 0x08
IRQ_PAYLOAD_CRC_ERROR_MASK = 0x20
IRQ_RX_DONE_MASK = 0x40
IRQ_RX_TIME_OUT_MASK = 0x80

# Buffer size
MAX_PKT_LENGTH = 255

__DEBUG__ = True

class SX127x:

    default_parameters = {
                'frequency': 433E6, 
                'tx_power_level': 17, 
                'signal_bandwidth': 62.5E3,    
                'spreading_factor': 9, 
                'coding_rate': 8, 
                'preamble_length': 8,
                'implicit_header': False, 
                'sync_word': 0x12, 
                'enable_CRC': False,
                'invert_IQ': False,
                }

    frfs = {169E6: (42, 64, 0),
            433E6: (108, 64, 0),
            434E6: (108, 128, 0),
            866E6: (216, 128, 0),
            868E6: (217, 0, 0),
            915E6: (228, 192, 0)}
            
    def __init__(self,
                 spi,
                 pins,
                 parameters=default_parameters):
        
        self._spi = spi
        self._pins = pins
        self._parameters = parameters
        self._lock = False

        # setting pins
        if "dio_0" in self._pins:
            self._pin_rx_done = Pin(self._pins["dio_0"], Pin.IN)
        if "ss" in self._pins:
            self._pin_ss = Pin(self._pins["ss"], Pin.OUT)
       # if "led" in self._pins:
        #    self._led_status = Pin(self._pins["led"], Pin.OUT)

        # check hardware version
        init_try = True
        re_try = 0
        while init_try and re_try < 5:
            version = self.read_register(0x42)
            re_try = re_try + 1
            if version != 0:
                init_try = False
        if version != 0x12:
            raise Exception('Invalid version.')

        if __DEBUG__:
            print("SX version: {}".format(version))

        # put in LoRa and sleep mode
        self.sleep()

        # config
        self.set_frequency(self._parameters['frequency'])
        self.set_signal_bandwidth(self._parameters['signal_bandwidth'])

        # set LNA boost
        self.write_register(0x0c, self.read_register(0x0c) | 0x03)

        # set auto AGC
        self.write_register(0x26, 0x04)

        self.set_tx_power(self._parameters['tx_power_level'])
        self._implicit_header_mode = None
        self.implicit_header_mode(self._parameters['implicit_header'])
        self.set_spreading_factor(self._parameters['spreading_factor'])
        self.set_coding_rate(self._parameters['coding_rate'])
        self.set_preamble_length(self._parameters['preamble_length'])
        self.set_sync_word(self._parameters['sync_word'])
        self.enable_CRC(self._parameters['enable_CRC'])
        self.invert_IQ(self._parameters["invert_IQ"])

        # set LowDataRateOptimize flag if symbol time > 16ms (default disable on reset)
        # self.write_register(0x26, self.read_register(0x26) & 0xF7)  # default disable on reset
        bw_parameter = self._parameters["signal_bandwidth"]
        sf_parameter = self._parameters["spreading_factor"]

        if 1000 / (bw_parameter / 2**sf_parameter) > 16:
            self.write_register(
                0x26, 
                self.read_register(0x26) | 0x08
            )

        # set base addresses
        self.write_register(0x0e, FifoTxBaseAddr)
        self.write_register(0x0f, 0x00)

        self.standby()

    def begin_packet(self, implicit_header_mode = False):
        self.standby()
        self.implicit_header_mode(implicit_header_mode)

        # reset FIFO address and paload length
        self.write_register(0x0d, FifoTxBaseAddr)
        self.write_register(0x22, 0)

    def end_packet(self):
        # put in TX mode
        self.write_register(0x01, MODE_LONG_RANGE_MODE | MODE_TX)

        # wait for TX done, standby automatically on TX_DONE
        while self.read_register(0x12) & IRQ_TX_DONE_MASK == 0:
            pass

        # clear IRQ's
        self.write_register(0x12, IRQ_TX_DONE_MASK)

        self.collect_garbage()

    def write(self, buffer):
        currentLength = self.read_register(0x22)
        size = len(buffer)

        # check size
        size = min(size, (MAX_PKT_LENGTH - FifoTxBaseAddr - currentLength))

        # write data
        for i in range(size):
            self.write_register(0x00, buffer[i])

        # update length
        self.write_register(0x22, currentLength + size)
        return size

    def set_lock(self, lock = False):
        self._lock = lock

    def println(self, msg, implicit_header = False):
        self.set_lock(True)  # wait until RX_Done, lock and begin writing.

        self.begin_packet(implicit_header)

        if isinstance(msg, str):
            message = msg.encode()
            
        self.write(message)

        self.end_packet()

        self.set_lock(False) # unlock when done writing
        self.collect_garbage()

    def get_irq_flags(self):
        irq_flags = self.read_register(0x12)
        self.write_register(0x12, irq_flags)
        return irq_flags

    def packet_rssi(self):
        rssi = self.read_register(0x1a)
        return (rssi - (164 if self._frequency < 868E6 else 157))

    def packet_snr(self):
        snr = self.read_register(0x1b)
        return snr * 0.25

    def standby(self):
        self.write_register(0x01, MODE_LONG_RANGE_MODE | MODE_STDBY)

    def sleep(self):
        self.write_register(0x01, MODE_LONG_RANGE_MODE | MODE_SLEEP)

    def set_tx_power(self, level, outputPin = 1):
        self._tx_power_level = level

        if (outputPin == 0):
            # RFO
            level = min(max(level, 0), 14)
            self.write_register(0x09, 0x70 | level)

        else:
            # PA BOOST
            level = min(max(level, 2), 17)
            self.write_register(0x09, 0xff)#0x80 | (level - 2))

    def set_frequency(self, frequency, freq_table=frfs):
        self._frequency = frequency

        self.write_register(0x06, freq_table[frequency][0])
        self.write_register(0x07, freq_table[frequency][1])
        self.write_register(0x08, freq_table[frequency][2])

    def set_spreading_factor(self, sf):
        sf = min(max(sf, 6), 12)
        self.write_register(0x31, 0xc5 if sf == 6 else 0xc3)
        self.write_register(0x37, 0x0c if sf == 6 else 0x0a)
        self.write_register(
            0x1e, 
            (self.read_register(0x1e) & 0x0f) | ((sf << 4) & 0xf0)
        )

    def set_signal_bandwidth(self, sbw):
        bins = (7.8E3, 10.4E3, 15.6E3, 20.8E3, 31.25E3, 41.7E3, 62.5E3, 125E3, 250E3)

        bw = 9

        if sbw < 10:
            bw = sbw
        else:
            for i in range(len(bins)):
                if sbw <= bins[i]:
                    bw = i
                    break

        self.write_register(
            0x1d, 
            (self.read_register(0x1d) & 0x0f) | (bw << 4)
        )

    def set_coding_rate(self, denominator):
        denominator = min(max(denominator, 5), 8)
        cr = denominator - 4
        self.write_register(
            0x1d, 
            (self.read_register(0x1d) & 0xf1) | (cr << 1)
        )

    def set_preamble_length(self, length):
        self.write_register(0x20,  (length >> 8) & 0xff)
        self.write_register(0x21,  (length >> 0) & 0xff)

    def enable_CRC(self, enable_CRC = False):
        modem_config_2 = self.read_register(0x1e)
        config = modem_config_2 | 0x04 if enable_CRC else modem_config_2 & 0xfb
        self.write_register(0x1e, config)

    def invert_IQ(self, invert_IQ):
        self._parameters["invertIQ"] = invert_IQ
        if invert_IQ:
            self.write_register(
                0x33,
                (
                    (
                        self.read_register(0x33)
                        & 0xFE
                        & 0xBF
                    )
                    | 0x40
                    | 0x00
                ),
            )
            self.write_register(0x3B, 0x19)
        else:
            self.write_register(
                0x33,
                (
                    (
                        self.read_register(0x33)
                        & 0xFE
                        & 0xBF
                    )
                    | 0x00
                    | 0x01
                ),
            )
            self.write_register(0x3B, 0x1D)

    def set_sync_word(self, sw):
        self.write_register(0x39, sw)

    def set_channel(self, parameters):
        self.standby()
        for key in parameters:
            if key == "frequency":
                self.set_frequency(parameters[key])
                continue
            if key == "invert_IQ":
                self.invert_IQ(parameters[key])
                continue
            if key == "tx_power_level":
                self.set_tx_power(parameters[key])
                continue

    def dump_registers(self):
        for i in range(128):
            print("0x{:02X}: {:02X}".format(i, self.read_register(i)), end="")
            if (i + 1) % 4 == 0:
                print()
            else:
                print(" | ", end="")

    def implicit_header_mode(self, implicit_header_mode = False):
        if self._implicit_header_mode != implicit_header_mode:  # set value only if different.
            self._implicit_header_mode = implicit_header_mode
            modem_config_1 = self.read_register(0x1d)
            config = (modem_config_1 | 0x01 
                    if implicit_header_mode else modem_config_1 & 0xfe)
            self.write_register(0x1d, config)

    def receive(self, size = 0):
        self.implicit_header_mode(size > 0)
        if size > 0: 
            self.write_register(0x22, size & 0xff)

        # The last packet always starts at FIFO_RX_CURRENT_ADDR
        # no need to reset FIFO_ADDR_PTR
        self.write_register(
            0x01, MODE_LONG_RANGE_MODE | MODE_RX_CONTINUOUS
        )

    def on_receive(self, callback):
        self._on_receive = callback

        if self._pin_rx_done:
            if callback:
                self.write_register(0x40, 0x00)
                self._pin_rx_done.irq(
                    trigger=Pin.IRQ_RISING, handler = self.handle_on_receive
                )
            else:
                self._pin_rx_done.detach_irq()

    def handle_on_receive(self, event_source):
        self.set_lock(True)              # lock until TX_Done
        irq_flags = self.get_irq_flags()

        if (irq_flags == IRQ_RX_DONE_MASK):  # RX_DONE only, irq_flags should be 0x40
            # automatically standby when RX_DONE
            if self._on_receive:
                payload = self.read_payload()
                self._on_receive(self, payload)

        elif self.read_register(0x01) != (
            MODE_LONG_RANGE_MODE | MODE_RX_SINGLE
            ):
            # no packet received.
            # reset FIFO address / # enter single RX mode
            self.write_register(0x0d, 0x00)
            self.write_register(
                0x01, 
                MODE_LONG_RANGE_MODE | MODE_RX_SINGLE
            )

        self.set_lock(False)             # unlock in any case.
        self.collect_garbage()
        return True

    def received_packet(self, size = 0):
        irq_flags = self.get_irq_flags()

        self.implicit_header_mode(size > 0)
        if size > 0: 
            self.write_register(0x22, size & 0xff)

        # if (irq_flags & IRQ_RX_DONE_MASK) and \
           # (irq_flags & IRQ_RX_TIME_OUT_MASK == 0) and \
           # (irq_flags & IRQ_PAYLOAD_CRC_ERROR_MASK == 0):

        if (irq_flags == IRQ_RX_DONE_MASK):  
            # RX_DONE only, irq_flags should be 0x40
            # automatically standby when RX_DONE
            return True
 
        elif self.read_register(0x01) != (MODE_LONG_RANGE_MODE | MODE_RX_SINGLE):
            # no packet received.
            # reset FIFO address / # enter single RX mode
            self.write_register(0x0d, 0x00)
            self.write_register(
                0x01, 
                MODE_LONG_RANGE_MODE | MODE_RX_SINGLE
            )

    def read_payload(self):
        # set FIFO address to current RX address
        # fifo_rx_current_addr = self.read_register(0x10)
        self.write_register(
            0x0d, 
            self.read_register(0x10)
        )

        # read packet length
        if self._implicit_header_mode:
            packet_length = self.read_register(0x22)  
        else:
            packet_length = self.read_register(0x13)

        payload = bytearray()
        for i in range(packet_length):
            payload.append(self.read_register(0x00))

        self.collect_garbage()
        return bytes(payload)

    def read_register(self, address, byteorder = 'big', signed = False):
        response = self.transfer(address & 0x7f)
        return int.from_bytes(response, byteorder)

    def write_register(self, address, value):
        self.transfer(address | 0x80, value)


    def transfer(self, address, value = 0x00):
        response = bytearray(1)

        self._pin_ss.value(0)

        self._spi.write(bytes([address]))
        self._spi.write_readinto(bytes([value]), response)

        self._pin_ss.value(1)

        return response


    def collect_garbage(self):
        gc.collect()
        if __DEBUG__:
            print('[Memory - free: {}   allocated: {}]'.format(gc.mem_free(), gc.mem_alloc()))
