#DearPyGui-Grid
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
    - [Basic Usage](#basic-usage)
    - [Padding & Offsets](#padding--offsets)


DearPyGui-Grid is a layout management tool for [Dear PyGui](https://github.com/hoffstadt/DearPyGui). `Grid` does *not* create or use items for layout aids. Instead, it emulates a table-like structure and works by leveraging common configuration options supported by most items.







<br>

##Features
* create simple to complex layouts *without* the messy web of group, table, theme, and spacer items
* position widgets in individual cells or over a cell range
* supports overlapping widgets
* edge-level padding customization per-slot (row/column) or per widget
* spacing between rows and columns
* slot-level static and dynamic sizing (policy emulation)
* optional overlay outlining the grid and its' slots - useful for debugging or designing layouts
* minimal dependencies

<br>

##Installation

Using Python 3.10 (or newer), DearPyGui-Grid can be installed via `pip`:

```python
python -m pip install dearpygui-grid
```

<br>

##Usage

####Basic Usage

A layout object is created by instantiating the `Grid` class. The first two arguments set the initial number of columns and rows in the layout. The third argument, `target`, is the id of the grid's "reference" item. This item is used to help the grid determine its' content position and size when drawn, and is non-optional in most cases. `Grid` also accepts several keyword-only arguments. These, along with `cols`, `rows`, and `target`, can be updated later via the `.configure` method.

Next, we'll add some button items to the new window and attach them to the 3x3 grid in a cross pattern. This is done using the `.push` method; passing it the id of the item to attach in addition to the cell coordinates - indices of the column and row respectively - that the item will occupy. Column and row indices are zero-indexed.


Lastly, we need to tell Dear PyGui when to draw the grid. This can be done by registering the grid instance itself as a callback. An on-resize or when-visible handler is usually sufficient. While running the script below, you should see a rather seamless cross of buttons. You'll also see the grid at work when attempting to resize the window.


```python
import dearpygui.dearpygui as dpg
import dearpygui_grid as dpg_grid


dpg.create_context()
dpg.setup_dearpygui()
dpg.create_viewport()
dpg.show_viewport()

window = dpg.add_window(width=400, height=400, no_scrollbar=True, no_title_bar=True)

grid = dpg_grid.Grid(3, 3, window)

grid.push(dpg.add_button(parent=window), 1, 0)  # middle col, top row
grid.push(dpg.add_button(parent=window), 0, 1)  # left col, middle row
grid.push(dpg.add_button(parent=window), 1, 1)  # middle col, middle row
grid.push(dpg.add_button(parent=window), 2, 1)  # right col, middle row
grid.push(dpg.add_button(parent=window), 1, 2)  # middle col, bottom row

with dpg.item_handler_registry() as window_hr:
    dpg.add_item_visible_handler(callback=grid)
dpg.bind_item_handler_registry(window, window_hr)

dpg.start_dearpygui()

```
<div>
    <p align="center">
        <img src=""/>
        <img src=""/>
    </p>
    <p style="font-size:12px;text-align:center;font-style:italic;"></p>
    <br>
</div>

####Padding & Offsets

In the example above, the target window item is configured using the `no_scrollbar` and `no_title_bar` settings. If you try running the script without them, you'll see that the grid does not take into account the size of the window's title bar, meaning that it will slightly overlap any content in the top row. Additionally, the content in the window consumes enough space for the scrollbar to display which, again, clips our content. But, what if you want the grid to behave *with* the scrollbar and title bar? Fortunately, this can also be managed by applying offsets, padding, and spacing to the layout.

| Attribute  | Value Type     | Components | Description |
| :--------: | :------------: | :--------: | :---------: |
| `.offsets` | `array[float]` | 4          | Space between the left, upper, right, and lower inner walls of the grid and its' content region.          |
| `.padding` | `array[float]` | 4          | Space between the left, upper, right, and lower inner walls of the grid's slots and their content region. |
| `.spacing` | `array[float]` | 2          | Space between the outer walls of the grid's slots from other slots.         |

Applying an 8-pixel offset will be more than sufficient to shrink the content region enough so the scrollbar isn't visible. To allow the grid's content to be shown below the title bar and not under it, a 26-pixel offset is applied to the grid's upper border. A value of 26 is used because the height of the title bar using Dear PyGui's internal default theme is 18 pixels - the 8 additional pixels are added to make the layout uniform by matching the offsets applied to the other borders.

```python
import dearpygui.dearpygui as dpg
import dearpygui_grid as dpg_grid


dpg.create_context()
dpg.setup_dearpygui()
dpg.create_viewport()
dpg.show_viewport()

window = dpg.add_window(width=400, height=400)

grid = dpg_grid.Grid(3, 3, window)
# Can optionally be applied per component, as `grid.offsets[i] = ...`
grid.offsets = 8, 18 + 8, 8, 8

grid.push(dpg.add_button(parent=window), 1, 0)  # middle col, top row
grid.push(dpg.add_button(parent=window), 0, 1)  # left col, middle row
grid.push(dpg.add_button(parent=window), 1, 1)  # middle col, middle row
grid.push(dpg.add_button(parent=window), 2, 1)  # right col, middle row
grid.push(dpg.add_button(parent=window), 1, 2)  # middle col, bottom row

with dpg.item_handler_registry() as window_hr:
    dpg.add_item_visible_handler(callback=grid)
dpg.bind_item_handler_registry(window, window_hr)

dpg.start_dearpygui()

```
<div>
    <p align="center">
        <img src=""/>
        <img src=""/>
    </p>
    <p style="font-size:12px;text-align:center;font-style:italic;"></p>
    <br>
</div>

While `.offsets` "pads" the grid's content, `.padding` affects the content of its' slots - columns and rows - similarly. Specifically, it affects the content of its' *cells* since, unlike the grid, each slot only has two boundries; left and right for columns, top and bottom for rows. When drawn, the grid calculates the size, position, and offsets (padding) of each cell using the settings of the parenting column and row.

Using the same example once more, left-edge and right-edge column padding (the first and third component of `.padding` respectively) is set to 10. To make it easier to see how the adjustment affects the layout, row upper-edge and lower-edge padding is not changed.

```python
import dearpygui.dearpygui as dpg
import dearpygui_grid as dpg_grid


dpg.create_context()
dpg.setup_dearpygui()
dpg.create_viewport()
dpg.show_viewport()

window = dpg.add_window(width=400, height=400)

grid = dpg_grid.Grid(3, 3, window)
grid.offsets = 8, 18 + 8, 8, 8
grid.padding[0] = 10  # column left-edge
grid.padding[2] = 10  # column right-edge

grid.push(dpg.add_button(parent=window), 1, 0)  # middle col, top row
grid.push(dpg.add_button(parent=window), 0, 1)  # left col, middle row
grid.push(dpg.add_button(parent=window), 1, 1)  # middle col, middle row
grid.push(dpg.add_button(parent=window), 2, 1)  # right col, middle row
grid.push(dpg.add_button(parent=window), 1, 2)  # middle col, bottom row

with dpg.item_handler_registry() as window_hr:
    dpg.add_item_visible_handler(callback=grid)
dpg.bind_item_handler_registry(window, window_hr)

dpg.start_dearpygui()

```
<div>
    <p align="center">
        <img src=""/>
        <img src=""/>
    </p>
    <p style="font-size:12px;text-align:center;font-style:italic;"></p>
    <br>
</div>

>***Note**: The amount of space between slots can be also adjusted. The value found on the `.spacing` attribute is a 2-length array containing the spacing values for columns and rows respectively. It is effectively a different form of padding; a combination of a grid offset and slot padding value. Customization for slot spacing is limited compared in comparison (for now), so it is only briefly mentioned.*

<br>

####Realistic Usage

Not all layouts are as simple as aligning a few buttons symmetrically. A typical modern interface layout consists of a menu bar and/or ribbon, a side panel, main view, and maybe a footer bar. `Grid` is a versitile tool capable of this and more, but requires more of a dive into its' capabilities and a bit of creativity.

```python
```