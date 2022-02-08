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

.. todo:: Add links to any specific hardware product page(s), or category page(s).
  Use unordered list & hyperlink rST inline format: "* `Link Text <url>`_"

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

.. todo:: Uncomment or remove the Bus Device and/or the Register library dependencies
  based on the library's use of either.

# * Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
# * Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

# imports

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/circuitpython/CircuitPython_Org_DisplayIO_ScrollBox.git"

import time
import displayio
from fontio import BuiltinFont
import terminalio
import bitmaptools

from adafruit_displayio_layout.widgets.widget import Widget
from adafruit_displayio_layout.widgets.control import Control

from adafruit_display_text import bitmap_label, wrap_text_to_pixels

from adafruit_displayio_layout.widgets.easing import exponential_easeinout as easing
# ScrollBox is currently limited to "non-bouncy" easing functions

class ScrollBox(Widget, Control):

    def __init__(self,
                 display,
                 x=0,
                 y=0,
                 width=100, # pixel width
                 height=50, # pixel height
                 x_offset=0, # pixels offset to the right
                 y_offset=0, # pixels offset from the top
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
        super(Control, self).__init__()

        self._text = text

        self._display = display # used to handle animation
        self._x_offset = x_offset
        self._y_offset = y_offset

        self._current_row = starting_row # the top row that is currently displayed
        self.max_row = None # bottom row
        self._font = font
        self.animation_time=animation_time
        self.easing_function=easing_function
        self._width = width
        self._height = height

        if isinstance(self._font, BuiltinFont):
            self._line_spacing_pixels = round(self._font.bitmap.height * line_spacing)
        else:
            self._line_spacing_pixels = round((self._font.ascent + self._font.descent) * line_spacing)
        self._dirty_rows = [] # placeholder for rows that need to be redrawn

        # setup the main bitmap, palette and tilegrid and add to the self Widget Group
        self.bitmap  = displayio.Bitmap(width, height, 2) # two-color bitmap
        self.palette = displayio.Palette(2)
        self.palette[0] = background_color
        self.palette[1] = color
        if background_transparent:
            self.palette.make_transparent(0)
        self.tilegrid = displayio.TileGrid(self.bitmap, pixel_shader=self.palette)
        self.append(self.tilegrid)

        self._make_text_list(text=self._text, font=self._font, row_start=self._y_offset) # build the
        self.scroll_to_row(row=starting_row, animation_time=0) # update the scroll box

    def _make_text_list(self, text, font, row_start): # Build data structure for text and its key parameters

        self._reset_dirty_rows()
        bitmap_fill_region(self.bitmap) # clear the bitmap

        # Convert text to lines using wrapping function (self.text_width_max)
        self.text_list = [] # initialize the blank list
        row_count = row_start # The first y-pixel row
        for line in wrap_text_to_pixels(text, (self.bitmap.width - self._x_offset), font):
            self.text_list.append( TextData(text=line, font=font, row=row_count) )
            row_count = row_count + self._line_spacing_pixels # Increment for next row's top
        self.max_row = row_count # maximum limits of the scrolling (0 to _max_row)

    def _reset_dirty_rows(self):
        self._dirty_rows = [0, self._height] # Reset that all rows need to be redrawn

    def scroll_to_row(self, row=0, animation_time=None):
        self.scroll(ypixels=row-self._current_row, animation_time=animation_time)

    def scroll(self, ypixels=0, animation_time=None): # scroll this many pixels

        if animation_time == None:
            animation_time = self.animation_time

        start_row = self._current_row # find the starting row
        target_row = start_row + ypixels # target row after the animation

        if ypixels == 0:
            pass # do not adjust the dirty region
        else:
            if ypixels > 0:
                add_dirty_row_min = self._current_row + self.bitmap.height
                add_dirty_row_max = self._current_row + self.bitmap.height + ypixels
            elif ypixels < 0:
                add_dirty_row_min = self._current_row + ypixels
                add_dirty_row_max = self._current_row

            # Update the total dirty region

            if (self._dirty_rows[0] is None):
                self._dirty_rows[0] = add_dirty_row_min
            else:
                self._dirty_rows[0] = min(self._dirty_rows[0], add_dirty_row_min)

            if (self._dirty_rows[1] is None):
                self._dirty_rows[1] = add_dirty_row_max
            else:
                self._dirty_rows[1] = max(self._dirty_rows[1], add_dirty_row_max)

        start_time = time.monotonic() # store the start of the animation

        while True:
            elapsed_time = time.monotonic() - start_time
            if elapsed_time < animation_time: # animate
                position = elapsed_time/animation_time # fraction of total movement to perform (0.0 to 1.0)
                new_row = round( self.easing_function(position) * ypixels ) + start_row
                self._display.auto_refresh=False
                self._scroll_and_draw(new_row)
                self._display.auto_refresh=True

            else: # animation is complete
                break

        # draw the final animation position
        self._display.auto_refresh=False
        self._scroll_and_draw(start_row + ypixels)
        self._display.auto_refresh=True
        
        self._dirty_rows=[None, None] # Bitmap is updated, there are no more dirty rows.

    def _scroll_and_draw(self, new_row):

        # Constrain the row selection to the row limit range
        if new_row < 0:
            new_row=0
        if new_row > self.max_row:
            new_row = self.max_row

        scroll_rows = self._current_row - new_row

        if abs(scroll_rows) > self.bitmap.height: # if scrolling puts us outside the window, clear bitmap.
            bitmap_fill_region(self.bitmap, x1=self._x_offset, palette_index=0)
        else:
            if scroll_rows > 0:
                self.bitmap.blit(0, scroll_rows, self.bitmap)
                bitmap_fill_region(self.bitmap, y2=scroll_rows, palette_index=0)

            elif scroll_rows < 0:
                self.bitmap.blit(0, 0, self.bitmap, y1=-scroll_rows)
                bitmap_fill_region(self.bitmap, y1=self._height + scroll_rows, palette_index=0)

        self._current_row = new_row # update the current position

        if (self._dirty_rows[0] is None) or (self._dirty_rows[1] is None):
            pass # don't do anything, since no dirty rows are specified
        else:
            start_line=0

            # determine which rows need to be blitted,
            # all rows within the update_region range, blit them at the right place
            for i, t in enumerate (self.text_list):
                if t.bottom >= self._dirty_rows[0]: # Found starting line to be drawn
                    rows_to_draw = t.bottom - self._dirty_rows[0]

                    if isinstance(self._font, BuiltinFont):
                        descent = 0
                    else:
                        descent = self._font.descent
                    line_start_offset = descent - rows_to_draw # offset from the text_anchor
                    start_line=i
                    break # found the first line that should be drawn

            for j, t in enumerate (self.text_list[start_line:]): # iterate through the remaining text lines
                if t.top <= self._dirty_rows[1]:
                    line_bitmap = t.bitmap
                    if (line_bitmap is None): # this line was empty, so don't draw anything.
                        continue

                    anchor_offset = t.bitmap_anchor_offset
                        # pixel y-offset between the baseline anchor point and the top of this bitmap

                    # calculate which rows from this text line should be copied into the main bitmap
                    min_row_to_blit = max(self._dirty_rows[0],
                                          t.anchor + anchor_offset,
                                          self._current_row,
                                          )
                    max_row_to_blit = min(self._dirty_rows[1],
                                          t.anchor + line_bitmap.height + anchor_offset,
                                          self._current_row + self._height,
                                          )

                    # calculate the offsets into the target bitmap
                    bitmap_x_target = self._x_offset
                    bitmap_y_target = min_row_to_blit - self._current_row

                    # calculate the offsets into the source bitmap relative to the upper left corner
                    # of the source bitmap
                    bitmap_x_source  = 0
                    bitmap_y_source1 = (min_row_to_blit - t.anchor - anchor_offset)
                    bitmap_y_source2 = (max_row_to_blit - t.anchor - anchor_offset)
                    
                    if ( (0 <= bitmap_y_source1 <= t.bitmap.height) and
                         (0 <= bitmap_y_source2 <= t.bitmap.height) ):

                        self.bitmap.blit(bitmap_x_target, bitmap_y_target,
                                         line_bitmap,
                                         x1=bitmap_x_source,
                                         y1=bitmap_y_source1,
                                         y2=bitmap_y_source2,
                                         skip_index=None)

                else:
                    break # the top of the line is past the update region, so must be finished drawing

    @property
    def current_row(self):
        return self._current_row

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, new_text: str) -> None:
        self._text = new_text
        self._make_text_list(text=self._text, font=self._font, row_start=self._y_offset)
        self.scroll_to_row(row=0, animation_time=0) # update the scroll box

    @property
    def font(self):
        return self._font

    @font.setter
    def font(self, new_font) -> None:
        self._font = new_font
        self._make_text_list(text=self._text, font=self._font, row_start=self._y_offset)
        self.scroll_to_row(row=0, animation_time=0) # update the scroll box

    @property
    def color(self):
        return self.palette[1]

    @color.setter
    def color(self, new_color) -> None:
        self.palette[1] = new_color

    @property
    def background_color(self):
        return self.palette[0]

    @background_color.setter
    def background_color(self, new_color) -> None:
        self.palette[0] = new_color

    @property
    def background_transparent(self):
        return self.palette.is_transparent(0)

    @background_transparent.setter
    def background_transparent(self, new_transparent) -> None:
        if new_transparent:
            self.palette.make_transparent(0)
        else:
            self.palette.make_opaque(0)

    
