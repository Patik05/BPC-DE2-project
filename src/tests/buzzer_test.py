# Test: buzzer (GP13) - should beep 5 times
from machine import Pin
import time

buzzer = Pin(13, Pin.OUT)

while True:
    buzzer.value(1)
    time.sleep(0.001)
    buzzer.value(0)
    time.sleep(0.001)