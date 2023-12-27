import sys
import numbers
import functools
import threading
import dataclasses
from array import array
import dearpygui.dearpygui as dearpygui
from dearpygui._dearpygui import (
    get_item_configuration as _item_get_config,
    get_item_state as _item_get_state,
    configure_item as _item_set_config,
)
from typing import (
    Any,

    Protocol,
    Callable,
    Literal,
    Sequence,
    Generic,
    Iterator,
    SupportsIndex,
    Sized,
    Iterable,
    TypeVar,

    overload,
    cast,
)
from typing_extensions import Self




# [ GENERAL TYPING ]

_T = TypeVar('_T')
_N = TypeVar('_N', bound=numbers.Real)


Item  = int | str

NaN = float('nan')




# [ CONFIG GETTERS/SETTERS ]

class _RectGetter(Protocol):
    """A function that returns an item's size and position; as
    `(width, height, x_pos, y_pos, is_visible)`.
    """
    def __call__(self, item: Item) -> tuple[int, int, int, int, bool]: ...


def _get_item_rect(item: Item) -> tuple[int, int, int, int, bool]:
    d  = _item_get_state(item)
    if 'visible' in d:
        return *d['rect_size'], *d['pos'], d['visible']  # type: ignore
    return *d['rect_size'], *d['pos'], _item_get_config(item)['show']  # type: ignore



class _RectSetter(Protocol):
    """A function that updates an item's size and position via
    `dearpygui.configure_item`.
    """
    def __call__(self, item: Item, x_pos: int, y_pos: int, width: int, height: int, show: bool) -> Any: ...


def _set_item_rect(item: Item, x_pos: int, y_pos: int, width: int, height: int, show: bool):
    _item_set_config(
        item,
        width=int(width),
        height=int(height),
        pos=(int(x_pos), int(y_pos)),
        show=show,
    )





# [ ITEM POSITION CALCULATORS ]

class _Positioner(Protocol):
    """Calculates the final position of an item in the occupying cell
    or cellspan.
    """
    def __call__(self, item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float, /) -> tuple[float, float]: ...


_ANCHOR_MAP: dict[str, _Positioner] = {}

def _get_positioner(key: str):
    try:
        return _ANCHOR_MAP[key.casefold()]
    except AttributeError:
        return _ANCHOR_MAP[key]  # raise `KeyError`

def _anchor_position(*anchors: str) -> Callable[[_Positioner], _Positioner]:
    def register_anchor_fn(fn: _Positioner) -> _Positioner:
        for s in anchors:
            _ANCHOR_MAP[s.lower()] = fn  # type: ignore
        return fn
    return register_anchor_fn


@_anchor_position("n", "north")
def _anchor_position_N(item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float) -> tuple[float, float]:
    return (cell_wt - item_wt) / 2 + cell_x, cell_y  # center x

@_anchor_position("ne", "northeast")
def _anchor_position_NE(item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float) -> tuple[float, float]:
    return (cell_wt - item_wt) + cell_x, cell_y

@_anchor_position("e", "east")
def _anchor_position_E(item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float) -> tuple[float, float]:
    return (cell_wt - item_wt) + cell_x, (cell_ht - item_ht) / 2 + cell_y  # center y

@_anchor_position("se", "southeast")
def _anchor_position_SE(item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float) -> tuple[float, float]:
    return (cell_wt - item_wt) + cell_x, (cell_ht - item_ht) + cell_y

@_anchor_position("s", "south")
def _anchor_position_S(item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float) -> tuple[float, float]:
    return (cell_wt - item_wt) / 2 + cell_x, (cell_ht - item_ht) + cell_y  # center x

@_anchor_position("sw", "southwest")
def _anchor_position_SW(item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float) -> tuple[float, float]:
    return cell_x, (cell_ht - item_ht) + cell_y

@_anchor_position("w", "west")
def _anchor_position_W(item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float) -> tuple[float, float]:
    return cell_x, (cell_ht - item_ht) / 2 + cell_y  # center y

@_anchor_position("nw", "northwest")
def _anchor_position_NW(item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float) -> tuple[float, float]:
    return cell_x, cell_y

@_anchor_position("c", "center", "centered")
def _anchor_position_C(item_wt: float, item_ht: float, cell_x: float, cell_y: float, cell_wt: float, cell_ht: float) -> tuple[float, float]:
    return (cell_wt - item_wt) / 2 + cell_x, (cell_ht - item_ht) / 2 + cell_y  # center x & y




# [ HELPER FUNCTIONS ]

def _create_context():
    # runs once, then no-op
    dearpygui.create_context()
    @functools.wraps(_create_context)
    def create_context(): ...
    setattr(sys.modules[__name__], _create_context.__name__, create_context)


def _is_nan(v: Any):
    return v != v


def _is_null_v(value: Any, default: float = NaN):
    return value is None or _is_nan(value)


def _to_float_array(value: Sequence[float | None] | float | None, length: int, default: float = NaN):
    arr = array('f', [default] * length)
    if value is None or _is_nan(value):  # nan
        return arr

    for i in range(length):
        v = value[i]  # type: ignore
        if _is_null_v(v):
            arr[i] = default  # type: ignore
        else:
            arr[i] = v  # type: ignore
    return arr





# [ GRID COMPONENTS ]

class _Configure(Generic[_T]):
    __slots__ = ("_key",)

    def __init__(self, key: str = '', /):
        self._key = key

    def __set_name__(self, cls: type, name: str):
        self._key = self._key or name

    @overload
    def __get__(self, inst: Any, cls: type | None = ...) -> _T: ...
    @overload
    def __get__(self, inst: None, cls: type | None = None) -> Self: ...
    def __get__(self, inst: Any, cls: Any = None):
        if inst is None:
            return self
        return inst.configuration()[self._key]

    def __set__(self, inst: Any, value: Any):
        inst.configure(**{self._key: value})







