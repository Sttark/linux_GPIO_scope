# Linux GPIO Scope

## Linux GPIO Library for Pi 5 and Jetson

This repository provides a GPIO library for the Raspberry Pi 5 and NVIDIA Jetson platforms using the new Linux kernel GPIO userspace API.

The Raspberry Pi 5 and Jetson boards use a newer Linux kernel that is incompatible with the pigpio and piscope libraries commonly used for GPIO access in Python on earlier Raspberry Pi models. This library replicates much of the pigpio API and maps it to [lgpio](https://abyz.me.uk/lg/py_lgpio.html) to provide similar GPIO functionality on these newer boards.

### Key Features

- Implements input, output, PWM, and interrupt handling for GPIO pins
- Provides a class-based interface similar to pigpio for easy use
- Utilizes hardware PWM on GPIO 18 and 19 (and potentially 12 and 13) of the Pi 5
- Logs GPIO pin state changes to `pin_activity.log`
- Can be extended to support Jetson boards with minor modifications
- Includes a visualizer tool (`visualizer.py`) that reads pin activities from a pipe for real-time monitoring

### Usage

The GPIO class initializes lgpio and provides methods to:
- Set pin modes (input/output)
- Read and write pin levels
- Handle interrupts on input pins
- Generate software PWM on any pin
- Use hardware PWM on GPIO 18/19 of the Pi 5

Callback threads are spawned to monitor state changes on input pins and simulate PWM output. These are automatically cleaned up when monitoring is stopped.

The logging thread writes pin state changes to `pin_activity.log` in real time.

To use this library on a Pi 5 or Jetson board, simply import GPIO and instantiate it. See the code for examples. Contributions and improvements are welcome!

### Visualizer Integration

The `visualizer.py` tool is an independent Python script that provides real-time visualization of GPIO pin activities, similar to the functionality of [PiScope](https://abyz.me.uk/rpi/pigpio/piscope.html) for earlier Raspberry Pi models. This is particularly useful for debugging and monitoring GPIO applications.

#### Creating a Pipe for Pin Activity

The library includes functionality to create a named pipe (`pin_activity.pipe`) which is used to stream pin state changes. This pipe allows `visualizer.py` to read pin activities in real-time, without the need for direct access to the GPIO class or its log file.

To integrate with `visualizer.py`, the GPIO library automatically writes state changes, including pin number, state, and timestamp, to `pin_activity.pipe`. Users can start `visualizer.py`, which continuously reads from this pipe, displaying pin activities graphically.

#### Using `visualizer.py`

1. Ensure the GPIO library is initialized and running in your application.
2. Start `visualizer.py` in a separate terminal or script.
3. `visualizer.py` will begin reading pin activities from `pin_activity.pipe` and display them in real time.

This approach decouples the visualization of pin activities from the main GPIO handling logic, allowing developers to monitor GPIO state changes conveniently while focusing on the core functionality of their applications.

Contributions to enhance `visualizer.py`, including additional features for visualization and support for more complex GPIO activities, are welcome.