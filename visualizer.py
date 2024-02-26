import os
import errno
import ast
import sys
from collections import defaultdict
import time
from PySide6 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
from pyqtgraph import LabelItem, InfiniteLine, ViewBox
from PySide6.QtCore import Signal

class CustomViewBox(ViewBox):
    rangeChanged = Signal(float)  # Define a signal to emit the range delta

    def __init__(self, *args, **kwargs):
        super(CustomViewBox, self).__init__(*args, **kwargs)

    def wheelEvent(self, ev, axis=None):
        # Existing zoom functionality
        super(CustomViewBox, self).wheelEvent(ev, axis)

        # Fetch the new view range after zoom
        xRange = self.viewRange()[0]
        rangeDelta = xRange[1] - xRange[0]  # Calculate the delta of the x-range
        
        # Emit the range delta
        self.rangeChanged.emit(rangeDelta)

# Constants
NUM_GPIO_PINS = 26
GPIO_PIN_RANGE = range(2, 28)

# Create the named pipe if it does not exist
pipe_name = 'log_pipe'
if not os.path.exists(pipe_name):
    os.mkfifo(pipe_name)

# Initialize data storage for each GPIO pin
gpio_data = defaultdict(lambda: {'timestamps': [], 'states': [], 'last_state': None})

class GPIOPlotter(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(GPIOPlotter, self).__init__(parent)
        
        self.layout = QtWidgets.QVBoxLayout()
        #self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        # Initialize the plot view
        self.plotWidget = pg.GraphicsLayoutWidget()
        self.plots = []
        self.curves = []
        plot_height = 20
        for i in GPIO_PIN_RANGE:
            # Create a label for the GPIO pin and add it to the layout
            label = LabelItem(f"GPIO{i}", size='6pt')
            self.plotWidget.addItem(label)
            self.plotWidget.ci.layout.setSpacing(0)
            customViewBox = CustomViewBox()
            customViewBox.rangeChanged.connect(self.updateRange)  # Connect signal to slot
            plot = self.plotWidget.addPlot(viewBox=customViewBox)
            #plot = self.plotWidget.addPlot()
            plot.setMouseEnabled(x=True, y=False)
            plot.showGrid(x=True, y=True)
            plot.setFixedHeight(plot_height)
            plot.setContentsMargins(0, 0, 0, 0)
            curve = plot.plot([], [], pen='y' if i % 2 == 0 else 'r', stepMode=True)  # Set color based on index
            self.plots.append(plot)
            self.curves.append(curve)
            self.plotWidget.nextRow()
            
            # Set y-axis range and hide labels
            plot.setRange(yRange=[-.1, 1.1], disableAutoRange=True)
            if i != GPIO_PIN_RANGE:
                plot.getAxis('bottom').setStyle(showValues=False)
                
        # Set all plots to share the same x-axis
        for i in range(len(self.plots) - 1):
            self.plots[i].setXLink(self.plots[-1])
    
        self.layout.addWidget(self.plotWidget)

        # Timer for updating plots
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.updatePlots)
        self.timer.start(100)

        # Open the named pipe in non-blocking mode
        self.pipe_fd = os.open(pipe_name, os.O_RDONLY | os.O_NONBLOCK)
        self.pipe = os.fdopen(self.pipe_fd, 'r')

        # Create a horizontal layout for the distance label and pause button
        self.bottomLayout = QtWidgets.QHBoxLayout()
        self.bottomLayout.setContentsMargins(0, 0, 0, 0)

        # Initialize x-axis range label
        self.xRangeLabel = QtWidgets.QLabel()
        self.bottomLayout.addWidget(self.xRangeLabel)

        # Initialize distance label
        self.lastClickTime = None
        self.distanceLabel = QtWidgets.QLabel()
        self.bottomLayout.addWidget(self.distanceLabel)

        # Initialize pause button, set its clicked signal to togglePause method.
        self.isPaused = False
        self.pauseButton = QtWidgets.QPushButton("Pause")
        self.pauseButton.clicked.connect(self.togglePause)
        self.bottomLayout.addWidget(self.pauseButton)
        
        # Initialize zoom in button, set its clicked signal to zoomIn method.
        self.range = 10
        self.zoomInButton = QtWidgets.QPushButton("Zoom In")
        self.zoomInButton.clicked.connect(self.zoomIn)
        self.bottomLayout.addWidget(self.zoomInButton)
        self.zoomOutButton = QtWidgets.QPushButton("Zoom Out")
        self.zoomOutButton.clicked.connect(self.zoomOut)
        self.bottomLayout.addWidget(self.zoomOutButton)

        # Add the horizontal layout to the main vertical layout
        self.layout.addLayout(self.bottomLayout)

        # Connect the click event
        self.plotWidget.scene().sigMouseClicked.connect(self.onClick)
        self.verticalLines = []  # Add this line to store references to vertical lines
        self.clickCount = 0  # Add this line to track the number of clicks
        self.clickPositions = []  # List to store x-axis positions of the clicks in nanoseconds

    def updateRange(self, newRange):
        self.range = newRange / 1e9  # Update the range with the new value
        xRange = self.plots[-1].getViewBox().viewRange()[0]
        self.xRangeLabel.setText(f'X Range: {self.format_distance(xRange[1] - xRange[0])}')

    def togglePause(self):
        self.isPaused = not self.isPaused
        self.pauseButton.setText("Resume" if self.isPaused else "Pause")
    
    def zoomIn(self):
        self.range = self.range / 2
        current_range = self.plots[-1].getViewBox().viewRange()[0]
        new_min = current_range[0] + ((current_range[1] - current_range[0]) / 2)
        self.plots[len(self.plots)-1].setXRange(new_min, current_range[1], padding=0)
        self.xRangeLabel.setText(f'X Range: {self.format_distance(current_range[1] - new_min)}')

    def zoomOut(self):
        self.range = self.range * 1.5
        current_range = self.plots[-1].getViewBox().viewRange()[0]
        new_min = current_range[0] - ((current_range[1] - current_range[0]) / 2)
        self.plots[len(self.plots)-1].setXRange(new_min, current_range[1], padding=0)
        self.xRangeLabel.setText(f'X Range: {self.format_distance(current_range[1] - new_min)}')

    def trimData(self):
        """Trim the data for each GPIO pin to keep only the last 2000 events."""
        max_events = 10000  # Maximum number of events to retain
        for gpio in GPIO_PIN_RANGE:
            data = gpio_data[gpio]
            if len(data['timestamps']) > max_events:
                # Calculate the number of items to remove
                num_to_remove = len(data['timestamps']) - max_events
                # Remove the oldest items
                data['timestamps'] = data['timestamps'][num_to_remove:]
                data['states'] = data['states'][num_to_remove:]

    def updatePlots(self):
        if self.isPaused:
            return  # Skip updating plots if paused

        # Get the current time in nanoseconds
        current_time_ns = time.time_ns()
        # Define the start of the trailing window (10 seconds ago)
        window_start_ns = current_time_ns - self.range * 1e9  # 10 seconds in nanoseconds
        xRange = self.plots[-1].getViewBox().viewRange()[0]
        self.xRangeLabel.setText(f'X Range: {self.format_distance(xRange[1] - xRange[0])}')

        # Call trim_data here to ensure each GPIO pin's data is trimmed before updating plots
        self.trimData()

        try:
            raw_data = self.pipe.readlines()
            if raw_data:
                events = []
                most_recent_event_time = None
                for line in raw_data:
                    try:
                        event = ast.literal_eval(line)
                        if event[0] in GPIO_PIN_RANGE:
                            events.append(event)
                            # Update most_recent_event_time with the latest timestamp
                            if most_recent_event_time is None or event[2] > most_recent_event_time:
                                most_recent_event_time = event[2]
                        else:
                            print(f"Invalid GPIO pin number: {event[0]}")
                    except (SyntaxError, ValueError) as e:
                        print(f"Error parsing data: {e}")

                for gpio, state, timestamp in events:
                    # Initialize gpio_data for new GPIO
                    if gpio not in gpio_data:
                        gpio_data[gpio] = {'timestamps': [], 'states': [], 'last_state': None}

                    # Check if this is the first event for the GPIO
                    if not gpio_data[gpio]['timestamps']:
                        # Assume opposite state prior to the first event
                        opposite_state = 0 if state == 1 else 1
                        # Backfill an event with the opposite state at the start of the window
                        gpio_data[gpio]['timestamps'].append(window_start_ns)
                        gpio_data[gpio]['states'].append(opposite_state)

                    gpio_data[gpio]['timestamps'].append(timestamp)
                    gpio_data[gpio]['states'].append(state)
                    gpio_data[gpio]['last_state'] = state

                # If we have events, update all GPIOs to the most recent event's timestamp
                if most_recent_event_time:
                    for gpio in GPIO_PIN_RANGE:
                        if gpio not in gpio_data:
                            continue  # Skip GPIOs that have not been initialized
                        # Only update if the last timestamp is older than the most recent event's timestamp
                        if gpio_data[gpio]['timestamps'] and gpio_data[gpio]['timestamps'][-1] < most_recent_event_time:
                            last_state = gpio_data[gpio]['last_state']
                            gpio_data[gpio]['timestamps'].append(most_recent_event_time)
                            gpio_data[gpio]['states'].append(last_state)
                
                for gpio, curve in zip(GPIO_PIN_RANGE, self.curves):
                    if gpio not in gpio_data:
                        continue  # Skip curves for GPIOs that have not been initialized
                    data = gpio_data[gpio]
                    if data['timestamps']:
                        # Logic for extending timestamps and updating curves remains unchanged

                        if len(data['timestamps']) > 1:
                            timestamps_extended = data['timestamps'] + [data['timestamps'][-1] + (data['timestamps'][-1] - data['timestamps'][-2])]
                        else:
                            timestamps_extended = data['timestamps'] + [data['timestamps'][-1]] if data['timestamps'] else data['timestamps']
                        
                        curve.setData(timestamps_extended, data['states'])
                    self.plots[gpio-2].setXRange(window_start_ns, current_time_ns, padding=0)

        except IOError as e:
            if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                raise

    def onClick(self, event):
        self.clickCount += 1  # Increment click count on each click

        if self.clickCount <= 2:
            # Convert the click position to the corresponding x-axis value on the plot
            # Choose one plot to map the scene position to view position, since all share the same x-axis
            viewPos = self.plots[0].vb.mapSceneToView(event.scenePos())
            x = viewPos.x()
            self.clickPositions.append(x)  # Store the x-axis position once

            # Now create the vertical line on each plot using the captured x position
            for plot in self.plots:
                vLine = InfiniteLine(pos=x, angle=90, movable=False, pen='r')
                plot.addItem(vLine)
                self.verticalLines.append(vLine)  # Keep track of the line

            # On the second click, calculate and display the distance
            if self.clickCount == 2:
                distance_ns = abs(self.clickPositions[1] - self.clickPositions[0])
                formattedDistance = self.format_distance(distance_ns)
                self.distanceLabel.setText(f"Distance: {formattedDistance}")
        else:
            # Clear all lines on the third click
            for line in self.verticalLines:
                for plot in self.plots:
                    plot.removeItem(line)
            self.verticalLines.clear()  # Clear the list of line references
            self.clickCount = 0  # Reset click count for future clicks
            self.clickPositions.clear()  # Clear stored click positions
            self.distanceLabel.setText("")  # Clear distance label

    @staticmethod
    def format_distance(distance_ns):
        """Converts distance in nanoseconds to a formatted time string in the largest unit."""
        distance_s = distance_ns / 1e9
        if distance_s >= 1:
            return f"{distance_s:.1f} s"
        elif distance_ns >= 1e6:
            return f"{distance_ns / 1e6:.0f} ms"
        elif distance_ns >= 1e3:
            return f"{distance_ns / 1e3:.0f} μs"
        else:
            return f"{distance_ns:.0f} ns"

    def closeEvent(self, event):
        self.pipe.close()
        os.close(self.pipe_fd)
        super(GPIOPlotter, self).closeEvent(event)

def main():
    app = QtWidgets.QApplication(sys.argv)
    mainWin = GPIOPlotter()
    mainWin.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()