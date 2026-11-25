# Test: BME280 / BMP280 sensor (I2C1: SDA = GP26, SCL = GP27)
from machine import I2C, Pin
from bme280 import BME280
import time

i2c = I2C(1, sda=Pin(26), scl=Pin(27))
print("I2C1:", [hex(a) for a in i2c.scan()])    # expect 0x76

sensor = BME280(i2c)

for _ in range(5):
    print("Temperature: {:.1f} C  Pressure: {:.1f} hPa".format(sensor.temperature(), sensor.pressure()))
    time.sleep(1)