@dataclasses.dataclass(init=False)
class Slot:
    """Stores dedicated size settings of a row or column."""
    __slots__ = ( '_label', '_size', '_weight', '_padding')

    label  : _Configure[str]         = dataclasses.field(default=_Configure('label'))
    weight : _Configure[float]       = dataclasses.field(default=_Configure('weight'))
    size   : _Configure[int]         = dataclasses.field(default=_Configure('size'))
    padding: _Configure[list[float]] = dataclasses.field(default=_Configure('padding'))

    def __init__(self, label: str = '', *, weight: float = 1.0, size: int = 0, padding: Sequence[float] = (NaN, NaN)):
        """Args:
            * label: An informal name for the object.

            * weight: Affects dynamic slot scaling proportional to the size of the
            grid and the total weight value of the axis.

            * size: The width or height of the slot. A positive non-zero value
            enforces a "fixed" sizing policy for the slot. Otherwise, the slot
            uses a "sized" policy based on its' *weight*.

            * padding: A 2-item sequence containing the amount of space between the
            slot's walls and its' content region. When the slot is a column,
            this is the first (x1_pad i.e. left-padding) and third (x2_pad i.e.
            right-padding) value used for cell padding. When the slot is a row,
            these values are the second (y1_pad i.e. upper-padding) and fourth
            (y2_pad i.e. lower-padding) values, respectively.
        """
        self.configure(label=label, size=size, weight=weight, padding=padding)

    @overload
    def configure(self, *, label: str = ..., weight: float = ..., size: int = ..., padding: Sequence[float] = ...): ...  # type: ignore
    def configure(self, **kwargs):
        """Update the slot's various settings."""
        if 'label' in kwargs:
            self._label = kwargs['label']
        if 'weight' in kwargs:
            self._weight = max(0.0, kwargs['weight'] or 0.0) if not _is_null_v(kwargs['size']) else 0.0
        if 'size' in kwargs:
            self._size = max(0, int(kwargs['size'] or 0)) if not _is_null_v(kwargs['size']) else 0
        if 'padding' in kwargs:
            self._padding = _to_float_array(kwargs['padding'], 2)

    def configuration(self) -> dict[str, Any]:
        """Return the slot's settings and values."""
        return {f:getattr(self, f'_{f}') for f in self.__dataclass_fields__}

    @property
    def policy(self) -> Literal['FIXED', 'SIZED']:
        return 'FIXED' if self._size else 'SIZED'


