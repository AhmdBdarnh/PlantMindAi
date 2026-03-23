import serial
import struct
import time

class ElectricitySensor:
    """
    Class for handling electricity-related sensor functionality including:
    - Voltage, current, power, energy, frequency, power factor, and alarm via UART
    """
    def __init__(self):
        pass
        
    def set_electricity_sensor_pin(self):
        """Set up the UART configuration for electricity sensor"""
        # set the uart configurations
        self.__elec_uart = serial.Serial("/dev/ttyAMA1", baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=1)

        # reset energy 
        buf = [0x01, 0x42]
        crc = self.__electricity_modbus_crc16(buf)
        buf.append(crc & 0xFF)
        buf.append((crc >> 8) & 0xFF)
        # self.__send_electricity_modbus_request(buf)
        self.__elec_uart.write(buf)
        time.sleep(0.1)
        resp = self.__get_electricity_modbus_response(False)

        if resp == None:
            print("Electricity sensor not responding!")
            return False
        # check the response 
        # Correct reply: slave address + 0x42 + CRC check high byte + CRC check low byte. 

        if len(resp) != 4 or resp[0] != 0x01 or resp[1] != 0x42:
            print("Invalid response for Electricity sensor request!")
            if resp[1] == 0xC2:
                print("Electricity sensor error code: %02x", resp[2])
            return False
            
        rcvd_crc = struct.unpack("<H", resp[2:4])[0]
        calc_crc = self.__electricity_modbus_crc16(resp[:-2])
        if rcvd_crc != calc_crc:
            print("CRC mismatch!")
            return False

    def __electricity_modbus_crc16(self, data):
        """Calculate CRC16 for electricity modbus protocol"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if (crc & 0x0001):
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc
    
    def __send_electricity_modbus_request(self):
        """Send modbus request to electricity sensor"""
        modbus_req = [0x01, 0x04, 0x00, 0x00, 0x00, 0x0A]
        crc = self.__electricity_modbus_crc16(modbus_req)
        modbus_req.append(crc & 0xFF)
        modbus_req.append((crc >> 8) & 0xFF)
        # print(f"Electricity Modbus Request (hex): {''.join([f'{x:02x}' for x in modbus_req])}")
        self.__elec_uart.write(modbus_req)

    def __get_electricity_modbus_response(self, check = True):
        """Get modbus response from electricity sensor"""
        response = self.__elec_uart.read(25) # expected 25 bytes to be received
        self.__elec_uart.reset_input_buffer()

        if check == True:
            if len(response) < 25 or response[0] != 0x01 or response[1] != 0x04 or response[2] != 0x14:
                print("Invalid response for Electricity request!")
                return None
            
            rcvd_crc = struct.unpack("<H", response[23:25])[0]
            calc_crc = self.__electricity_modbus_crc16(response[:-2])
            # print(f"Electricity Modbus Response (hex): {''.join([f'{x:02x}' for x in response])}")
            if rcvd_crc != calc_crc:
                print("CRC mismatch!")
                return None
            
            return response[3:23]
        else:
            # if check is False, just return the response
            return response
    
    def get_electricity_values(self):
        """
        Get electricity values from the sensor.
        Returns voltage, current, power, energy, frequency, power_factor, alarm respectively.
        """
        try:
            self.__send_electricity_modbus_request()
            resp = self.__get_electricity_modbus_response()
            # print(f"Electricity Modbus Response (hex): {''.join([f'{x:02x}' for x in resp])}")
            if resp == None:
                return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

            # voltage is 2 bytes, current is 4 bytes, power is 4 bytes, energy is 4 bytes, frequency is 2 bytes, power factor is 2 bytes, alarm is 2 bytes
            voltage, current_l, current_h, power_l, power_h, energy_l, energy_h, frequency, power_factor, alarm = struct.unpack(">H H H H H H H H H H", resp)

            current = (current_h << 16) | current_l
            power = (power_h << 16) | power_l
            energy = (energy_h << 16) | energy_l

            
            voltage = voltage / 10.0
            current = current / 1000.0
            power = power / 10.0            
            frequency = frequency / 10.0
            power_factor = power_factor / 100.0            

            return voltage, current, power, energy, frequency, power_factor, alarm
        except Exception as err:
            print(f'Sensor Error: {err.args[0]}')
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