# TextData data structure Class for holding the text line, bitmap and row offset
# The bitmaps are rendered and destroyed as-needed to reduce the amount of memory required.
class TextData():

    def __init__(self,
                *,
                text,
                font,
                row,
                ):

        self.text=text
        self.font=font

        self.top = row # y-position in the display for the top row, in pixels


        if isinstance(font, BuiltinFont):
            ascent = font.bitmap.height
            descent = 0
        else:
            ascent = font.ascent
            descent = font.descent
        self.anchor = row + ascent # y-position in the display for the bitmap anchor point
        self.bottom = row + ascent + descent

        self._bitmap = None
        self.bitmap_anchor_offset = None # the y-offset of the anchor, relative to the bitmap upper left corner

    @property
    def bitmap(self):
        if (self._bitmap is None):
            # generate the bitmap_label to capture the bitmap and bitmap_anchor_offset
            temp_label = bitmap_label.Label(
                                            text=self.text,
                                            font=self.font,
                                            base_alignment=True,
                                            background_tight=True,
                                            )
            try:
                self._bitmap = temp_label.bitmap
                self.bitmap_anchor_offset = temp_label.bounding_box[1] # the bitmap y-offset for the baseline anchor
            except:
                self._bitmap = None
                self.bitmap_anchor_offset = None

        return self._bitmap

    def clear_bitmap(self):
        self._bitmap = None
        self.bitmap_anchor_offset = None


# bitmap fill helper function with pixel constraints
def bitmap_fill_region(bitmap, x1=0, y1=0, x2=None, y2=None, palette_index=0):
    if (x2 is None):
        x2=bitmap.width
    if (y2 is None):
        y2=bitmap.height

    bitmaptools.fill_region(bitmap, x1=x1, y1=y1, x2=x2, y2=y2, value=palette_index)

