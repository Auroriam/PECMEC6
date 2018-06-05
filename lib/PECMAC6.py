'''
    File name: PECMAC6.py
    Author: Alex Bucknall
    Organisation: Aurora Industrial Machines
    Date created: 21/04/2018
    Date last modified: 05/06/2018
    Version: v1_0_1
    Pycom Firmware Version: LoPy_v1.17.3.b1
    License: MIT
'''

from machine import I2C
import logging
import binascii
import time
from math import floor

# Log Output Priorities
ALL                                     = 0     # Display All Messages
DEBUG                                   = 10    # Display Debug Messages
INFO                                    = 20    # Display Info Messages
ERROR                                   = 40    # Display Error Messages
NONE                                    = 100   # Disable Logging

# I2C Address of the Device
PECMAC125A_DEFAULT_ADDRESS				= 0x2A  # Default I2C Address

# I2C Logical Pins
PECMAC125A_SCL                          = 'P9'  # I2C Clock - Set for LoPy
PECMAC125A_SDA                          = 'P10' # I2C Data  - Set for LoPy

# PECMAC125A Commands
PECMAC125A_COMMAND_1					= 0x01  # Read Current
PECMAC125A_COMMAND_2					= 0x02  # Read Device ID
PECMAC125A_COMMAND_3					= 0x03  # Read Calibration
PECMAC125A_COMMAND_4					= 0x04  # Calibrate
PECMAC125A_HEADER_BYTE_1				= 0x92  # Header Byte 1
PECMAC125A_HEADER_BYTE_2				= 0x6A  # Header Byte 2
PECMAC125A_RESERVED						= 0x00  # Reserved Byte
PECMAC125A_READ_DATA	                = 0x55  # Read data

# Current Sensor Channels
CHANNEL_1                               = 0x01  # Channel 1
CHANNEL_2                               = 0x02  # Channel 2
CHANNEL_3                               = 0x03  # Channel 3
CHANNEL_4                               = 0x04  # Channel 4
CHANNEL_5                               = 0x05  # Channel 5
CHANNEL_6                               = 0x06  # Channel 6
CHANNEL_7                               = 0x07  # Channel 7
CHANNEL_8                               = 0x08  # Channel 8
CHANNEL_9                               = 0x09  # Channel 9
CHANNEL_10                              = 0x0A  # Channel 10
CHANNEL_11                              = 0x0B  # Channel 11
CHANNEL_12                              = 0x0C  # Channel 12

# PECMAC125A Scale
PECMAC125A_SCALE                        = 1     # (1): mA, (1000): A

