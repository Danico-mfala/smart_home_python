import threading
import asyncio
from firebase import firebase
import RPi.GPIO as GPIO
import Adafruit_DHT
import time

# Initialize Firebase
url = 'https://smarthome-5a0ae-default-rtdb.firebaseio.com/'
firebase = firebase.FirebaseApplication(url)

# Define GPIO pins
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 4
FLAME_PIN = 27
LED_PIN = 18
BUZZER_PIN = 23
LED1_PIN = 17  # GPIO pin for LED1
LED2_PIN = 22  # GPIO pin for LED2
PHOTO_PIN = 5  # GPIO pin for photoresistor
NEW_LED_PIN = 6  # GPIO pin for the new LED
SERVO_PIN = 19  # GPIO pin for the servo motor

# Define door open and close angles
DOOR_OPEN_ANGLE = 33  # Angle in degrees for door open position
DOOR_CLOSE_ANGLE = 67  # Angle in degrees for door close position

# Set up GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(FLAME_PIN, GPIO.IN)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.setup(LED1_PIN, GPIO.OUT)
GPIO.setup(LED2_PIN, GPIO.OUT)
GPIO.setup(PHOTO_PIN, GPIO.IN)  # Configure photoresistor pin as input
GPIO.setup(NEW_LED_PIN, GPIO.OUT)  # Configure new LED pin as output
GPIO.setup(SERVO_PIN, GPIO.OUT)  # Configure servo motor pin as output

# Initialize PWM for servo motor
pwm = GPIO.PWM(SERVO_PIN, 50)  # Set PWM frequency to 50Hz
pwm.start(0)  # Start PWM with duty cycle 0

# Variable to store the last state of the door
last_door_state = None

# Function to read DHT11 sensor data
def read_dht_sensor():
    humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
    return humidity, temperature

# Function to read flame sensor data
def read_flame_sensor():
    return GPIO.input(FLAME_PIN)

# Function to read light level from photoresistor
def read_light_level():
    return GPIO.input(PHOTO_PIN)

# Function to control LED1 based on Firebase data
async def control_led1():
    led1_state = firebase.get("/LED1", None)
    if led1_state == 1:
        GPIO.output(LED1_PIN, GPIO.HIGH)
        print("LED1: ON")
    else:
        GPIO.output(LED1_PIN, GPIO.LOW)
        print("LED1: OFF")

# Function to control LED2 based on Firebase data
async def control_led2():
    led2_state = firebase.get("/LED2", None)
    if led2_state == 1:
        GPIO.output(LED2_PIN, GPIO.HIGH)
        print("LED2: ON")
    else:
        GPIO.output(LED2_PIN, GPIO.LOW)
        print("LED2: OFF")

# Function to control servo motor based on door state
def control_servo(door_state):
    global last_door_state

    if door_state == last_door_state:
        return  # No change in door state, so do nothing

    if door_state == 1:
        start_angle = DOOR_CLOSE_ANGLE
        end_angle = DOOR_OPEN_ANGLE
    else:
        start_angle = DOOR_OPEN_ANGLE
        end_angle = DOOR_CLOSE_ANGLE

    step = 1 if start_angle < end_angle else -1

    for angle in range(start_angle, end_angle + step, step):
        duty_cycle = angle / 18 + 2.5
        pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(0.01)  # Reduced delay for faster movement

    pwm.ChangeDutyCycle(0)  # Stop sending signal to servo to keep it in place
    last_door_state = door_state  # Update the last state

async def update_sensors():
    while True:
        humidity, temperature = read_dht_sensor()
        flame_detected = read_flame_sensor()
        light_level = read_light_level()

        if humidity is not None and temperature is not None:
            # Batch update to Firebase
            data = {
                "Temperature": {"value": temperature},
                "Humidity": {"value": humidity},
                "FlameStatus": {"value": "Detected" if flame_detected == 0 else "Not Detected"}
            }
            firebase.patch("/", data)
            print(f"Temperature: {temperature:0.1f}°C, Humidity: {humidity:0.1f}%, Flame Status: {'Detected' if flame_detected == 0 else 'Not Detected'}")
        else:
            print("Failed to retrieve DHT11 sensor data.")

        # Control additional LED based on light level
        if light_level == 0:
            GPIO.output(NEW_LED_PIN, GPIO.LOW)
            print("New LED: OFF")
        else:
            GPIO.output(NEW_LED_PIN, GPIO.HIGH)
            print("New LED: ON")

        await asyncio.sleep(2)

async def update_actuators():
    while True:
        await asyncio.gather(control_led1(), control_led2())

        door_state = firebase.get("/Door", None)
        if door_state is not None:
            control_servo(int(door_state))

        await asyncio.sleep(0.5)

async def flame_alert():
    while True:
        flame_detected = read_flame_sensor()
        if flame_detected == 0:
            print("Flame detected! Blinking LED and sounding alarm...")
            # Update flame detection status in Firebase
            firebase.put("FlameStatus", "value", "Detected")
            while read_flame_sensor() == 0:
                GPIO.output(LED_PIN, GPIO.HIGH)
                GPIO.output(BUZZER_PIN, GPIO.HIGH)
                time.sleep(0.5)
                GPIO.output(LED_PIN, GPIO.LOW)
                GPIO.output(BUZZER_PIN, GPIO.LOW)
                time.sleep(0.5)
            print("No flame detected.")
            # Update flame detection status in Firebase
            firebase.put("FlameStatus", "value", "Not Detected")
        else:
            print("Flame not detected in loop.")
       
        await asyncio.sleep(0.1)

async def main():
    await asyncio.gather(update_sensors(), update_actuators(), flame_alert())

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
finally:
    pwm.stop()
    GPIO.cleanup()
 