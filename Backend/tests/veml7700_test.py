from light import LightSensor
import board
import busio


# Initialize the I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

light_sensor = LightSensor(I2C=i2c)


veml_lux = light_sensor.get_light_intensity_veml()

print(f"VEML7700 Lux: {veml_lux}")