class PECMAC6():
    def __init__(self, addr=PECMAC125A_DEFAULT_ADDRESS, bus=0, pins=(PECMAC125A_SCL,PECMAC125A_SDA), channels=6, log=NONE):
        self.i2c = I2C(bus, pins=pins)
        self.addr = addr
        self.channels = channels

        logging.basicConfig(level=log) # Initialise Log Output
        self.log = logging.getLogger("")

        if self.addr not in self.i2c.scan(): # Verify I2C ADDR is available
            i2c_devices = (hex(int(i)) for i in self.i2c.scan())
            self.log.error("Error: Failed to Init I2C Addr - {}\nAvailable Addresses:".format(hex(self.addr)), *i2c_devices, sep='\n> ')
        else:
            self.log.info("I2C Addr - {}".format(hex(self.addr)))

        self.log.info("PECMAC6 Setup Complete.")

    def get_info(self): # Returns tuple of Sensor Type, Maximum Rated Current and Number of Channels
        try:
            command = [PECMAC125A_HEADER_BYTE_1, PECMAC125A_HEADER_BYTE_2, PECMAC125A_COMMAND_2, PECMAC125A_RESERVED, PECMAC125A_RESERVED, PECMAC125A_RESERVED, PECMAC125A_RESERVED]
            command.append(self.__calculate_checksum(command))
            self.log.debug("Bytes : {}".format(str(command)))
            self.i2c.writeto(self.addr, bytes(command))
            time.sleep(0.5)
            id_data = self.i2c.readfrom(self.addr, 7)
            for index, each in enumerate(id_data):
                self.log.debug("Byte {0} : {1}".format(str(index), str(each)))
            typeOfSensor, maxCurrent, noOfChannel = id_data[0], id_data[1], id_data[2]
            return (typeOfSensor, maxCurrent, noOfChannel)
        except OSError as err:
            self.log.error(err)
            return None

    def get_current(self, start, end): # Returns dict of current values for provided sensors
        total_current = {}
        if (end - start) >= 5:  # To support Pycom I2C buffer length
            x = []
            while(not start > end):
                if not ((start + 4) > end): 
                    pair = (start,start + 4)
                else:
                    pair = (start, end)
                x.append(pair)
                start += 5
            for each in x:
                currents = self.get_current(each[0],each[1])
                for current in currents:
                    total_current[current] = currents[current]
            return total_current            
        else:
            try:
                command = [PECMAC125A_HEADER_BYTE_1, PECMAC125A_HEADER_BYTE_2, PECMAC125A_COMMAND_1, start, end, PECMAC125A_RESERVED, PECMAC125A_RESERVED]
                command.append(self.__calculate_checksum(command))
                self.log.debug("Bytes : {}".format(command))
                self.i2c.writeto(self.addr, bytes(command))
                time.sleep(0.5)
                current_data = self.i2c.readfrom(self.addr, (((end-start)+1)*3)+1)
                self.__verify_checksum(current_data)
                for index, each in enumerate(current_data):
                    self.log.debug("Byte {0} : {1}".format(str(index), str(each)))
                current = {}
                for i in range(0, (end-start)+1) :
                    msb1 = current_data[i * 3]
                    msb = current_data[(1 + (i * 3))]
                    lsb = current_data[(2 + (i * 3))]
                    current["SENSOR_{}".format(start+i)] = float((msb1 * 65536) + (msb * 256) + (lsb / PECMAC125A_SCALE)) # Convert raw bytes to mA
                return current
            except OSError as err:
                self.log.error(str(err))
                return None    

    def get_calibration(self, start, end):
        command = [PECMAC125A_HEADER_BYTE_1, PECMAC125A_HEADER_BYTE_2, PECMAC125A_COMMAND_3, start, end, PECMAC125A_RESERVED, PECMAC125A_RESERVED]
        command.append(self.__calculate_checksum(command))
        self.log.debug("Bytes : {}".format(command))
        try:
            self.i2c.writeto(self.addr, bytes(command))
        except OSError as err:
            self.log.error(str(err))
            return None  
        time.sleep(0.5)
        print(((end - start + 1) * 2) + 1)
        calibration_data = self.i2c.readfrom(self.addr, (((end - start + 1) * 2) + 1))
        self.__verify_checksum(calibration_data)
        for index, each in enumerate(calibration_data):
            self.log.debug("Byte {0} : {1}".format(str(index), str(each)))
        calibration = {}
        for i in range(0, (end-start)+1) :
            msb = calibration_data[i * 2]
            lsb = calibration_data[1 + i * 2]
            calibration["SENSOR_{}".format(start+i)] = float((msb * 256) + lsb) # Convert raw bytes to mA
        return calibration
    
    def set_calibration(self):
        # TODO
        pass

    def __calculate_checksum(self, command): # Calculates Checksum for I2C write
        checksum = 0
        for each in command:
            checksum += each
        checksum &= 0xFF
        self.log.debug("Checksum : {}".format(hex(checksum)))
        return checksum

    def __verify_checksum(self, data): # Verifies Checksum for I2C read
        expected = 0
        received = int(data[-1])
        for _, byte in zip(range(len(data)-1), data):
            expected += byte
        if(expected is not received):
            self.log.error("Mismatched Checksum : {0} - {1}".format(expected, received))
