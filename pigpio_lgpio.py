import lgpio
import threading
import time
import os

LOG_PIPE_NAME = "log_pipe"

# Check if the named pipe exists, if not, create it
if not os.path.exists(LOG_PIPE_NAME):
    os.mkfifo(LOG_PIPE_NAME)

class GPIO:
    """"
      BOTH_EDGES, RISING_EDGE, or FALLING_EDGE.
    """
    INPUT = 'in'
    OUTPUT = 'out'
    RISING_EDGE = lgpio.RISING_EDGE
    FALLING_EDGE = lgpio.FALLING_EDGE
    BOTH_EDGES = lgpio.BOTH_EDGES

    def __init__(self, gpiochip=4):
        self.gpiochip = lgpio.gpiochip_open(gpiochip)
        self.callback_threads = {}
        self.stop_threads = False
        self.line_modes = {}
        self.pin_activity_logs = []
        self.max_log_size = 10000
        self.log_file = 'pin_activity.log'
        self.log_lock = threading.Lock()
        self.log_thread = threading.Thread(target=self.log_writer, daemon=True)
        self.log_thread.start()

    def log_writer(self):
        while not self.stop_threads:
            time.sleep(0.1)
            with self.log_lock:
                if self.pin_activity_logs:
                    with open(LOG_PIPE_NAME, 'w') as f:
                        for event in self.pin_activity_logs:
                            f.write(str(event) + '\n')
                    self.pin_activity_logs = []

    def log_event(self, gpio, state):
        event = (gpio, state, time.time_ns())
        with self.log_lock:
            self.pin_activity_logs.append(event)
            if len(self.pin_activity_logs) > self.max_log_size:
                self.pin_activity_logs = self.pin_activity_logs[-self.max_log_size:]

    def set_mode(self, gpio, mode, level=0, flag=lgpio.SET_PULL_NONE, bouncetime=0):
        """
        Flags:
        lgpio.SET_ACTIVE_LOW
        lgpio.SET_OPEN_DRAIN
        lgpio.SET_OPEN_SOURCE
        lgpio.SET_PULL_UP
        lgpio.SET_PULL_DOWN
        lgpio.SET_PULL_NONE
        """
        self.line_modes[gpio] = mode
        self.setup(gpio, mode, level, flag, bouncetime)

    def setup(self, gpio, mode, level, flag, bouncetime):
        """
        SET_ACTIVE_LOW
        SET_OPEN_DRAIN
        SET_OPEN_SOURCE
        SET_PULL_UP
        SET_PULL_DOWN
        SET_PULL_NONE
        """
        if gpio in [18, 19]:
            raise ValueError("GPIOs 18 or 19 are reserved for hardware PWM.")
        if mode == self.INPUT:
            # gpio_claim_alert(handle, gpio, eFlags, lFlags=0, notify_handle=None)
            lgpio.gpio_claim_alert(self.gpiochip, gpio, lgpio.BOTH_EDGES, flag)
            if bouncetime:
                lgpio.gpio_set_debounce_micros(self.gpiochip, gpio, bouncetime)
            lgpio.callback(self.gpiochip, gpio, lgpio.BOTH_EDGES, self.input_callback)
            self.line_modes[gpio] = 'in'
        else:
            # gpio_claim_output(handle, gpio, level=0, lFlags=0)
            lgpio.gpio_claim_output(self.gpiochip, gpio, level, flag)
            self.line_modes[gpio] = 'out'

    def input_callback(self, chip, gpio, level, tick):
        self.log_event(gpio, level)

    def read(self, gpio):
        if self.line_modes.get(gpio) != 'in':
            raise ValueError("GPIO must be in INPUT mode to read.")
        return lgpio.gpio_read(self.gpiochip, gpio)

    def write(self, gpio, level):
        if self.line_modes.get(gpio) != 'out':
            raise ValueError("GPIO must be in OUTPUT mode to write.")
        lgpio.gpio_write(self.gpiochip, gpio, level)
        self.log_event(gpio, level)

    def callback(self, gpio, edge, callback=None):
        if self.line_modes.get(gpio) != 'in':
            raise ValueError("GPIO must be in INPUT mode to add a callback.")
        return lgpio.callback(self.gpiochip, gpio, edge, callback)

    def software_PWM(self, gpio, frequency, duty_cycle_percentage=50):
        """
        This is actually software PWM. It works on any GPIO pin, but the frequency is not guaranteed.
        """
        if self.line_modes.get(gpio) != 'out':
            raise ValueError("GPIO must be in OUTPUT mode to use PWM.")
        lgpio.tx_pwm(self.gpiochip, gpio, frequency, duty_cycle_percentage, pulse_offset=0, pulse_cycles=0)
        if not hasattr(self, 'pwm_channels'):
            self.pwm_channels = {}
        self.pwm_channels[gpio] = {'frequency': frequency, 'duty_cycle_percentage': duty_cycle_percentage}
        if frequency > 0:
            self.start_pwm_logging_thread(gpio, frequency, duty_cycle_percentage)
        else:
            self.stop_monitoring(gpio)

    def hardware_PWM(self, gpio, frequency, duty_cycle_percentage=50):
        """
        :param channel: The PWM channel number (2 for GPIO18, 3 for GPIO19).
        :param frequency: The desired frequency in Hz.
        :param duty_cycle_percentage: The duty cycle percentage (0-100%).
        
        PWM on Pi 5 is GPIO18 (/sys/class/pwm/pwmchip2/pwm2) and GPIO19 (/sys/class/pwm/pwmchip2/pwm3)
        Set 
        dtoverlay=pwm-2chan,pin=18,pin2=19,func=2,func2=2
        in /boot/firmware/config.txt
        """
        if gpio not in [18, 19]:
            raise ValueError("GPIO must be 18 or 19")
        pwm_channel_number = 2 if gpio == 18 else 3
        chip = 'pwmchip2'
        pwm_channel = f'pwm{pwm_channel_number}'
        period_ns = int(1e9 / frequency) if frequency > 0 else 0
        duty_cycle_ns = int(period_ns * (duty_cycle_percentage / 100)) if frequency > 0 else 0
        pwm_path = f'/sys/class/pwm/{chip}'
        channel_path = f'{pwm_path}/{pwm_channel}'
        if not os.path.exists(channel_path):
            with open(f'{pwm_path}/export', 'w') as f:
                f.write(str(pwm_channel_number))
        # Disable the PWM channel
        with open(f'{channel_path}/enable', 'r') as f:
            enabled = int(f.read())
        if enabled:
            with open(f'{channel_path}/enable', 'w') as f:
                f.write('0')
        if frequency > 0:
            # Read current period and duty cycle
            with open(f'{channel_path}/period', 'r') as f:
                current_period = int(f.read())
            with open(f'{channel_path}/duty_cycle', 'r') as f:
                current_duty_cycle = int(f.read())

            # If the current duty cycle is higher than the new period, set the new duty cycle first
            if current_duty_cycle > period_ns:
                with open(f'{channel_path}/duty_cycle', 'w') as f:
                    f.write(str(int(duty_cycle_ns)))

            # If the new duty cycle is higher than the current period, set the new period first
            if duty_cycle_ns > current_period:
                with open(f'{channel_path}/period', 'w') as f:
                    f.write(str(int(period_ns)))

            # Set the duty cycle if it wasn't set before
            if current_duty_cycle <= period_ns:
                with open(f'{channel_path}/duty_cycle', 'w') as f:
                    f.write(str(int(duty_cycle_ns)))

            # Set the period if it wasn't set before
            if duty_cycle_ns <= current_period:
                with open(f'{channel_path}/period', 'w') as f:
                    f.write(str(int(period_ns)))

            with open(f'{channel_path}/enable', 'w') as f:
                f.write('1')
        if not hasattr(self, 'pwm_channels'):
            self.pwm_channels = {}
        self.pwm_channels[gpio] = {'frequency': frequency, 'duty_cycle_percentage': duty_cycle_percentage}
        if frequency > 0:
            self.start_pwm_logging_thread(gpio, frequency, duty_cycle_percentage)
        else:
            self.stop_monitoring(gpio)

    def start_pwm_logging_thread(self, channel, frequency, duty_cycle_percentage):
        """
        Start a thread to simulate PWM signal and log its activity.
        """
        def pwm_thread(channel, frequency, duty_cycle_percentage):
            period_ns = 1e9 / frequency
            high_time_ns = period_ns * (duty_cycle_percentage / 100)
            low_time_ns = period_ns - high_time_ns
            while not self.stop_threads and self.pwm_channels[channel]['frequency'] > 0:
                self.log_event(channel, 1)
                time.sleep(high_time_ns / 1e9)
                if self.stop_threads or self.pwm_channels[channel]['frequency'] == 0:
                    break
                self.log_event(channel, 0)
                time.sleep(low_time_ns / 1e9)
        if channel in self.callback_threads:
            self.stop_monitoring(channel)
        pwm_logging_thread = threading.Thread(target=pwm_thread, args=(channel, frequency, duty_cycle_percentage), daemon=True)
        self.callback_threads[channel] = pwm_logging_thread
        pwm_logging_thread.start()

    def stop_monitoring(self, gpio):
        """
        Stop monitoring a GPIO or PWM channel and its associated thread.
        """
        if gpio in self.callback_threads:
            if gpio in self.pwm_channels:
                self.pwm_channels[gpio]['frequency'] = 0
            self.callback_threads[gpio].join()
            del self.callback_threads[gpio]