@dataclasses.dataclass(init=False)
class Axis(Iterable[Slot], Sized):
    """Container for a `Grid` object's rows or columns.

    Instances are treated as immutable, unsigned pseudo-integrals
    for most operations; the value of which is a representation
    of the number of slots (rows or columns) in the axis. However,
    in-place operations directly affect the number of slots they
    contain.

    Slots are identified by their positions (index) in the axis.
    Indexing the axis returns the `Slot` object for that row or
    column.

    Slots are always appended to, or are removed from, the end of
    the axis whenever the number of slots is updated.

    Operations that update the number of slots in the axis are
    thread-safe.
    """
    __slots__ = ('_slots', '_lock', '_label', '_spacing', '_padding')

    label  : _Configure[str]         = dataclasses.field(default=_Configure('label'))
    length : _Configure[int]         = dataclasses.field(default=_Configure('length'))
    spacing: _Configure[float]       = dataclasses.field(default=_Configure('spacing'))
    padding: _Configure[list[float]] = dataclasses.field(default=_Configure('padding'))

    def __init__(self, length: int = 0, *, label: str = '', spacing: float = NaN, padding: tuple[float, float] | Sequence[float] = (NaN, NaN)) -> None:
        """Args:
            * length: The initial number of slots.

            * label: An informal name for the object.

            * spacing: The amount of empty space between slots in the axis.

            * padding: A 2-item sequence containing the amount of space between a
            slot's walls and its' content region. When the axis contains columns
            (x-axis), this is the first (x1_pad i.e. left-padding) and third (x2_pad
            i.e. right-padding) value used for cell padding. If the axis contains
            rows (y-axis), these values are the second (y1_pad i.e. upper-padding)
            and fourth (y2_pad i.e. lower-padding) values, respectively.

        A slot's padding component values are always used over the axis' padding
        values, falling back to the axis' padding component value when the slot's
        padding component value is missing.
        """
        self._slots = cast(list[Slot], [])
        self._lock  = threading.Lock()
        self.configure(label=label, length=length, spacing=spacing, padding=padding)

    @overload
    def configure(self, *, label: str = ..., length: int = ..., spacing: float = ..., padding: tuple[float, float] | Sequence[float] = ...): ...  # type: ignore
    def configure(self, **kwargs):
        """Update the axis' various settings."""
        if 'label' in kwargs:
            self._label = kwargs['label']
        if 'length' in kwargs:
            self.resize(kwargs['length'])
        if 'padding' in kwargs:
            self._padding = _to_float_array(kwargs['padding'], 2, NaN)
        if 'spacing' in kwargs:
            spacing = kwargs['spacing'] or 0.0
            self._spacing = max(0.0, spacing) if not _is_null_v(spacing) else NaN

    def configuration(self) -> dict[Literal['label', 'length', 'spacing', 'padding'], Any]:
        """Return the axis' settings and values."""
        return {f:getattr(self, f'_{f}') for f in self.__dataclass_fields__}  # type: ignore

    def __str__(self):
        return str(self._slots)

    def __bool__(self):
        return bool(self._slots)

    def __len__(self) -> int:
        # TODO: check for concurrency issues
        return len(self._slots)

    __int__ = __index__ = __len__

    def __float__(self):
        return float(len(self))

    def __complex__(self):
        return complex(len(self))

    def __lt__(self, other: Any) -> bool:
        return len(self) < other

    def __le__(self, other: Any) -> bool:
        return len(self) <= other

    def __eq__(self, other: Any) -> bool:  # XXX: `__hash__ == None`
        return len(self) == other

    def __ne__(self, other: Any) -> bool:
        return len(self) != other

    def __gt__(self, other: Any) -> bool:
        return len(self) > other

    def __ge__(self, other: Any) -> bool:
        return len(self) >= other

    @property
    def weight(self) -> float:
        """[get] Return the axis' total weight value."""
        with self._lock:
            return sum(s._weight for s in self._slots if not s._size)

    @property
    def min_size(self) -> int:
        """[get] Return the axis' minimum size when drawn."""
        with self._lock:
            return sum(s._size for s in self._slots)


    # Number Behaviors (no bitwise)

    def __pos__(self):
        return +len(self)

    def __neg__(self):
        return -len(self)

    def __add__(self, x: _N) -> _N:
        return len(self) + x

    def __sub__(self, x: _N) -> _N:
        return len(self) - x

    def __mul__(self, x: _N) -> _N:
        return len(self) * x

    def __truediv__(self, x: _N) -> _N:
        return len(self) * x

    def __floordiv__(self, x: _N) -> _N | float:
        return len(self) // x

    def __mod__(self, x: _N) -> _N:
        return len(self) % x

    def __divmod__(self, x: Any) -> tuple[float, float]:
        length = len(self)
        return (length // x, length % x)

    def __pow__(self, x: int, mod: int | None = None) -> int:
        return pow(len(self), x, mod)

    def __round__(self, ndigits: int = 0):
        return round(len(self), ndigits)

    __trunc__ = __floor__ = __ceil__ = __abs__ = __int__


    # Sequence Behaviors/Methods

    def __getitem__(self, index: SupportsIndex) -> Slot:
        return self._slots[index]

    def __iter__(self) -> Iterator[Slot]:
        yield from self._slots

    def __iadd__(self, x: int) -> Self:
        """
        >>> x = Axis(4)
        >>> x += 8
        >>> len(x)
        12
        >>> x += 0
        >>> len(x)
        12
        >>> x += -10  # __isub__
        >>> len(x)
        2
        """
        if not x:
            return self
        if x > 0:
            with self._lock:
                self._slots.extend(Slot(self._label) for _ in range(x))
                return self
        return self.__isub__(abs(x))

    def __isub__(self, x: int) -> Self:
        """
        >>> x = Axis(12)
        >>> x -= 8
        >>> len(x)
        4
        >>> x -= 0
        >>> len(x)
        4
        >>> x -= -10  # __iadd__
        >>> len(x)
        12
        """
        if not x:
            return self
        if x > 0:
            with self._lock:
                del self._slots[-x:]
                return self
        return self.__iadd__(abs(x))

    def resize(self, length: int):
        """Add/remove slots from the axis so that it contains the number
        of slots specified.

        Awaits internal lock release.

        Args:
            * length: A positive number indicating the target length of
            the axis.


        Slots are always added to, and removed from, the end of the axis.


        >>> x = Axis(8)
        >>> x.resize(2)  # trim
        >>> len(x)
        2
        >>> x.resize(12)  # extend
        >>> len(x)
        12
        """
        if length < 0:
            raise ValueError(f'`length` cannot be less than zero (got {length!r}).')
        return self.__iadd__(length-len(self))

    def __imul__(self, x: int):  # NOTE: ROUNDS DOWN
        """
        >>> x = Axis(4)
        >>> x *= 4
        >>> len(x)
        16
        >>> x *= 0.73  # trunc 11.68
        >>> len(x)
        11
        """
        if x < 0:
            raise ValueError(f'cannot multiply slots by a negative number (got {x!r}).')
        return self.resize(int(len(self) * x))

    def __itruediv__(self, x: float):  # NOTE: ROUNDS DOWN (floor division)
        """
        >>> x = Axis(16)
        >>> x /= 2
        >>> len(x)
        8
        >>> x /= 3  # floor div
        2
        """
        if x < 0:
            raise ValueError(f"cannot divide slots by a negative number (got {x!r}).")
        return self.resize(len(self) // x)  # type: ignore

    __ifloordiv__ = __itruediv__

    def insert(self, index: SupportsIndex):
        """Adds a new row/column at the specified index.

        Awaits internal lock release.

        Args:
            * index: Position of the new slot.
        """
        with self._lock:
            self._slots.insert(index, Slot(self._label))

    def remove(self, index: SupportsIndex = -1):
        """Delete the row/column at the specified index, or the last
        row/column if not specified.

        Awaits internal lock release.

        Args:
            * index: Target slot index.
        """
        with self._lock:
            self._slots.pop(index)




@dataclasses.dataclass(slots=True, frozen=True)
class ItemData:
    """Contains the size and placement information of an item attached
    to a `Grid` object.

    Args:
        * item: Item integer uuid or string alias.

        * cellspan: a 4-tuple containing starting and ending cell coordinates
        that the item will occupy, as `(col_start, row_start, col_end, row_end)`.

        * max_size: A 2-item float array with the item's maximum width and
        height. When it is desired to not specify a maximum size component, set
        the value to zero.

        * padding: A 4-item sequence of padding override values for the item, as
        `[left-padding, upper-padding, right-padding, bottom-padding]`. When it
        is desired to not override a padding component, set the padding value to
        infinity (`float(inf)`).

        * positioner: A helper function that calculates an item's final position.

        * rect_setter: The function that will be called to update the item's size,
        position, and visibility status.
    """
    item       : Item
    cellspan   : tuple[int, int, int, int]
    max_size   : Sequence[float]           = dataclasses.field(default_factory=lambda: array('f', (0.0, 0.0)))
    padding    : Sequence[float]           = dataclasses.field(default_factory=lambda: array('f', (NaN, NaN, NaN, NaN)))
    positioner : _Positioner               = _get_positioner('centered')
    rect_setter: _RectSetter               = _set_item_rect

    def __hash__(self):
        return hash(self.item)


@dataclasses.dataclass(slots=True)
class CellData:
    """Contains individual grid cell properties calculated in a single
    frame.
    """
    col   : int
    row   : int
    x_pos : float = 0.0
    y_pos : float = 0.0
    width : float = 0.0
    height: float = 0.0
    x1_pad: float = 0.0
    y1_pad: float = 0.0
    x2_pad: float = 0.0
    y2_pad: float = 0.0

    @property
    def cell(self):
        """[get] Return the cell's column and row coordinates."""
        return self.col, self.row

    def __hash__(self):
        return hash((self.col, self.row))


@dataclasses.dataclass(init=False)
class Grid:
    """A layout manager for Dear PyGui."""
    __slots__ = (
        # internal
        '_lock',
        '_item_data',
        '_drawlayer',
        # configuration
        'rows',
        'cols',
        '_label',
        '_width',
        '_height',
        '_offsets',
        '_padding',
        '_spacing',
        '_target',
        '_rect_getter',
        '_overlay',
        '_show',
        # other
        '__weakref__',
    )

    label      : _Configure[str]         = dataclasses.field(default=_Configure("label"))
    width      : _Configure[int]         = dataclasses.field(default=_Configure("width"))
    height     : _Configure[int]         = dataclasses.field(default=_Configure("height"))
    offsets    : _Configure[list[float]] = dataclasses.field(default=_Configure("offsets"))
    padding    : _Configure[list[float]] = dataclasses.field(default=_Configure("padding"))
    spacing    : _Configure[list[float]] = dataclasses.field(default=_Configure("spacing"))
    target     : _Configure[Item]        = dataclasses.field(default=_Configure("target"))
    rect_getter: _Configure[_RectGetter] = dataclasses.field(default=_Configure("rect_getter"))
    overlay    : _Configure[bool]        = dataclasses.field(default=_Configure("overlay"))
    show       : _Configure[bool]        = dataclasses.field(default=_Configure("show"))

    def __init_subclass__(cls):
        super().__init_subclass__()
        if cls.__code__ is not cls.__call__.__code__:
            cls.__code__ = cls.__call__.__code__

    def __init__(  # type: ignore
        self,
        cols       : int             = 1,
        rows       : int             = 1,
        target     : Item            = 0,
        *,
        label      : str             = '',
        width      : int             = 0,
        height     : int             = 0,
        offsets    : Sequence[float] = (0, 0, 0, 0),
        padding    : Sequence[float] = (0, 0, 0, 0),
        spacing    : Sequence[float] = (0, 0),
        rect_getter: _RectGetter     = _get_item_rect,
        overlay    : bool            = False,
        show       : bool            = True,
    ):
        """Args:
            * cols: Number of initial columns.

            * rows: Number of initial rows.

            * target: The unique identifier of an existing item. The grid
            will scale with this item, unless *width*/*height* is set.

            * label: An informal name for the grid.

            * rect_getter: A callable that accepts *target* as a positional
            argument and returns a 5-tuple containing a related width, height,
            x-position, y-position, and visibility status.

            * width: Overrides *target* width when drawing the grid.

            * height: Overrides *target* height when drawing the grid.

            * offsets: A 4-length sequence indicating the amount of empty
            space between the each of the grid's walls and the content region.

            * padding: A 4-item sequence containing the amount of space between a
            slot's inner walls and their content regions. The first and third values
            are for column left and right padding respectively, while the second
            and fourth values are the upper and lower padding values for rows.

            * spacing: A 2-length sequence indicating the amount of empty space
            between slots.

            * overlay: Show/hide the visual representation of the grid and its'
            rows and columns. Useful when planning/designing layouts.

            * show: Show/hide grid and its' managed items.

        If *rect_getter* is unspecified, `dearpygui.get_item_state` is called
        to fetch the size, position, and visibility state of *target*. This
        means that `rect_size` and `pos` must be included in the dictionary
        returned from `dearpygui.get_item_state(target)`. For some items,
        `dearpygui.get_item_configuration` may also be called if the 'visible'
        key is missing from the item's state mapping.

        *target* is non-optional, unless *rect_getter* is specified.

        When drawn, the grid is sized to *width*/*height*, or to the
        width/height of *target* when *width*/*height* is unspecified.

        The size(s) and position(s) of the grid and its managed items are
        only updated when *target* is visible and when *show* is True.
        Additionally, the grid's overlay is drawn only when the grid would
        be drawn and when *overlay* is True.

        *offsets* is expected to be a sequence 4 items in length, as
        `[left_offset, upper_offset, right_offset, bottom_offset]`.

        When *show* is True/False, the visibility state (`show`) of all items
        managed by the grid will also be set to True/False.

        False-like configuration option values are evaluated as the option's
        default value. Additionally, options that expect numeric values
        are evaluated as zero when the value is False-like or when it compares
        less than zero. When a configuration option's value is set to the
        default/minimum value, that option is considered "not set" or
        "unspecified".

        >NOTE: Be mindful of calls made to the grid within your custom
        *rect_getter*. Under normal operation, attempting to update or
        draw the grid will result in a deadlock!
        """
        assert self.__code__ == self.__call__.__code__
        _create_context()
        self.cols = Axis(0, label='x')
        self.rows = Axis(0, label='y')

        if not dearpygui.does_item_exist(self.__drawlist):
            type(self).__drawlist = dearpygui.add_viewport_drawlist()
        self._drawlayer = dearpygui.add_draw_layer(parent=self.__drawlist)
        self._item_data = cast(set[ItemData], set())
        self._lock      = threading.Lock() if not sys.gettrace() else threading.RLock()

        self.configure(
            rows=rows,
            cols=cols,
            label=label,
            width=width,
            height=height,
            offsets=offsets,
            padding=padding,
            spacing=spacing,
            target=target,
            rect_getter=rect_getter,
            overlay=overlay,
            show=show,
        )

    @overload
    def configure(self, *, cols: int = ..., rows: int = ..., label: str = ..., width: int = ..., height: int = ..., offsets: Sequence[float] = ..., padding: Sequence[float] = ..., spacing: Sequence[float] = ..., target: Item = ..., rect_getter: _RectGetter = ..., overlay: bool = ..., show: bool = ...): ...  # type: ignore
    def configure(self, **kwargs):
        """Update the grid's settings.

        Awaits internal lock release.
        """
        with self._lock:
            # slots
            if 'cols' in kwargs:
                cols = kwargs['cols']
                if not isinstance(cols, int):
                    raise TypeError(f'expected int for `cols` (got {type(cols)!r}).')
                self.cols.resize(kwargs['cols'])
            if 'rows' in kwargs:
                rows = kwargs['rows']
                if not isinstance(rows, int):
                    raise TypeError(f'expected int for `rows` (got {type(rows)!r}).')
                self.rows.resize(kwargs['rows'])

            if 'label' in kwargs:
                self._label = kwargs['label'] or ''

            if 'target' in kwargs or 'rect_getter' in kwargs:
                target      = kwargs.get('target', getattr(self, '_target', 0)) or 0
                rect_getter = kwargs.get('rect_getter', getattr(self, '_rect_getter', _get_item_rect)) or _get_item_rect
                if not target and rect_getter is _get_item_rect:
                    raise ValueError(f'`target` required when using the default rect-getter.')
                try:
                    _, _, _, _, _ = rect_getter(target)
                except ValueError:
                    raise TypeError(f'expected `rect_getter` to return a 5-tuple, got {type(rect_getter)!r}.')
                except TypeError:
                    if not callable(rect_getter):
                        raise TypeError(f'expected callable for `rect_getter`, got {type(rect_getter)!r}.') from None
                    raise
                self._target      = target
                self._rect_getter = rect_getter

            # sizing
            if 'width' in kwargs:
                width = int(max(0, kwargs.get('width' , getattr(self, '_width' , 0)) or 0))
                self._width = width
            if 'height' in kwargs:
                height = int(max(0, kwargs.get('height' , getattr(self, '_height' , 0)) or 0))
                self._height = height

            # offsets
            if 'offsets' in kwargs:
                self._offsets = _to_float_array(kwargs['offsets'], 4, 0.0)
            if 'padding' in kwargs:
                self._padding = _to_float_array(kwargs['padding'], 4, 0.0)
            if 'spacing' in kwargs:
                self._spacing = _to_float_array(kwargs['spacing'], 2, 0.0)

            # visibility
            if 'overlay' in kwargs:
                overlay = bool(kwargs['overlay'])
                _item_set_config(self._drawlayer, show=overlay)
                self._overlay = overlay
            if 'show' in kwargs:
                show = bool(kwargs['show'])
                _rm_items = []
                if not show:
                    _item_set_config(self._drawlayer, show=False)
                    for item_data in self._item_data:
                        try:
                            _item_set_config(item_data.item, show=False)
                        except SystemError:
                            if not dearpygui.does_item_exist(item_data.item):
                                _rm_items.append(item_data)
                            else:
                                raise
                else:
                    for item_data in self._item_data:
                        try:
                            _item_set_config(item_data.item, show=True)
                        except SystemError:
                            if not dearpygui.does_item_exist(item_data.item):
                                _rm_items.append(item_data)
                            else:
                                raise
                self._item_data.difference_update(_rm_items)
                self._show = show

    def configuration(self):
        """Return the grid's various settings and values."""
        cfg = {'cols': len(self.cols), 'rows': len(self.rows)}
        cfg.update({f:getattr(self, f'_{f}') for f in self.__dataclass_fields__})
        return cfg

    ANCHORS = tuple(s.lower() for s in _ANCHOR_MAP)

    @overload
    def push(self, item: Item, col: int, row: int, /, *, anchor: str = ..., rect_setter: _RectSetter = ..., max_size: tuple[int | None, int | None] | Sequence[int | None] = ..., padding: tuple[int | None, int | None, int | None, int | None] | Sequence[int | None] = ...): ...
    @overload
    def push(self, item: Item, col: int, row: int, /, *, anchor: str = ..., rect_setter: _RectSetter = ..., max_width: int = ..., max_height: int = ..., padding: tuple[int | None, int | None, int | None, int | None] | Sequence[int | None] = ...): ...
    @overload
    def push(self, item: Item, col: int, row: int, /, *, anchor: str = ..., rect_setter: _RectSetter = ..., max_size: tuple[int | None, int | None] | Sequence[int | None] = ..., x1_pad: int = ..., y1_pad: int = ..., x2_pad: int = ..., y2_pad: int = ...): ...
    @overload
    def push(self, item: Item, col: int, row: int, /, *, anchor: str = ..., rect_setter: _RectSetter = ..., max_width: int = ..., max_height: int = ..., x1_pad: int = ..., y1_pad: int = ..., x2_pad: int = ..., y2_pad: int = ...): ...
    @overload
    def push(self, item: Item, cell_start: tuple[int, int] | Sequence[int], cell_stop: tuple[int, int] | Sequence[int] | None = ..., /, *, anchor: str = ..., rect_setter: _RectSetter = ..., max_size: tuple[int | None, int | None] | Sequence[int | None] = ..., padding: tuple[int | None, int | None, int | None, int | None] | Sequence[int | None] = ...): ...
    @overload
    def push(self, item: Item, cell_start: tuple[int, int] | Sequence[int], cell_stop: tuple[int, int] | Sequence[int] | None = ..., /, *, anchor: str = ..., rect_setter: _RectSetter = ..., max_width: int = ..., max_height: int = ..., padding: tuple[int | None, int | None, int | None, int | None] | Sequence[int | None] = ...): ...
    @overload
    def push(self, item: Item, cell_start: tuple[int, int] | Sequence[int], cell_stop: tuple[int, int] | Sequence[int] | None = ..., /, *, anchor: str = ..., rect_setter: _RectSetter = ..., max_size: tuple[int | None, int | None] | Sequence[int | None] = ..., x1_pad: int = ..., y1_pad: int = ..., x2_pad: int = ..., y2_pad: int = ...): ...
    @overload
    def push(self, item: Item, cell_start: tuple[int, int] | Sequence[int], cell_stop: tuple[int, int] | Sequence[int] | None = ..., /, *, anchor: str = ..., rect_setter: _RectSetter = ..., max_width: int = ..., max_height: int = ..., x1_pad: int = ..., y1_pad: int = ..., x2_pad: int = ..., y2_pad: int = ...): ...
    def push(self, item: Item, cell_start: Any, cell_stop: Any = None, /, *, anchor: str = 'c', rect_setter: _RectSetter = _set_item_rect, max_size: Any = None, max_width: Any = None, max_height: Any = None, padding: Any = None, x1_pad: Any = None, y1_pad: Any = None, x2_pad: Any = None, y2_pad: Any = None):
        """Attach an item to the grid.

        Awaits internal lock release.

        Args:
            * item: Integer uuid or string alias of an item.

            * col, cell_start: Index of the cell's column that will contain the item,
            OR a 2-item sequence containing both the column and row indices of the
            initial cell of the cell range the item will occupy.

            * row, cell_stop: Index of the cell's row that will contain the item,
            OR a 2-item sequence containing both the column and row indices of the
            last cell of the cell range the item will occupy.

            * anchor: A (inter)cardinal direction name ("north", "southwest", etc) or
            abbreviation ("n", "sw", etc) indicating the area of the cell the item will
            "stick" to. "c(enter)" will result in the item being centered in the
            specified cell or cellspan. Value is case-insensitive. Defaults to "c".

            * rect_setter: A callable accepting *item*, x-position, y-position,
            width, height, and visible state as positional arguments that updates the
            item's size, position, and visibility.

            * max_size: The maximum width and height the item will scale to. If
            unspecified, the item's maximum size is without bounds. When specified,
            *max_width/height* values are ignored.

            * max_width: Individual width component of *max_size*. Cannot be
            combined with *max_size*.

            * max_height: Individual height component of *max_size*. Cannot be
            combined with *max_size*.

            * padding: Overrides slot-level padding values, as `[x1_pad, y1_pad,
            x1_pad, y1_pad]`, or `[left-padding, upper-padding, right-padding,
            bottom-padding]`. When *padding* is specified, *x[i]/y[i]_pad* values
            are ignored.

            * x1_pad: Left-padding component of *padding*. Cannot be combined with
            *padding*.

            * y1_pad: Upper-padding component of *padding*. Cannot be combined with
            *padding*.

            * x2_pad: Right-padding component of *padding*. Cannot be combined with
            *padding*.

            * y2_pad: Bottom-padding component of *padding*. Cannot be combined with
            *padding*.


        When it is desired for the item to occupy a single cell, *col* is the cell's
        column index and *row* is the cell's row index (ex. `grid.push(item, col_idx,
        row_idx)`). Alternatively, a 2-item sequence can be passed as the *col* argument
        containing both indicies (ex. `grid.push(item, (col_idx, row_idx)`) while *row*
        is left unspecified or None. To push an item onto a range of cells, *col*
        and *row* must both be 2-item sequences containing the coordinates of the
        first and last cell in the range, respectively.

        Column and row indices can be negative.

        When the grid is (re)drawn, `dearpygui.configure_item` is indirectly
        called to set the item's size, position, and visibility. In order for an
        item to to be correctly sized, positioned, and shown, it must support sizing
        via `width` and `height` configurations, explicit positioning via `pos`,
        and visibility updates via `show`. If an item does not support one of more
        of the mentioned configuration options, consider parenting them in another
        item that does. Alternatively, a 5-argument callable can be used as the
        *rect_setter* argument; it will be called instead to update the item's
        configuration. This allows users to force compatibility for otherwise
        incompatible items (ex. `mvText` items), process other events before/after
        the resize, or forward the resize event to a different item entirely.

        An item's size is usually dependant on the size of the row(s) and column(s)
        they occupy. *max_size* (OR individual *max_width/height*) values can be set
        to clamp the item's size as the cell or cellspan expands. However, setting a
        minimum size per item is not supported. This is because having one cell/item
        in a row or column of different size than others in that slot is atypical of
        a grid-layout. When desired, it is recommended to set the `size` attribute of
        the entire row or column; this will prevent the slot from sizing dynamically
        when the grid is redrawn. If an item must have a unique minimum size, a custom
        *rect_setter* can be set that sends other width/height values to
        `dearpygui.configure_item`.

        When *padding* is specified, all non-None and non-infinity values are used to
        override the slot-level padding values. For example, if the column padding
        (left-padding, right-padding) and row padding (upper-padding, bottom-padding)
        values are both `[20, 20]` and *padding* is `[10, None, None, None]` (OR
        `x1_pad=10`), the padding values used when drawing the item will be `[10, 20,
        20, 20]`, as `[left-padding, upper-padding, right-padding, bottom-padding]`.

        >NOTE: Be mindful of calls made to the grid within your custom *rect_setter*.
        Under normal operation, attempting to update or draw the grid will result
        in a deadlock!
        """
        if hasattr(cell_start, '__iter__'):  # possible cell range
            try:
                x1, y1 = cell_start
            except ValueError:
                raise ValueError(
                    f'expected a 2-item sequence of cell coordinates for `cell_start`, got {len(cell_start)!r}.'
                ) from None

            try:
                x2, y2 = cell_stop
            except TypeError:
                if cell_stop is None:  # single cell
                    x2 = x1
                    y2 = y1
                else:
                    raise ValueError(
                        f'expected a 2-item sequence of cell coordinates for `cell_stop`, got {cell_stop!r}.'
                    ) from None
        else:  # single cell
            x1 = x2 = cell_start

            try:
                y1 = y2 = int(cell_stop)
            except TypeError:
                if cell_stop is not None:
                    raise TypeError(
                        f'expected int for `row`, got {type(cell_stop)!r}.'
                    ) from None
                raise TypeError(
                    f"expected 3 positional arguments for '{self.push.__qualname__}()' got 2."
                ) from None
        cellspan = int(x1), int(y1), int(x2), int(y2),

        if _is_null_v(max_size):
            max_size = _to_float_array((max_width, max_height), 2, 0.0)
        else:
            max_size = _to_float_array(max_size, 2, 0.0)
        for i in range(len(max_size)):
            max_size[i] = max(0.0, max_size[i])

        if _is_null_v(padding):
            padding = _to_float_array((x1_pad, y1_pad, x2_pad, y2_pad), 4, NaN)
        else:
            padding = _to_float_array(padding, 4, NaN)

        with self._lock:
            # Two instances of `ItemData` can potentially exist for the same item
            # since refs can be integers or strings. Both are removed just in case.
            if isinstance(item, int):
                int_id = item
                str_id = dearpygui.get_item_alias(item)
            if isinstance(item, str):
                int_id = dearpygui.get_alias_id(item)
                str_id = item
            # XXX: `ItemData.__hash__` forwards to `ItemData.item.__hash__`
            self._item_data.discard(int_id)  # type: ignore
            self._item_data.discard(str_id)  # type: ignore

            item_data = ItemData(
                item=item,
                cellspan=cellspan,
                max_size=max_size,
                padding=padding,
                positioner=_get_positioner(anchor),
                rect_setter=rect_setter,
            )
            self._item_data.add(item_data)
            return item_data

    def pop(self, item: Item):
        """Release an item from the grid.

        Awaits internal lock release.
        """
        with self._lock:
            try:
                self._item_data.remove(item)  # type: ignore
            except KeyError:
                if isinstance(item, str):
                    self._item_data.discard(dearpygui.get_alias_id(item))  # type: ignore
            try:
                _item_set_config(item, pos=())
            except SystemError:
                pass

    def clear(self):
        """Release all items from the grid.

        Awaits internal lock release.
        """
        with self._lock:
            for item_data in self._item_data:
                try:
                    _item_set_config(item_data.item, pos=())
                except SystemError:
                    pass
            self._item_data.clear()

    __drawlist = '[mvViewportDrawlist] Grid'

    def __call__(self, *args):
        """Redraw the grid; updating the size, position, and visibility state
        of any item attached.

        Awaits internal lock release.


        Any item attached to the grid whose cell or cellspan is outside of the
        grid's range will be hidden.
        """
        with self._lock:
            parent_width, parent_height, parent_x_pos, parent_y_pos, parent_visible = self._rect_getter(self._target)
            if not self._show or not parent_visible:
                _item_set_config(self._drawlayer, show=False)
                return

            area_width  = self._width or parent_width
            area_height = self._height or parent_height

            cell_map = self._draw_grid_cells(area_width, area_height)
            self._draw_grid_items(cell_map)

            if self._overlay:
                dearpygui.delete_item(self._drawlayer, children_only=True)
                _item_set_config(self._drawlayer, show=True)

                area_x_max = parent_x_pos + area_width
                area_y_max = parent_y_pos + area_height
                self._draw_overlay_outline(
                    parent_x_pos,
                    parent_y_pos,
                    area_x_max,
                    area_y_max,
                    (150, 255, 255),
                    (150, 255, 255, 80),
                )
                self._draw_overlay_slots(
                    cell_map.values(),
                    parent_x_pos,
                    parent_y_pos,
                    area_x_max,
                    area_y_max,
                    (150, 255, 255, 120),
                    (150, 255, 255, 255),
                    (150, 255, 255, 80),
                )

    __code__ = __call__.__code__

    def _draw_grid_cells(self, area_width: float, area_height: float) -> dict[tuple[int, int], CellData]:
        grid_x1_pad, grid_y1_pad, grid_x2_pad, grid_y2_pad = self._offsets

        grid_width  = area_width  - grid_x1_pad - grid_x2_pad
        grid_height = area_height - grid_y1_pad - grid_y2_pad

        weight_wt = max(0, (grid_width  - self.cols.min_size)) / max(1, self.cols.weight)  # |- `ZeroDivisionError`
        weight_ht = max(0, (grid_height - self.rows.min_size)) / max(1, self.rows.weight)  # |

        default_x1_pad, default_x2_pad = self.cols._padding
        if default_x1_pad != default_x1_pad:  # is NaN
            default_x1_pad = self._padding[0]
        if default_x2_pad != default_x2_pad:  # is NaN
            default_x2_pad = self._padding[2]
        default_y1_pad, default_y2_pad = self.rows._padding
        if default_y1_pad != default_y1_pad:  # is NaN
            default_y1_pad = self._padding[1]
        if default_y2_pad != default_y2_pad:  # is NaN
            default_y2_pad = self._padding[3]

        cell_wt_offs = self.cols._spacing
        if cell_wt_offs != cell_wt_offs:  # is NaN
            cell_wt_offs = self._spacing[0]
        cell_ht_offs = self.rows._spacing
        if cell_ht_offs != cell_ht_offs:  # is NaN
            cell_ht_offs = self._spacing[1]

        cell_x_pos_offs = cell_wt_offs / 2.0
        cell_y_pos_offs = cell_ht_offs / 2.0

        cols = tuple(enumerate(self.cols._slots))

        alloc_ht = 0.0
        cell_map = {}
        for row_idx, row in enumerate(self.rows._slots):
            _cell_ht   = row.size or weight_ht * row.weight  # FIXED or SIZED
            cell_ht    = _cell_ht - cell_ht_offs
            cell_y_pos = grid_y1_pad + alloc_ht + cell_y_pos_offs
            alloc_ht  += _cell_ht

            cell_y1_pad, cell_y2_pad = row.padding

            if cell_y1_pad != cell_y1_pad:  # is NaN
                cell_y1_pad = default_y1_pad
            if cell_y2_pad != cell_y2_pad:  # is NaN
                cell_y2_pad = default_y2_pad

            alloc_wt = 0.0
            for col_idx, col in cols:
                _cell_wt   = col.size or weight_wt * col.weight  # FIXED or SIZED
                cell_wt    = _cell_wt - cell_wt_offs
                cell_x_pos = grid_x1_pad + alloc_wt + cell_x_pos_offs
                alloc_wt  += _cell_wt

                cell_x1_pad, cell_x2_pad = col.padding
                if cell_x1_pad != cell_x1_pad:  # is NaN
                    cell_x1_pad = default_x1_pad
                if cell_x2_pad != cell_x2_pad:  # is NaN
                    cell_x2_pad = default_x2_pad

                cell_map[(col_idx, row_idx)] = CellData(
                    col_idx,
                    row_idx,
                    cell_x_pos,
                    cell_y_pos,
                    cell_wt,
                    cell_ht,
                    cell_x1_pad,
                    cell_y1_pad,
                    cell_x2_pad,
                    cell_y2_pad,
                )
        return cell_map

    def _draw_grid_items(self, cell_map: dict[tuple[int, int], CellData]):
        n_rows   = len(self.rows)
        n_cols   = len(self.cols)
        rm_items = ()
        for item_data in self._item_data:
            c1, r1, c2, r2 = item_data.cellspan
            # convert negative indexes
            r1 %= n_rows
            c1 %= n_cols
            r2 %= n_rows
            c2 %= n_cols
            # correct inversed cellspan
            if r1 > r2:
                r1, r2 = r2, r1
            if c1 > c2:
                c1, c2 = c2, c1

            try:
                cell1 = cell_map[c1, r1]
                cell2 = cell_map[c2, r2]
            except KeyError:  # hide item
                item_x_pos  = 0
                item_y_pos  = 0
                item_width  = 0
                item_height = 0
                item_show   = False
            else:
                x1_pad, y1_pad, x2_pad, y2_pad = item_data.padding
                # if is NaN
                if x1_pad != x1_pad:
                    x1_pad = cell1.x1_pad
                if y1_pad != y1_pad:
                    y1_pad = cell1.y1_pad
                if x2_pad != x2_pad:
                    x2_pad = cell2.x2_pad
                if y2_pad != y2_pad:
                    y2_pad = cell2.y2_pad

                cell_x_pos = cell1.x_pos + x1_pad
                cell_y_pos = cell1.y_pos + y1_pad

                item_width, item_height = item_data.max_size
                cell_width = cell2.x_pos + cell2.width - cell_x_pos - x2_pad
                if not item_width or item_width > cell_width:
                    item_width = cell_width
                cell_height = cell2.y_pos + cell2.height - cell_y_pos - y2_pad
                if not item_height or item_height > cell_height:
                    item_height = cell_height

                if item_width < 1 or item_height < 1:  # hide item
                    item_x_pos = 0
                    item_y_pos = 0
                    item_show  = False
                else:
                    item_x_pos, item_y_pos = item_data.positioner(
                        item_width,
                        item_height,
                        cell_x_pos,
                        cell_y_pos,
                        cell_width,
                        cell_height,
                    )
                    item_show = True

            try:
                item_data.rect_setter(
                    item_data.item,
                    int(item_x_pos),
                    int(item_y_pos),
                    int(item_width),
                    int(item_height),
                    item_show,
                )
            except SystemError:
                if not dearpygui.does_item_exist(item_data.item):
                    if not rm_items:
                        rm_items = []
                    rm_items.append(item_data)
                else:
                    raise
        self._item_data.difference_update(rm_items)

    def _draw_overlay_outline(self, x_min: int, y_min: int, x_max: int, y_max: int, line_color: Sequence[int], pad_color: Sequence[int]):
        layer = self._drawlayer
        x1_pad, y1_pad, x2_pad, y2_pad = self._offsets

        # padding
        if x1_pad:
            dearpygui.draw_rectangle(
                (x_min, y_max),
                (x_min + x1_pad, y_min + y1_pad),
                color=(0, 0, 0, 0),
                fill=pad_color,  # type: ignore
                parent=layer,
            )
        if y1_pad:
            dearpygui.draw_rectangle(
                (x_min, y_min),
                (x_max - x2_pad, y_min + y1_pad),
                color=(0, 0, 0, 0),
                fill=pad_color,  # type: ignore
                parent=layer,
            )
        if x2_pad:
            dearpygui.draw_rectangle(
                (x_max, y_min),
                (x_max - x2_pad, y_max - y2_pad),
                color=(0, 0, 0, 0),
                fill=pad_color,  # type: ignore
                parent=layer,
            )
        if y2_pad:
            dearpygui.draw_rectangle(
                (x_max, y_max),
                (x_min + x1_pad, y_max - y2_pad),
                color=(0, 0, 0, 0),
                fill=pad_color,  # type: ignore
                parent=layer,
            )

        # spacing

        # outline
        dearpygui.draw_rectangle(
            (x_min, y_min), (x_max, y_max),
            fill=(0, 0, 0, 0),
            color=line_color,  # type: ignore
            parent=layer,
        )

    def _draw_overlay_slots(self, cells: Iterable[CellData], x_min: int, y_min: int, x_max: int, y_max: int, line_color: Sequence[int], space_color: Sequence[int], pad_color: Sequence[int], ):
        layer = self._drawlayer
        x1_pad, y1_pad, x2_pad, y2_pad = self._offsets
        x_space = self.cols._spacing / 2
        y_space = self.rows._spacing / 2
        cont_x_min = x_min + x1_pad
        cont_y_min = y_min + y1_pad
        cont_x_max = x_max - x2_pad
        cont_y_max = y_max - y2_pad


        rows = set(range(len(self.rows)))
        cols = set(range(len(self.cols)))

        for cell in cells:
            cell_x_min  = x_min + cell.x_pos
            cell_y_min  = y_min + cell.y_pos
            cell_x_max  = cell_x_min + cell.width
            cell_y_max  = cell_y_min + cell.height
            cell_x1_pad = cell.x1_pad
            cell_y1_pad = cell.y1_pad
            cell_x2_pad = cell.x2_pad
            cell_y2_pad = cell.y2_pad
            # inner cell padding
            if cell_x1_pad:
                dearpygui.draw_rectangle(
                    (cell_x_min              , cell_y_max              ),
                    (cell_x_min + cell_x1_pad, cell_y_min + cell_y1_pad),
                    color=(0, 0, 0, 0),
                    fill=pad_color,  # type: ignore
                    parent=layer,
                )
            if cell_y1_pad:
                dearpygui.draw_rectangle(
                    (cell_x_min              , cell_y_min              ),
                    (cell_x_max - cell_x2_pad, cell_y_min + cell_y1_pad),
                    color=(0, 0, 0, 0),
                    fill=pad_color,  # type: ignore
                    parent=layer,
                )
            if cell_x2_pad:
                dearpygui.draw_rectangle(
                    (cell_x_max              , cell_y_min              ),
                    (cell_x_max - cell_x2_pad, cell_y_max - cell_y2_pad),
                    color=(0, 0, 0, 0),
                    fill=pad_color,  # type: ignore
                    parent=layer,
                )
            if cell_y2_pad:
                dearpygui.draw_rectangle(
                    (cell_x_max              , cell_y_max              ),
                    (cell_x_min + cell_x1_pad, cell_y_max - cell_y2_pad),
                    color=(0, 0, 0, 0),
                    fill=pad_color,  # type: ignore
                    parent=layer,
                )

            # column
            if cell.col in cols:
                # outer spacing
                dearpygui.draw_rectangle(
                    (cell_x_min          , cont_y_min),
                    (cell_x_min - x_space, cont_y_max),
                    color=(0, 0, 0, 0),
                    fill=space_color,  # type: ignore
                    parent=layer,
                )
                dearpygui.draw_rectangle(
                    (cell_x_max          , cont_y_min),
                    (cell_x_max + x_space, cont_y_max),
                    color=(0, 0, 0, 0),
                    fill=space_color,  # type: ignore
                    parent=layer,
                )
                # lines
                dearpygui.draw_line(
                    (cell_x_min, cont_y_min),
                    (cell_x_min, cont_y_max),
                    color=line_color,  # type: ignore
                    parent=layer,
                )
                dearpygui.draw_line(
                    (cell_x_max, cont_y_min),
                    (cell_x_max, cont_y_max),
                    color=line_color,  # type: ignore
                    parent=layer,
                )
                cols.remove(cell.col)

            # row
            ln_y1_pos = cell.y_pos + y_min
            ln_y2_pos = ln_y1_pos + cell.height
            if cell.row in rows:
                # outer spacing
                dearpygui.draw_rectangle(
                    (cont_x_min, cell_y_min          ),
                    (cont_x_max, cell_y_min - y_space),
                    color=(0, 0, 0, 0),
                    fill=space_color,  # type: ignore
                    parent=layer,
                )
                dearpygui.draw_rectangle(
                    (cont_x_min, cell_y_max          ),
                    (cont_x_max, cell_y_max + y_space),
                    color=(0, 0, 0, 0),
                    fill=space_color,  # type: ignore
                    parent=layer,
                )
                # lines
                dearpygui.draw_line(
                    (cont_x_min, cell_y_min),
                    (cont_x_max, cell_y_min),
                    color=line_color,  # type: ignore
                    parent=layer,
                )
                dearpygui.draw_line(
                    (cont_x_min, cell_y_max),
                    (cont_x_max, cell_y_max),
                    color=line_color,  # type: ignore
                    parent=layer,
                )
                rows.remove(cell.row)
