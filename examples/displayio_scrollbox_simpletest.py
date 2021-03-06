# # SPDX-FileCopyrightText: 2022 Kevin Matocha (kmatch)
# # SPDX-License-Identifier: MIT

# Example demonstrating the CircuitPython ScrollBox widget for vertical scrolling of text.

import math
import time
import board
import terminalio
import displayio_scrollbox

display = board.DISPLAY

text_string = (
    "CircuitPython is a programming language designed to simplify experimenting and "
)
text_string = text_string + "learning to code on low-cost microcontroller boards."
text_string = (
    text_string
    + "\n\nWith CircuitPython, there are no upfront desktop downloads needed."
)
text_string = (
    text_string
    + " Once you get your board set up, open any text editor, and start editing code. "
)
text_string = text_string + "It's that simple."

## Base example uses the builtin monospace font: terminalio.FONT
font = terminalio.FONT

# Initialize the scroll box
my_scroll_box = displayio_scrollbox.ScrollBox(
    display=display,
    x=20,
    y=20,
    width=150,
    height=100,
    text=text_string,
    starting_row=0,
    font=font,
    background_color=0x333333,
    animation_time=1.2,
    x_offset=5,
    y_offset=5,
)

# Set the x and y positions of the ScrollBox
my_scroll_box.x = (display.width - my_scroll_box.width) // 2
my_scroll_box.y = (display.height - my_scroll_box.height) // 2


# Set the number of scrolling rows and number of steps based on the ScrollBox dimensions
move_rows = my_scroll_box.height - 10
steps = math.floor(my_scroll_box.max_row / move_rows)
sleep_time = 0.8

# Add the ScrollBox to the display
display.show(my_scroll_box)

while True:

    for i in range(steps):
        # Scroll up by the "move_rows" number of pixels
        my_scroll_box.scroll(ypixels=+move_rows)
        time.sleep(sleep_time)

    time.sleep(2 * sleep_time)

    my_scroll_box.text = "This is a shorter line now"

    for i in range(steps):
        # Scroll down by the "move_rows" number of pixels
        my_scroll_box.scroll(ypixels=-move_rows)
        time.sleep(sleep_time)

    time.sleep(2 * sleep_time)
