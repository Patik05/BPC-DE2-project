# Test: RGB LED (R = GP14, G = GP15, B = GP16) - red, green, blue for 1 s each
from machine import Pin
import time

for pin, name in ((14, "red"), (15, "green"), (16, "blue")):
    led = Pin(pin, Pin.OUT)
    print(name)
    led.value(1)
    time.sleep(1)
    led.value(0)