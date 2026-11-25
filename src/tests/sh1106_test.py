# Test: OLED display (I2C0: SDA = GP4, SCL = GP5)
from machine import I2C, Pin
from sh1106 import SH1106_I2C

i2c = I2C(0, sda=Pin(4), scl=Pin(5))
print("I2C0:", [hex(a) for a in i2c.scan()])    # expect 0x3c

oled = SH1106_I2C(i2c)
oled.fill(0)
oled.text("OLED test OK", 0, 0)
oled.show()