from machine import I2C, Pin, PWM
from sh1106 import SH1106_I2C
from hcsr04 import HCSR04
from bme280 import BME280
import time

# --- pins ---
TRIG_PIN = 2
ECHO_PIN = 3
BUZZ_PIN = 13
RGB_PINS = (14, 15, 16)     # R, G, B

OLED_I2C_ID = 0
OLED_SDA = 4
OLED_SCL = 5

SENS_I2C_ID = 1
SENS_SDA = 26
SENS_SCL = 27

# --- settings ---
ALARM_CM = 20           # closer than this -> "NEAR!" on the display
MAX_CM = 200            # bar graph full scale
NEAR_CM = 10            # closer than this -> red LED, fastest beeping
FAR_CM = 100            # farther than this -> green LED, buzzer silent

BEEP_FAST_MS = 50       # buzzer on/off time at NEAR_CM or closer (fast beeping)
BEEP_SLOW_MS = 500      # buzzer on/off time at FAR_CM (slow beeping)

MEAS_PERIOD_MS = 100    # distance measurement interval
HOLD_MS = 500           # keep the last distance during short echo dropouts
TEMP_PERIOD_MS = 2000   # temperature read interval
LOOP_MS = 10            # main loop step (buzzer timing resolution)

BUZZER_ACTIVE_LOW = False   # True if the buzzer beeps on logic 0
RGB_COMMON_ANODE = False    # True if the RGB LED common pin goes to 3V3
RGB_BRIGHTNESS = 0.5        # 0.0 - 1.0

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


def closeness(d):
    """0.0 at NEAR_CM or closer, 1.0 at FAR_CM or farther."""
    t = (d - NEAR_CM) / (FAR_CM - NEAR_CM)
    return min(max(t, 0.0), 1.0)


def distance_color(d):
    """RGB levels 0.0-1.0: red (near) -> yellow -> green (far), blue = no echo."""
    if d is None:
        return (0.0, 0.0, 1.0)
    t = closeness(d)
    return (min(1.0, 2 * (1 - t)), min(1.0, 2 * t), 0.0)


def held_distance(last_d, age_ms):
    """Distance to use when there is no echo."""
    if last_d is None:
        return None
    if last_d <= NEAR_CM:   # object too close to measure (< ~3 cm) -> keep beeping fast
        return last_d
    if age_ms < HOLD_MS:    # short dropout -> keep the last value
        return last_d
    return None


def beep_interval(d):
    """Buzzer on/off time in ms: short when close, long when far, None = silent."""
    if d is None or d >= FAR_CM:
        return None
    return int(BEEP_FAST_MS + closeness(d) * (BEEP_SLOW_MS - BEEP_FAST_MS))


def set_buzzer(buzzer, on):
    buzzer.value(on != BUZZER_ACTIVE_LOW)


def set_rgb(leds, color):
    for pwm, level in zip(leds, color):
        duty = int(level * RGB_BRIGHTNESS * 65535)
        if RGB_COMMON_ANODE:
            duty = 65535 - duty
        pwm.duty_u16(duty)


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
    oled_i2c = I2C(OLED_I2C_ID, sda=Pin(OLED_SDA), scl=Pin(OLED_SCL), freq=400_000)
    sens_i2c = I2C(SENS_I2C_ID, sda=Pin(SENS_SDA), scl=Pin(SENS_SCL), freq=100_000)
    oled_found = oled_i2c.scan()
    sens_found = sens_i2c.scan()
    print("I2C0 (OLED):  ", [hex(a) for a in oled_found])   # expect 0x3c
    print("I2C1 (BME280):", [hex(a) for a in sens_found])   # expect 0x76

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
    buzzer = Pin(BUZZ_PIN, Pin.OUT)
    set_buzzer(buzzer, False)

    leds = []
    for p in RGB_PINS:
        pwm = PWM(Pin(p))
        pwm.freq(1000)
        leds.append(pwm)
    set_rgb(leds, (0.0, 0.0, 0.0))

    temp_c = 20.0       # updated from BME280 (20 C until first read)
    d_min = None
    d_max = None
    last_d = None       # last valid distance
    interval = None     # buzzer on/off time, None = silent
    buzzer_on = False
    now = time.ticks_ms()
    last_valid = now
    last_toggle = now
    last_temp = time.ticks_add(now, -TEMP_PERIOD_MS)   # read temp right away
    last_meas = time.ticks_add(now, -MEAS_PERIOD_MS)   # measure right away

    print("Press Ctrl+C to stop.")

    try:
        while True:
            now = time.ticks_ms()

            # temperature -> speed of sound
            if thermo is not None and time.ticks_diff(now, last_temp) >= TEMP_PERIOD_MS:
                last_temp = now
                try:
                    temp_c = thermo.temperature()
                except OSError:
                    print("BME280: read error")

            # distance -> display, LED colour, beep rate
            if time.ticks_diff(now, last_meas) >= MEAS_PERIOD_MS:
                last_meas = now
                d = read_distance(sensor, temp_c)
                if d is not None:
                    last_d = d
                    last_valid = now
                    d_min = d if d_min is None else min(d_min, d)
                    d_max = d if d_max is None else max(d_max, d)
                else:
                    d = held_distance(last_d, time.ticks_diff(now, last_valid))
                set_rgb(leds, distance_color(d))
                interval = beep_interval(d)
                draw(oled, d, temp_c, d_min, d_max)

            # buzzer: toggle faster when closer, slower when farther
            now = time.ticks_ms()
            if interval is None:
                buzzer_on = False
                set_buzzer(buzzer, False)
            elif time.ticks_diff(now, last_toggle) >= interval:
                last_toggle = now
                buzzer_on = not buzzer_on
                set_buzzer(buzzer, buzzer_on)

            time.sleep_ms(LOOP_MS)

    except KeyboardInterrupt:
        print("\nProgram stopped. Exiting...")
        set_buzzer(buzzer, False)
        set_rgb(leds, (0.0, 0.0, 0.0))
        oled.fill(0)
        oled.show()
        oled.poweroff()


if __name__ == "__main__":
    main()
