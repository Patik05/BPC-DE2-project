# Test: HY-SRF05 ultrasonic sensor (TRIG = GP2, ECHO = GP3)
from hcsr04 import HCSR04
import time

sensor = HCSR04(trigger_pin=2, echo_pin=3)

for _ in range(10):
    print("Distance: {:.1f} cm".format(sensor.distance_cm()))   # 250.0 = no echo
    time.sleep(0.5)