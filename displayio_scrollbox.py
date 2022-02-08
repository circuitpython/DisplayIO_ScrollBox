# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2022 Kevin Matocha (kmatch98) for CircuitPython Organization
#
# SPDX-License-Identifier: MIT
"""
`displayio_scrollbox`
================================================================================

A graphics box for scrolling text vertically.


* Author(s): Kevin Matocha (kmatch98)

Implementation Notes
--------------------

**Hardware:**

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/circuitpython/CircuitPython_Org_DisplayIO_ScrollBox.git"

import time
import displayio
from fontio import BuiltinFont
import terminalio
import bitmaptools
from adafruit_display_text import bitmap_label, wrap_text_to_pixels
from adafruit_displayio_layout.widgets.widget import Widget
from adafruit_displayio_layout.widgets.control import Control
from adafruit_displayio_layout.widgets.easing import exponential_easeinout as easing

# ScrollBox is currently limited to "non-bouncy" easing functions


class ScrollBox(Widget, Control):
    """
    ScrollBox - A rectangular display Widget that prints text and
    provides capability for vertical scrolling.

    :param int x: x-pixel location of the upper left corner
    :param int y: y-pixel location of the upper left corner
    :param int width: pixel width of the graphical text box (default: 100)
    :param int height: pixel height of the graphical text box (default: 50)
    :param int x_offset: x-pixel offset of the text within the text box (default: 0)
    :param int y_offset: y-pixel offset of the text within the text box (default: 0)
    :param str text: text to be displayed
    :param Font font: font to be used for the text (default: terminalio.FONT)
    :param int color: color of the text (default: 0xFFFFFF white)
    :param int background_colr: color of the rectangle background of the text box
     (default: 0x000000 black)
    :param bool background_transparent: set to True if the background should be transparent
     (default: False)
    :param float line_spacing: sets the line spacing for the text (default: 1.0)
    :param int starting_row: during initial rendering, this is the initial row that will
     be used (default: 0)
    :param float animation_time: number of seconds to be used during scrolling operations, this
     value is used if no value is provided when a scroll is requested
    :param easing_function: the easing function that controls the movement of the scrolling
     (default: exponential_easeinout)
    """

    # pylint: disable=too-many-arguments,too-many-locals,too-many-instance-attributes
    def __init__(
        self,
        display,
        x=0,
        y=0,
        width=100,  # pixel width
        height=50,  # pixel height
        x_offset=0,  # pixels offset to the right
        y_offset=0,  # pixels offset from the top
        text="",
        font=terminalio.FONT,
        color=0xFFFFFF,
        background_color=0x000000,
        background_transparent=False,
        line_spacing=1.0,
        starting_row=0,
        animation_time=0.2,
        easing_function=easing,
        **kwargs,
    ):

        super().__init__(x=x, y=y, width=width, height=height, **kwargs)

        # initialize the Control superclass

        # pylint: disable=bad-super-call
        super(Control, self).__init__()

        self._text = text

        self._display = display  # used to handle animation
        self._x_offset = x_offset
        self._y_offset = y_offset

        self._current_row = starting_row  # the top row that is currently displayed
        self.max_row = None  # bottom row
        self._font = font
        self.animation_time = animation_time
        self.easing_function = easing_function
        self._width = width
        self._height = height

        if isinstance(self._font, BuiltinFont):
            self._line_spacing_pixels = round(self._font.bitmap.height * line_spacing)
        else:
            self._line_spacing_pixels = round(
                (self._font.ascent + self._font.descent) * line_spacing
            )
        self._dirty_rows = []  # placeholder for rows that need to be redrawn

        # setup the main bitmap, palette and tilegrid and add to the self Widget Group
        self.bitmap = displayio.Bitmap(width, height, 2)  # two-color bitmap
        self.palette = displayio.Palette(2)
        self.palette[0] = background_color
        self.palette[1] = color
        if background_transparent:
            self.palette.make_transparent(0)
        self.tilegrid = displayio.TileGrid(self.bitmap, pixel_shader=self.palette)
        self.append(self.tilegrid)

        self._make_text_list(
            text=self._text, font=self._font, row_start=self._y_offset
        )  # build the
        self.scroll_to_row(row=starting_row, animation_time=0)  # update the scroll box

    def _make_text_list(
        self, text, font, row_start
    ):  # Build data structure for text and its key parameters

        self._reset_dirty_rows()
        bitmap_fill_region(self.bitmap)  # clear the bitmap

        # Convert text to lines using wrapping function (self.text_width_max)
        self.text_list = []  # initialize the blank list
        row_count = row_start  # The first y-pixel row
        for line in wrap_text_to_pixels(
            text, (self.bitmap.width - self._x_offset), font
        ):
            self.text_list.append(_TextData(text=line, font=font, row=row_count))
            row_count = (
                row_count + self._line_spacing_pixels
            )  # Increment for next row's top
        self.max_row = row_count  # maximum limits of the scrolling (0 to _max_row)

    def _reset_dirty_rows(self):
        self._dirty_rows = [0, self._height]  # Reset that all rows need to be redrawn

    def scroll_to_row(self, row=0, animation_time=None):
        """Scroll to a specific row, in pixels.
        :param int row: the row to scroll to, in pixels.
        :param animation_time: the time in seconds to perform the scrolling animation
        """
        self.scroll(ypixels=row - self._current_row, animation_time=animation_time)

    def scroll(self, ypixels=0, animation_time=None):  # scroll this many pixels
        """Scroll a number of ypixels, relative to the current position.""
        :param int ypixels: the number of pixels to scroll, positive scross the text upward
        :param animation_time: the time in seconds to perform the scrolling animation
        """

        if animation_time is None:
            animation_time = self.animation_time

        start_row = self._current_row  # find the starting row

        if ypixels == 0:
            pass  # do not adjust the dirty region
        else:
            if ypixels > 0:
                add_dirty_row_min = self._current_row + self.bitmap.height
                add_dirty_row_max = self._current_row + self.bitmap.height + ypixels
            elif ypixels < 0:
                add_dirty_row_min = self._current_row + ypixels
                add_dirty_row_max = self._current_row

            # Update the total dirty region

            if self._dirty_rows[0] is None:
                self._dirty_rows[0] = add_dirty_row_min
            else:
                self._dirty_rows[0] = min(self._dirty_rows[0], add_dirty_row_min)

            if self._dirty_rows[1] is None:
                self._dirty_rows[1] = add_dirty_row_max
            else:
                self._dirty_rows[1] = max(self._dirty_rows[1], add_dirty_row_max)

        start_time = time.monotonic()  # store the start of the animation

        while True:
            elapsed_time = time.monotonic() - start_time
            if elapsed_time < animation_time:  # animate
                position = (
                    elapsed_time / animation_time
                )  # fraction of total movement to perform (0.0 to 1.0)
                new_row = round(self.easing_function(position) * ypixels) + start_row
                self._display.auto_refresh = False
                self._scroll_and_draw(new_row)
                self._display.auto_refresh = True

            else:  # animation is complete
                break

        # draw the final animation position
        self._display.auto_refresh = False
        self._scroll_and_draw(start_row + ypixels)
        self._display.auto_refresh = True

        self._dirty_rows = [
            None,
            None,
        ]  # Bitmap is updated, there are no more dirty rows.

    def _scroll_and_draw(self, new_row):
        # pylint: disable=too-many-branches

        # Constrain the row selection to the row limit range
        if new_row < 0:
            new_row = 0
        if new_row > self.max_row:
            new_row = self.max_row

        scroll_rows = self._current_row - new_row

        if (
            abs(scroll_rows) > self.bitmap.height
        ):  # if scrolling puts us outside the window, clear bitmap.
            bitmap_fill_region(self.bitmap, xstart=self._x_offset, palette_index=0)
        else:
            if scroll_rows > 0:
                self.bitmap.blit(0, scroll_rows, self.bitmap)
                bitmap_fill_region(self.bitmap, yend=scroll_rows, palette_index=0)

            elif scroll_rows < 0:
                self.bitmap.blit(0, 0, self.bitmap, y1=-scroll_rows)
                bitmap_fill_region(
                    self.bitmap, ystart=self._height + scroll_rows, palette_index=0
                )

        self._current_row = new_row  # update the current position

        if (self._dirty_rows[0] is None) or (self._dirty_rows[1] is None):
            pass  # don't do anything, since no dirty rows are specified
        else:
            start_line = 0

            # determine which rows need to be blitted,
            # all rows within the update_region range, blit them at the right place
            for i, text_item in enumerate(self.text_list):
                if (
                    text_item.bottom >= self._dirty_rows[0]
                ):  # Found starting line to be drawn
                    start_line = i
                    break  # found the first line that should be drawn

            for text_item in self.text_list[
                start_line:
            ]:  # iterate through the remaining text lines
                if text_item.top <= self._dirty_rows[1]:
                    line_bitmap = text_item.bitmap
                    if (
                        line_bitmap is None
                    ):  # this line was empty, so don't draw anything.
                        continue

                    anchor_offset = text_item.bitmap_anchor_offset
                    # pixel y-offset between the baseline anchor point and the top of this bitmap

                    # calculate which rows from this text line should be copied into the main bitmap
                    min_row_to_blit = max(
                        self._dirty_rows[0],
                        text_item.anchor + anchor_offset,
                        self._current_row,
                    )
                    max_row_to_blit = min(
                        self._dirty_rows[1],
                        text_item.anchor + line_bitmap.height + anchor_offset,
                        self._current_row + self._height,
                    )

                    # calculate the offsets into the target bitmap
                    bitmap_x_target = self._x_offset
                    bitmap_y_target = min_row_to_blit - self._current_row

                    # calculate the offsets into the source bitmap relative to the upper left corner
                    # of the source bitmap
                    bitmap_x_source = 0
                    bitmap_y_source1 = (
                        min_row_to_blit - text_item.anchor - anchor_offset
                    )
                    bitmap_y_source2 = (
                        max_row_to_blit - text_item.anchor - anchor_offset
                    )

                    if (0 <= bitmap_y_source1 <= text_item.bitmap.height) and (
                        0 <= bitmap_y_source2 <= text_item.bitmap.height
                    ):

                        self.bitmap.blit(
                            bitmap_x_target,
                            bitmap_y_target,
                            line_bitmap,
                            x1=bitmap_x_source,
                            y1=bitmap_y_source1,
                            y2=bitmap_y_source2,
                            skip_index=None,
                        )

                else:
                    break  # the top of line is past update region, so must be finished drawing

    @property
    def current_row(self):
        """The current top row displayed on the ScrollBox, in pixels."""
        return self._current_row

    @property
    def text(self) -> str:
        """The text string displayed in the ScrollBox."""
        return self._text

    @text.setter
    def text(self, new_text: str) -> None:
        self._text = new_text
        self._make_text_list(text=self._text, font=self._font, row_start=self._y_offset)
        self.scroll_to_row(row=0, animation_time=0)  # update the scroll box

    @property
    def font(self):
        """The font used for typesetting the text in the ScrollBox."""
        return self._font

    @font.setter
    def font(self, new_font) -> None:
        self._font = new_font
        self._make_text_list(text=self._text, font=self._font, row_start=self._y_offset)
        self.scroll_to_row(row=0, animation_time=0)  # update the scroll box

    @property
    def color(self) -> int:
        """The ScrollBox text color."""
        return self.palette[1]

    @color.setter
    def color(self, new_color) -> None:
        self.palette[1] = new_color

    @property
    def background_color(self):
        """The ScrollBox background color."""
        return self.palette[0]

    @background_color.setter
    def background_color(self, new_color) -> None:
        self.palette[0] = new_color

    @property
    def background_transparent(self):
        """Boolean value defining whether the background is transparent."""
        return self.palette.is_transparent(0)

    @background_transparent.setter
    def background_transparent(self, new_transparent) -> None:
        if new_transparent:
            self.palette.make_transparent(0)
        else:
            self.palette.make_opaque(0)


# TextData data structure Class for holding the text line, bitmap and row offset
# The bitmaps are rendered and destroyed as-needed to reduce the amount of memory required.
class _TextData:
    def __init__(
        self,
        *,
        text,
        font,
        row,
    ):

        self.text = text
        self.font = font

        self.top = row  # y-position in the display for the top row, in pixels

        if isinstance(font, BuiltinFont):
            ascent = font.bitmap.height
            descent = 0
        else:
            ascent = font.ascent
            descent = font.descent
        self.anchor = (
            row + ascent
        )  # y-position in the display for the bitmap anchor point
        self.bottom = row + ascent + descent

        self._bitmap = None
        self.bitmap_anchor_offset = (
            None  # the y-offset of the anchor, relative to the bitmap upper left corner
        )

    @property
    def bitmap(self):
        """Bitmap for the text_line."""
        if self._bitmap is None:
            # generate the bitmap_label to capture the bitmap and bitmap_anchor_offset
            temp_label = bitmap_label.Label(
                text=self.text,
                font=self.font,
                base_alignment=True,
                background_tight=True,
            )

            self._bitmap = temp_label.bitmap
            self.bitmap_anchor_offset = temp_label.bounding_box[
                1
            ]  # the bitmap y-offset for the baseline anchor

        return self._bitmap

    def clear_bitmap(self):
        """Removes the bitmap data."""
        self._bitmap = None
        self.bitmap_anchor_offset = None


#
# pylint: disable=too-many-arguments
def bitmap_fill_region(
    bitmap, xstart=0, ystart=0, xend=None, yend=None, palette_index=0
):
    """Bitmap fill helper function with pixel constraints."""
    if xend is None:
        xend = bitmap.width
    if yend is None:
        yend = bitmap.height

    bitmaptools.fill_region(
        bitmap, x1=xstart, y1=ystart, x2=xend, y2=yend, value=palette_index
    )
