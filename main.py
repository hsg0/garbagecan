# Garbage can lid for a Raspberry Pi Pico.
#
# VL53L0X on I2C0: SDA GP0, SCL GP1, powered from 3V3.
# A0090 9g micro servo: signal GP2, power from VBUS (5 V), ground to GND.
# Orange or white is the signal, red is 5 V, brown or black is ground.
#
# A hand at 12 cm or closer turns the servo 90 degrees anticlockwise.
# After the hand leaves, the servo returns to where it started.

from machine import I2C, Pin, PWM
import time

from vl53l0x import TimeoutError, VL53L0X

# Sensor distance is in millimeters. 12 cm = 120 mm.
OPEN_MM = 120

# A0090: 500 us is one end of travel and 2500 us is the other, so 1000 us is
# 90 degrees. Looking straight at the shaft, 1000 us -> 2000 us is anticlockwise.
# These sit away from the end stops so the motor is not held against them.
CLOSED_US = 1000
OPEN_US = 2000

# How long the space must stay clear before the lid goes back.
HOLD_MS = 1000

SERVO_PIN = 2
SDA_PIN = 0
SCL_PIN = 1


def servo_pulse(servo, microseconds):
    # 50 Hz PWM has a 20 ms period. duty_u16 is a fraction of that period.
    servo.duty_u16(microseconds * 65535 // 20000)


def open_sensor():
    # A long timeout matters: this sensor holds the I2C clock while it starts.
    i2c = I2C(0, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100000, timeout=500000)
    while True:
        found = i2c.scan()
        if 0x29 not in found:
            print("VL53L0X not found. I2C scan:", [hex(address) for address in found])
            print("Check 3V3, GND, SDA on GP0, and SCL on GP1.")
            time.sleep_ms(1000)
            continue
        try:
            return VL53L0X(i2c)
        except (TimeoutError, OSError) as error:
            print("Sensor stuck:", error)
            print("Unplug the Pico for 5 seconds, then plug it back in.")
            time.sleep_ms(1000)


def main():
    # Arm the servo before the sensor, so a sensor fault cannot leave it idle.
    servo = PWM(Pin(SERVO_PIN))
    servo.freq(50)
    # Move on every boot so a reboot is visible even before a hand is near.
    servo_pulse(servo, CLOSED_US)
    time.sleep_ms(500)
    servo_pulse(servo, OPEN_US)
    time.sleep_ms(800)
    servo_pulse(servo, CLOSED_US)

    tof = open_sensor()
    print("Ready. Opens at", OPEN_MM, "mm or closer.")
    lid_open = False
    clear_since = None

    while True:
        try:
            distance_mm = tof.ping()
        except (TimeoutError, OSError) as error:
            print("Sensor read failed:", error)
            time.sleep_ms(50)
            continue

        print("distance", distance_mm, "mm")
        hand_near = 0 <= distance_mm <= OPEN_MM

        if hand_near:
            clear_since = None
            if not lid_open:
                servo_pulse(servo, OPEN_US)
                lid_open = True
                print("open")
        elif lid_open:
            now = time.ticks_ms()
            if clear_since is None:
                clear_since = now
            elif time.ticks_diff(now, clear_since) >= HOLD_MS:
                servo_pulse(servo, CLOSED_US)
                lid_open = False
                clear_since = None
                print("closed")

        time.sleep_ms(50)


main()
