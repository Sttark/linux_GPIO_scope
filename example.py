import pigpio_lgpio as gpio
import time

# Create GPIO instance 
pi = gpio.GPIO()

# Set pin 4 to input with pullup
pi.set_mode(4, gpio.INPUT, flag=gpio.SET_PULL_UP) 

# Set pin 5 to output, default is low
pi.set_mode(5, gpio.OUTPUT)

# Read pin 4 
print(pi.read(4))

# Write high to pin 5
pi.write(5, 1) 

# Add rising edge callback to pin 4
def my_callback(pin, level, tick):
  print("Rising edge detected on ", pin)

cb1 = pi.callback(4, gpio.RISING_EDGE, my_callback) 

# Add falling edge callback
def my_callback2(pin, level, tick):
  print("Falling edge detected on ", pin)

cb2 = pi.callback(4, gpio.FALLING_EDGE, my_callback2)

# Software PWM on pin 5
pi.software_PWM(5, 50, 75) 

time.sleep(5)

# Change software PWM
pi.software_PWM(5, 100, 50)

time.sleep(5)

# Stop software PWM
pi.software_PWM(5, 0)

# Hardware PWM on pin 18
pi.hardware_PWM(18, 2000, 25)

time.sleep(5)

# Change hardware PWM
pi.hardware_PWM(18, 5000, 75) 

time.sleep(5)

# Stop hardware PWM
pi.hardware_PWM(18, 0)

# Stop callbacks
cb1.cancel() 
cb2.cancel()