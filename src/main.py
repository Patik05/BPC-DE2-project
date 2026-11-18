# Libraries (upload to the Pico):
#   sh1106.py  - OLED library from the course
#   bme280.py  - BME280 library from the course
#   hcsr04.py  - https://github.com/rsc1975/micropython-hcsr04

from machine import I2C, Pin
from sh1106 import SH1106_I2C
from hcsr04 import HCSR04
from bme280 import BME280
import time

# --- pins ---
TRIG_PIN = 2
ECHO_PIN = 3
BUZZ_PIN = 13

OLED_I2C_ID = 0
OLED_SDA = 4
OLED_SCL = 5

SENS_I2C_ID = 1
SENS_SDA = 26
SENS_SCL = 27

# --- settings ---
ALARM_CM = 20           # closer than this -> buzzer beeps
MAX_CM = 200            # bar graph full scale
PERIOD_MS = 100         # measurement interval
TEMP_PERIOD_MS = 2000   # temperature read interval

LIB_SOUND_SPEED = 343.64   # m/s, fixed speed of sound inside hcsr04 library (1 / 29.1 cm/us)
LIB_NO_ECHO_CM = 250.0     # hcsr04 library returns this value when no echo comes back


def sound_speed(temp_c):
    return 331.3 + 0.606 * temp_c   # m/s (~343 m/s at 20 C)


def read_distance(sensor, temp_c):
    """Return distance in cm corrected for temperature, or None if out of range."""
    try:
        d = sensor.distance_cm()
    except OSError:     # 'Out of range'
        return None
    if abs(d - LIB_NO_ECHO_CM) < 0.01:     # no echo -> out of range
        return None
    return d * sound_speed(temp_c) / LIB_SOUND_SPEED


def draw(oled, d, temp_c, d_min, d_max):
    oled.fill(0)
    if d is None:
        oled.text("--- cm", 0, 0)
        oled.text("no echo", 0, 12)
    else:
        oled.text("{:.1f} cm".format(d), 0, 0)
        oled.text("NEAR!" if d < ALARM_CM else "ok", 0, 12)
        # bar: full = near, empty = far
        w = int(128 * (1 - min(d, MAX_CM) / MAX_CM))
        oled.rect(0, 26, 128, 10, 1)
        oled.fill_rect(0, 26, w, 10, 1)
    oled.text("{:.1f}C".format(temp_c), 80, 12)
    if d_min is not None:
        oled.text("min {:.0f} cm".format(d_min), 0, 44)
        oled.text("max {:.0f} cm".format(d_max), 0, 54)
    oled.show()


def main():
    oled_i2c = I2C(OLED_I2C_ID, sda=Pin(OLED_SDA), scl=Pin(OLED_SCL), freq=100_000)
    sens_i2c = I2C(SENS_I2C_ID, sda=Pin(SENS_SDA), scl=Pin(SENS_SCL), freq=100_000)
    oled_found = oled_i2c.scan()
    sens_found = sens_i2c.scan()
    # For Debug
    #print("I2C0 (OLED):  ", [hex(a) for a in oled_found])   # expect 0x3c
    #print("I2C1 (BME280):", [hex(a) for a in sens_found])   # expect 0x76

    if 0x3C not in oled_found:
        print("OLED not found")
        return
    oled = SH1106_I2C(oled_i2c)

    thermo = None
    if 0x76 in sens_found:
        thermo = BME280(sens_i2c)
    else:
        print("BME280 not found")

    sensor = HCSR04(trigger_pin=TRIG_PIN, echo_pin=ECHO_PIN, echo_timeout_us=30000)
    buzzer = Pin(BUZZ_PIN, Pin.OUT, value=0)

    temp_c = 20.0       # updated from BME280 (20 C until first read)
    d_min = None
    d_max = None
    last_temp = time.ticks_add(time.ticks_ms(), -TEMP_PERIOD_MS)   # read temp right away

    print("Press Ctrl+C to stop.")

    try:
        while True:
            # temperature -> speed of sound
            if thermo is not None and time.ticks_diff(time.ticks_ms(), last_temp) >= TEMP_PERIOD_MS:
                last_temp = time.ticks_ms()
                try:
                    temp_c = thermo.temperature()
                except OSError:
                    print("BME280: read error")

            d = read_distance(sensor, temp_c)
            if d is not None:
                d_min = d if d_min is None else min(d_min, d)
                d_max = d if d_max is None else max(d_max, d)

            draw(oled, d, temp_c, d_min, d_max)

            if d is not None and d < ALARM_CM:
                buzzer.value(not buzzer.value())    # toggle -> beeping
            else:
                buzzer.value(0)                     # far -> silent

            time.sleep_ms(PERIOD_MS)

    except KeyboardInterrupt:
        print("\nProgram stopped. Exiting...")
        buzzer.value(0)
        oled.fill(0)
        oled.show()
        oled.poweroff()


if __name__ == "__main__":
    main()