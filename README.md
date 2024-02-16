# linux_GPIO_scope
**Linux GPIO Library for Pi 5 and Jetson

This repository provides a GPIO library for the Raspberry Pi 5 and NVIDIA Jetson platforms using the new Linux kernel GPIO userspace API.

The Raspberry Pi 5 and Jetson boards use a newer Linux kernel that is incompatible with the pigpio and piscope libraries commonly used for GPIO access in Python on earlier Raspberry Pi models. This library replicates much of the pigpio API and maps it to lgpio (https://abyz.me.uk/lg/py_lgpio.html.) to provide similar GPIO functionality on these newer boards.

Key features:

Implements input, output, PWM, and interrupt handling for GPIO pins
Provides a class-based interface similar to pigpio for easy use
Utilizes hardware PWM on GPIO 18 and 19 (and potentially 12 and 13) of the Pi 5
Logs GPIO pin state changes to pin_activity.log
Can be extended to support Jetson boards with minor modifications
The GPIO class initializes lgpio and provides methods to:

Set pin modes (input/output)
Read and write pin levels
Handle interrupts on input pins
Generate software PWM on any pin
Use hardware PWM on GPIO 18/19 of the Pi 5
Callback threads are spawned to monitor state changes on input pins and simulate PWM output. These are automatically cleaned up when monitoring is stopped.

The logging thread writes pin state changes to pin_activity.log in real time.

To use this library on a Pi 5 or Jetson board, simply import GPIO and instantiate it. See the code for examples. Contributions and improvements are welcome!



