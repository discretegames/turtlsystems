"""Core source code file of turtlsystems Python package (https://pypi.org/project/turtlsystems)."""

import os
from tkinter.constants import NO
import turtle
import subprocess
from pathlib import Path
from typing import Any, Callable, List, Dict, Tuple, Iterable, Collection, Sequence, Optional, Union, cast
from tempfile import TemporaryDirectory
from contextlib import ExitStack
from tkinter import TclError
from shutil import copyfile
from string import digits
from PIL import Image
from packaging import version

# Types:
Color = Tuple[int, int, int]
OpColor = Optional[Color]

# Globals:
DEFAULT_COLORS = (
    (255, 255, 255),
    (128, 128, 128),
    (255, 0, 0),
    (255, 128, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 255, 255),
    (0, 0, 255),
    (128, 0, 255),
    (255, 0, 255),
)
PNG_EXT, GIF_EXT, EPS_EXT = '.png', '.gif', '.eps'
FINAL_NAME, FRAME_NAME, LEVEL_NAME, DRAW_DIR_NAME = 'final', 'frame', 'level', 'draw'
DPI = 96

# Mutating globals:
_DRAW_NUMBER = 0
_INITIALIZED = _WAITED = _SILENT = False
_GHOSTSCRIPT = ''


# Dataclasses are not in 3.6 and SimpleNamespace is not typed properly so decided to use a plain class for State.
class State:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """L-system state."""

    def __init__(
        self,
        position: Tuple[float, float],
        heading: float, angle: float,
        length: float,
        thickness: float,
        pen_color: OpColor,
        fill_color: OpColor,
        swap_signs: bool,
        swap_cases: bool,
        modify_fill: bool
    ) -> None:
        self.position = position
        self.heading = heading
        self.angle = angle
        self.length = length
        self.thickness = thickness
        self.pen_color = pen_color
        self.fill_color = fill_color
        self.swap_signs = swap_signs
        self.swap_cases = swap_cases
        self.modify_fill = modify_fill


#####################
# Package Functions #
#####################


def init(
    window_size: Tuple[float, float] = (0.75, 0.75),
    window_title: str = "TurtLSystems",
    background_color: Tuple[int, int, int] = (0, 0, 0),
    background_image: Optional[str] = None,
    window_position: Optional[Tuple[Optional[int], Optional[int]]] = None,
    canvas_size: Optional[Tuple[Optional[int], Optional[int]]] = None,
    ghostscript: Optional[str] = None,
    mode: str = 'standard',
    delay: Optional[int] = None,
    silent: bool = False
) -> None:
    """Initializes global TurtLSystems properties.
    Calling this is optional and only needed when customization is desired.
    If used it should only be called once and placed before all calls to `draw` and `wait`.

    Args:
        - `window_size=(0.75, 0.75)` (Tuple[int | float, int | float]):
            The size of the window. Use integers for pixel dimensions. Use floats for a percentage of the screen size.
        - `window_title="TurtLSystems"` (str):
            The title of the window.
        - `background_color=(0, 0, 0)` (Tuple[int, int, int]):
            The background color of the window as a 0-255 rgb tuple. May be changed later by draw calls.
        - `background_image=None` (str | None):
            The file path to a background image for the window.
        - `window_position=None` (Tuple[int | None, int | None] | None):
            The top and left screen coordinates of the window, or None for centered.
        - `canvas_size=None` (Tuple[int | None, int | None] | None):
            The size of the drawing canvas when an area larger than the window size is desired.
        - `ghostscript=None` (str | None):
            The path to or command name of ghostscript.
            When None, an educated guess of the path is made on Windows and 'gs' is used on Mac/Linux.
            Ghostscript is the image conversion tool required for png and gif output:
            https://ghostscript.com/releases/gsdnld.html
        - `mode='standard'` (str):
            The turtle graphics coordinates mode. Either 'standard' or 'logo'.
        - `delay=None` (int | None):
            The turtle graphics animation delay in milliseconds. None for default value.
        - `silent=False` (bool):
            Whether to silence all messages and warnings produced by TurtLSystems.

    Returns nothing.
    """
    global _SILENT, _GHOSTSCRIPT, _INITIALIZED
    _SILENT = silent
    if _WAITED:
        message('Did not init() because wait() was already called.')
        return
    _GHOSTSCRIPT = ghostscript or ''
    turtle.title(window_title)
    turtle.mode(mode)
    if delay is not None:
        turtle.delay(delay)
    turtle.colormode(255)
    turtle.bgcolor(background_color)
    window_w, window_h = window_size
    window_x, window_y = window_position or (None, None)
    turtle.setup(window_w, window_h, window_x, window_y)
    # Use 1x1 canvas size unless canvas is actually bigger than window to avoid weird unnecessary scrollbars.
    # The canvas will still fill out the window, it won't behave like 1x1.
    canvas = turtle.getcanvas()  # Used to get final int window size as window_size may have been floats.
    canvas_size = canvas_size or (None, None)
    canvas_w = 1 if canvas_size[0] is None or canvas_size[0] <= canvas.winfo_width() else canvas_size[0]
    canvas_h = 1 if canvas_size[1] is None or canvas_size[1] <= canvas.winfo_height() else canvas_size[1]
    turtle.screensize(canvas_w, canvas_h)
    turtle.bgpic(background_image)
    _INITIALIZED = True


# Horrendously long function, I know, but can't be bothered to refactor.
def draw(  # pylint: disable=too-many-branches,too-many-statements
    # Positional args:
    start: str = 'F+G+G',
    rules: Union[Dict[str, str], str] = 'F {F+{G}-F}-G+F G GG',  # TODO back to normal
    level: int = 4,
    angle: float = 120,
    length: float = 20,
    thickness: float = 1,
    color: Optional[Tuple[int, int, int]] = (255, 255, 255),
    fill_color: Optional[Tuple[int, int, int]] = (128, 128, 128),
    background_color: Optional[Tuple[int, int, int]] = None,
    asap: bool = False,
    *,
    # Customization args:
    colors: Optional[Iterable[Optional[Tuple[int, int, int]]]] = None,
    position: Tuple[float, float] = (0, 0),
    heading: float = 0,
    scale: float = 1,
    prefix: str = '',
    suffix: str = '',
    max_chars: Optional[int] = None,
    # Turtle args:
    speed: Union[int, str] = 'fastest',
    show_turtle: bool = False,
    turtle_shape: str = 'classic',
    circle: float = 360,
    # Increment args:
    angle_increment: float = 15,
    length_increment: float = 5,
    length_scalar: float = 2,
    thickness_increment: float = 1,
    red_increment: int = 1,
    green_increment: int = 1,
    blue_increment: int = 1,
    # Text args:
    text: Optional[str] = None,
    text_color: Optional[Tuple[int, int, int]] = (255, 255, 255),
    text_position: Tuple[int, int] = (0, -200),
    font: str = 'Arial',
    font_size: int = 16,
    font_type: str = 'normal',
    align: str = 'center',
    # Png and gif frame args:
    png: Optional[str] = None,
    padding: Optional[int] = 10,
    transparent: bool = False,
    antialiasing: int = 4,
    output_scale: float = 1,
    # Gif args:
    gif: Optional[str] = None,
    frame_every: Union[int, Collection[str]] = 1,
    max_frames: int = 100,
    duration: int = 20,
    pause: int = 500,
    defer: int = 0,
    loops: Optional[int] = None,
    growth: bool = False,
    reverse: bool = False,
    alternate: bool = False,
    optimize: bool = True,
    # Advanced args:
    tmpdir: Optional[str] = None,
    skip_init: bool = False,
    callback: Optional[Callable[[str, turtle.Turtle], Optional[bool]]] = None,
) -> Tuple[str, Optional[turtle.Turtle]]:
    """Opens a turtle graphics window and draws an L-system pattern based on the arguments provided.
    When called multiple times all patterns are drawn to the same canvas.

    All arguments are optional but `start` and `rules` are the most important because they define the L-system,
    and `level` defines how many expansion steps take place. On an expansion step, every character in `start` is
    replaced with what it maps to in `rules` (or left unchanged if not present) resulting in a new string.
    The characters of the string after the last expansion are the instructions the turtle follows to draw a pattern.
    All non-whitespace printable ASCII characters have meaning. See the `lsystem` function documentation for specifics.

    Call `draw()` by itself to see an example Sierpinski triangle pattern.

    Positional args:
        - `start='F+G+G'` (str):
            The initial string or axiom of the L-system. Level 0.
        - `rules='F F+G-F-G+F G GG'` (Dict[str, str] | str):
            Dictionary that maps characters to what they are replaced with in the L-system expansion step.
            May also be a string where whitespace separated pairs of substrings correspond to the character and its
            replacement. For example `{'A': 'AB', 'B': 'B+A'}` and `'A AB B B+A'` represent the same rules.
        - `level=4` (int):
            The number of L-system expansion steps to take, i.e. how many times to apply `rules` to `start`.
        - `angle=120` (float):
            The angle to turn by on `+` or `-`. Defaults to degrees but can be changed with `circle`.
        - `length=20` (float):
            The distance in pixels to move forward by on letters.
        - `thickness=1` (float):
            Line width in pixels.
        - `color=(255, 255, 255)` (Optional[Tuple[int, int, int]]):
            Line color. 0-255 rgb tuple or None to hide all lines. Selected on `0`.
        - `fill_color=(128, 128, 128)` (Optional[Tuple[int, int, int]]):
            Fill color for `{...}` polygons `@` dots and turtle shapes.
            0-255 rgb tuple or None to hide all fills. Selected on `1`.
        - `background_color=None` (Optional[Tuple[int, int, int]]):
            0-255 rgb tuple for window background color or unchanged if None.
        - `asap=False` (bool):
            When True the draw will happen as fast as possible.

    Customization args:
        - `colors=None` (Optional[Iterable[Optional[Tuple[int, int, int]]]]):
            x
        - `position=(0, 0)` (Tuple[float, float]):
            x
        - `heading=0` (float):
            x
        - `scale=1'` (float):
            x
        - `prefix=''` (str):
            x
        - `suffix=''` (str):
            x
        - `max_chars=None` (Optional[int]):
            x

    Turtle args:
        - `speed='fastest'` (int | str):
            x
        - `show_turtle=False` (bool):
            x
        - `turtle_shape='classic'` (str):
            x
        - `circle=360` (float):
            x

    Increment args:
        - `angle_increment=15` (float):
            x
        - `length_increment=5` (float):
            x
        - `length_scalar=2` (float):
            x
        - `thickness_increment=1` (float):
            x
        - `red_increment=1` (int):
            x
        - `green_increment=1` (int):
            x
        - `blue_increment=1` (int):
            x

    Text args:
        - `text=None` (Optional[str]):
            x
        - `text_color=(255, 255, 255)` (Optional[Tuple[int, int, int]]):
            x
        - `text_position=(0, -200)` (Tuple[int, int]):
            x
        - `font='Arial` (str):
            x
        - `font_size=16` (int):
            x
        - `font_type='normal'` (str):
            x
        - `align='center'` (str):
            x

    Png and gif frame args:
        - `png=None` (Optional[str]):
            x
        - `padding=10` (Optional[int]):
            x
        - `transparent=False` (bool):
            x
        - `antialiasing=4` (int):
            x
        - `output_scale=1` (float):
            x

    Gif args:
        - `gif=None` (Optional[str]):
            x
        - `frame_every=1` (int | Collection[str]):
            x
        - `max_frames=100` (int):
            x
        - `duration=20` (int):
            x
        - `pause=500` (int):
            x
        - `defer=0` (int):
            x
        - `loops=None` (Optional[int]):
            x
        - `growth=False` (bool):
            x
        - `reverse=False` (bool):
            x
        - `alternate=False` (bool):
            x
        - `optimize=True` (bool):
            x

    Advanced args:
        - `tmpdir=None` (Optional[str]):
            x
        - `skip_init=False` (bool):
            x
        - `callback=None` (Optional[Callable[[str, turtle.Turtle], Optional[bool]]]):
            x
    ---
    Returns 2-tuple of the final L-system string and the turtle graphics Turtle object used to draw the pattern.
    (Tuple[str, Optional[turtle.Turtle]])
    """
    global _DRAW_NUMBER, _GHOSTSCRIPT
    _DRAW_NUMBER += 1
    if _WAITED:
        message('Did not draw() because wait() was already called.')
        return '', None
    if not skip_init and not _INITIALIZED:
        init()

    turtle.colormode(255)
    if background_color:
        turtle.bgcolor(background_color)
    true_background_color = cast(Color, conform_color(turtle.bgcolor()))

    if png or gif:
        if not _GHOSTSCRIPT:
            _GHOSTSCRIPT = guess_ghostscript()
            message(f'Guessed ghostscript to be "{_GHOSTSCRIPT}".')

    if gif and growth:  # Do growth animation of all levels of the L-system with recursive draw png calls.
        # Didn't put this in own function since it would need every single little arg. Cumbersome either way.
        with ExitStack() as exit_stack:
            if not tmpdir:
                tmpdir = exit_stack.enter_context(TemporaryDirectory())
            drawdir = make_drawdir(tmpdir)
            pngs = []
            for lvl in range(level + 1):
                pngs.append(str((drawdir / f'{LEVEL_NAME}{lvl}').with_suffix(PNG_EXT)))
                lvl_string, lvl_t = draw(
                    start, rules, lvl, angle, length, thickness, color, fill_color,
                    None, lvl != level or asap, png=pngs[-1], padding=None, tmpdir=tmpdir,  # <-- Key differences.
                    colors=colors, position=position, heading=heading, scale=scale, output_scale=output_scale,
                    prefix=prefix, suffix=suffix, max_chars=max_chars, speed=speed, show_turtle=show_turtle,
                    turtle_shape=turtle_shape, circle=circle, angle_increment=angle_increment,
                    length_increment=length_increment, length_scalar=length_scalar,
                    thickness_increment=thickness_increment, red_increment=red_increment,
                    green_increment=green_increment, blue_increment=blue_increment, text=text,
                    text_color=text_color, text_position=text_position, font=font, font_size=font_size,
                    font_type=font_type, align=align, transparent=transparent, antialiasing=antialiasing
                )
                lvl_t = cast(turtle.Turtle, lvl_t)
                if lvl != level:
                    lvl_t.clear()
                    lvl_t.hideturtle()

            rect_for_all = None
            for i, lvl_png in enumerate(reversed(pngs)):
                image = Image.open(lvl_png).convert('RGBA')
                image, rect = pad_image(image, padding, rect_for_all, output_scale, true_background_color, transparent)
                if not i:
                    rect_for_all = rect
                image.save(lvl_png)

            last_frame = Image.open(pngs[-1]).convert('RGBA')
            last_frame, rect_for_all = pad_image(
                last_frame, padding, None, output_scale, true_background_color, transparent)

            for lvl_png in pngs:
                image = Image.open(lvl_png).convert('RGBA')

            if png:
                try:
                    png = str(Path(png).with_suffix(PNG_EXT).resolve())
                    copyfile(pngs[-1], png)
                    message(f'Saved png "{png}".')
                except Exception as e:  # pylint: disable=broad-except
                    message('Unable to save png:', e)
            try:
                save_gif(gif, pngs, transparent, duration, pause, defer, loops, reverse, alternate, optimize)
                message(f'Saved growth gif "{gif}".')
            except Exception as e:  # pylint: disable=broad-except
                message('Unable to save growth gif:', e)
        return lvl_string, lvl_t
    # End of growth flag code.

    if asap:
        saved_tracer, saved_delay = turtle.tracer(), turtle.delay()
        turtle.tracer(0, 0)

    t = turtle.Turtle()
    if text and text_color:
        orient(t, text_position)
        t.pencolor(text_color)
        try:
            t.write(text, False, align, (font, font_size, font_type))
        except Exception as e:  # pylint: disable=broad-except
            message('Unable to add text:', e)
    t.pencolor(true_background_color)  # Ensure initial colors are tuples.
    t.fillcolor(true_background_color)
    if show_turtle:
        t.showturtle()
    else:
        t.hideturtle()
    t.shape(turtle_shape)
    t.degrees(circle)
    t.speed(speed)
    position = scale * position[0], scale * position[1]
    orient(t, position, heading)

    string = prefix + lsystem(start, rules, level) + suffix
    with ExitStack() as exit_stack:
        if png or gif:
            if not tmpdir:
                tmpdir = exit_stack.enter_context(TemporaryDirectory())
            drawdir = make_drawdir(tmpdir)

        eps_paths, size = run(t=t,
                              string=string,
                              colors=make_colors(color, fill_color, colors),
                              circle=circle,
                              position=position,
                              heading=heading,
                              angle=angle,
                              length=scale*length,
                              thickness=scale*thickness,
                              angle_increment=angle_increment,
                              length_increment=scale*length_increment,
                              length_scalar=scale*length_scalar,
                              thickness_increment=scale*thickness_increment,
                              color_increments=(red_increment, green_increment, blue_increment),
                              max_chars=max_chars,
                              gif=gif,
                              frame_every=frame_every,
                              max_frames=max_frames,
                              drawdir=drawdir if gif else None,
                              callback=callback)

        if png:
            eps = str((drawdir / FINAL_NAME).with_suffix(EPS_EXT))
            try:
                png, _ = save_png(png, eps, save_eps(eps), output_scale, antialiasing,
                                  true_background_color, transparent, padding)
                message(f'Saved png "{png}".')
            except Exception as e:  # pylint: disable=broad-except
                message('Unable to save png:', e)

        if gif:
            try:
                pngs = prep_gif(eps_paths, size, true_background_color,
                                output_scale, antialiasing, padding, transparent)
                save_gif(gif, pngs, transparent, duration, pause, defer, loops, reverse, alternate, optimize)
                message(f'Saved gif "{gif}".')
            except Exception as e:  # pylint: disable=broad-except
                message('Unable to save gif:', e)

        if asap:
            turtle.tracer(saved_tracer, saved_delay)
            turtle.update()

    return string, t


def wait(exit_on_click: bool = True, *, skip_init: bool = False) -> None:
    """Keeps window open. Calling this is optional.
    If used it should only be called once and be placed after all calls to `draw`.

    Args:
        - `exit_on_click=True` (bool):
            Whether the window can be closed by clicking anywhere.
        - `skip_init=False` (bool):
            For advanced use. Whether to skip calling `init` when it hasn't been called already.

    Returns nothing.
    """
    if not skip_init and not _INITIALIZED:
        init()
    global _WAITED
    if not _WAITED:
        _WAITED = True
        (turtle.exitonclick if exit_on_click else turtle.done)()


def lsystem(start: str, rules: Union[Dict[str, str], str], level: int) -> str:
    """Expands the L-system string `start` according to `rules` `level` number of times, returning the resulting string.

    When the L-system is run, every non-whitespace printable ASCII character has meaning. TODO
    ```
    TODO
    ```
    """
    if isinstance(rules, str):
        rules = make_rules(rules)
    for _ in range(level):
        start = ''.join(rules.get(c, c) for c in start)
    return start


####################
# Helper Functions #
####################


def message(*args: Any, **kwargs: Any) -> None:
    """Alias for `print` but only runs when not silenced."""
    if not _SILENT:
        print(*args, **kwargs)


def clamp(value: int, minimum: int = 0, maximum: int = 255) -> int:
    """Clamps `value` between `minimum` and `maximum`."""
    return max(minimum, min(value, maximum))


def conform_color(color: Optional[Sequence[float]]) -> OpColor:
    """Ensures `color` is a tuple with 0-255 clamped rgb."""
    if color:
        return clamp(int(color[0])), clamp(int(color[1])), clamp(int(color[2]))
    return None


def make_rules(rules: Union[Dict[str, str], str]) -> Dict[str, str]:
    """Creates rules dict."""
    if isinstance(rules, str):
        split = rules.split()
        rules = dict(zip(split[::2], split[1::2]))
    return rules


def make_colors(color: OpColor, fill_color: OpColor, colors: Optional[Iterable[OpColor]]) -> Tuple[OpColor, ...]:
    """Creates final colors tuple."""
    if colors is None:
        return conform_color(color), conform_color(fill_color), *DEFAULT_COLORS[2:]
    colors = [conform_color(c) for c, _ in zip(colors, range(len(DEFAULT_COLORS)))]
    colors.extend(DEFAULT_COLORS[len(colors):])
    return tuple(colors)


def make_drawdir(tmpdir: str) -> Path:
    """Creates drawdir in tempdir labeled with current draw number."""
    drawdir = Path(tmpdir).resolve() / f'{DRAW_DIR_NAME}{_DRAW_NUMBER}'
    drawdir.mkdir(parents=True, exist_ok=True)
    for file in drawdir.iterdir():  # Carefully delete files in the drawdir that were from previous runs.
        if file.is_file() and file.suffix in (PNG_EXT, EPS_EXT) and \
                file.stem.rstrip(digits) in (FINAL_NAME, FRAME_NAME, LEVEL_NAME):
            file.unlink(missing_ok=True)
    # drawdir folders are never deleted themselves because it would be too easy to accidentally delete user data.
    return drawdir


def orient(t: turtle.Turtle, position: Optional[Tuple[float, float]], heading: Optional[float] = None) -> None:
    """Silently orients turtle `t` to given `position` and `heading`."""
    speed = t.speed()
    down, visible = t.isdown(), t.isvisible()
    t.penup()
    t.hideturtle()
    t.speed(0)
    if position:
        t.setposition(position)
    if heading is not None:
        t.setheading(heading)
    t.speed(speed)
    if down:
        t.pendown()
    if visible:
        t.showturtle()


def guess_ghostscript() -> str:
    """Guess the path to ghostscript. Only guesses well on Windows.
    Should prevent people from needing to add ghostscript to PATH.
    """
    if os.name != 'nt':
        return 'gs'  # I'm not sure where to look on non-Windows OSes so just guess 'gs'.
    locations = 'C:\\Program Files\\gs', 'C:\\Program Files (x86)\\gs'
    files = 'gswin64c.exe', 'gswin32c.exe', 'gs.exe'
    for location in locations:
        path = Path(location)
        if path.exists():
            versions = [v for v in path.iterdir() if v.is_dir() and v.name.startswith('gs')]
            versions.sort(key=lambda v: version.parse(v.name[2:]), reverse=True)
            for v in versions:
                for file in files:
                    exe = v / 'bin' / file
                    if exe.exists():
                        return str(exe)
    return 'gswin64c'  # Last ditch guess.


def eps_to_png(eps: str, png: str, size: Tuple[int, int], output_scale: float, antialiasing: int) -> None:
    """Uses ghostscript to convert eps file to png with transparent background."""
    result = subprocess.run([_GHOSTSCRIPT,
                             '-q',
                            '-dSAFER',
                             '-dBATCH',
                             '-dNOPAUSE',
                             '-dEPSCrop',
                             '-sDEVICE=pngalpha',
                             f'-r{round(DPI * output_scale)}',
                             f'-g{round(output_scale * size[0])}x{round(output_scale * size[1])}',
                             f'-dGraphicsAlphaBits={antialiasing}',
                             f'-dTextAlphaBits={antialiasing}',
                             f'-sOutputFile={png}',
                             eps],
                            check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')
    if result.returncode:
        message(f'Ghostscript ({_GHOSTSCRIPT}) exit code {result.returncode}:')
        message(result.stdout)


def get_padding_rect(
        image: Image.Image, padding: int, background_color: Color) -> Tuple[int, int, int, int]:
    """Returns rectangle around content pixels in `image` padded by `padding` on all sides."""
    message(f'Calculating padding for {image.width}x{image.height} pixel image...')
    x_min, y_min, x_max, y_max = image.width - 1, image.height - 1, 0, 0
    data = image.load()
    empty = True
    for y in range(image.height):
        for x in range(image.width):
            if data[x, y][3] == 0 or background_color == data[x, y][:3]:
                continue
            empty = False
            x_min = min(x_min, x)
            y_min = min(y_min, y)
            x_max = max(x_max, x)
            y_max = max(y_max, y)
    if empty:
        x_min = x_max = image.width//2
        y_min = y_max = image.height//2
    x_min -= padding
    y_min -= padding
    x_max = max(x_max + padding, x_min) + 1
    y_max = max(y_max + padding, y_min) + 1
    return x_min, y_min, x_max, y_max


def save_eps(eps: str) -> Tuple[int, int]:
    """Saves current turtle graphics canvas as encapsulated postscript file."""
    turtle.update()
    canvas = turtle.getcanvas()
    width = max(canvas.winfo_width(), canvas.canvwidth)  # type: ignore
    height = max(canvas.winfo_height(), canvas.canvheight)  # type: ignore
    canvas.postscript(file=eps, x=-width//2, y=-height//2, width=width, height=height)  # type: ignore
    return width, height


def pad_image(
    image: Image.Image,
    padding: Optional[int],
    rect: Optional[Tuple[int, int, int, int]],
    output_scale: float,
    background_color: Color,
    transparent: bool
) -> Tuple[Image.Image, Optional[Tuple[int, int, int, int]]]:
    """Pads image on all sides and gives it correct background color."""
    if padding is not None:
        if not rect:
            rect = get_padding_rect(image, round(output_scale * padding), background_color)
        image = image.crop(rect)
    # Transparent backgrounds still have the correct color but alpha is 0.
    background = Image.new('RGBA', image.size, background_color + ((0,) if transparent else (255,)))
    return Image.alpha_composite(background, image), rect


def save_png(
    png: Optional[str],
    eps: str,
    size: Tuple[int, int],
    output_scale: float,
    antialiasing: int,
    background_color: Color,
    transparent: bool,
    padding: Optional[int],
    rect: Optional[Tuple[int, int, int, int]] = None,
) -> Tuple[str, Optional[Tuple[int, int, int, int]]]:
    """Finalizes pre-existing eps file into png with background and padding."""
    if not png:
        png = eps
    png = str(Path(png).with_suffix(PNG_EXT).resolve())
    eps_to_png(eps, png, size, output_scale, antialiasing)
    image = Image.open(png).convert('RGBA')
    image, rect = pad_image(image, padding, rect, output_scale, background_color, transparent)
    image.save(png)
    return png, rect


def prep_gif(eps_paths: List[str], size: Tuple[int, int], background_color: Color, output_scale: float,
             antialiasing: int, padding: Optional[int], transparent: bool) -> List[str]:
    """Converts eps files into pngs in preperation for gif. Returns list of png paths."""
    pngs, rect_for_all = [], None
    for i, eps in enumerate(reversed(eps_paths)):  # Reverse so rect_for_all corresponds to last frame.
        png, rect = save_png(None, eps, size, output_scale, antialiasing,
                             background_color, transparent, padding, rect_for_all)
        pngs.append(png)
        if not i:
            rect_for_all = rect
            message(f'Making {len(eps_paths)} gif frames..', end='', flush=True)
        elif (len(eps_paths) - i) % 10 == 0:
            message(f'{len(eps_paths) - i}..', end='', flush=True)
    pngs.reverse()
    message('.')
    return pngs


def save_gif(
    gif: str,
    pngs: List[str],
    transparent: bool,
    duration: int,
    pause: int,
    defer: int,
    loops: Optional[int],
    reverse: bool,
    alternate: bool,
    optimize: bool,
) -> str:
    """Saves gif from pre-generated png files. Returns path to gif."""
    images = [Image.open(png).convert('RGBA') for png in pngs]
    if reverse:
        images.reverse()
    if alternate:
        images.extend(images[-2:0:-1])
    gif = str(Path(gif).with_suffix(GIF_EXT).resolve())
    frames = [images[0]] * (defer // duration) + images + [images[-1]] * (pause // duration)
    frames[0].save(gif, save_all=True, append_images=frames[1:], loop=loops or 0, duration=duration,
                   optimize=optimize, transparency=0 if transparent else 255)
    # PIL seems to treat blank animated gifs like static gifs, so their timing is wrong. But nbd since they're blank.
    return gif


def run(  # pylint: disable=too-many-branches,too-many-statements
    *,
    t: turtle.Turtle,
    string: str,
    colors: Tuple[OpColor, ...],
    circle: float,
    position: Tuple[float, float],
    heading: float,
    angle: float,
    length: float,
    thickness: float,
    angle_increment: float,
    length_increment: float,
    length_scalar: float,
    thickness_increment: float,
    color_increments: Tuple[int, int, int],
    max_chars: Optional[int],
    gif: Optional[str],
    frame_every: Union[int, Collection[str]],
    max_frames: int,
    drawdir: Optional[Path],
    callback: Optional[Callable[[str, turtle.Turtle], Optional[bool]]]
) -> Tuple[List[str], Tuple[int, int]]:
    """Run turtle `t` on L-system string `string` with given options."""
    initial_angle, initial_length, initial_thickness = angle, length, thickness
    swap_signs, swap_cases, modify_fill = False, False, False
    pen_color, fill_color = colors[0], colors[1]
    stack: List[State] = []
    eps_paths: List[str] = []
    size = (1, 1)
    draws, frames_attempted = 0, 0

    def save_frame() -> None:
        nonlocal frames_attempted, size
        frames_attempted += 1
        if len(eps_paths) < max_frames:
            eps = str((cast(Path, drawdir) / f'{FRAME_NAME}{len(eps_paths)}').with_suffix(EPS_EXT))
            size = save_eps(eps)
            eps_paths.append(eps)

    def gif_handler() -> None:
        if gif:
            nonlocal draws
            draws += 1
            if isinstance(frame_every, int) and draws % frame_every == 0:
                save_frame()

    def set_pensize() -> None:
        t.pensize(max(0, thickness))  # type: ignore

    def set_color(color: OpColor) -> None:
        nonlocal pen_color, fill_color, modify_fill
        if modify_fill:
            modify_fill = False
            fill_color = color
            if fill_color:
                t.fillcolor(fill_color)
        else:
            pen_color = color
            if pen_color:
                t.pencolor(pen_color)

    def increment_color(channel: int, decrement: bool = False) -> None:
        color = fill_color if modify_fill else pen_color
        if color:
            amount = (-1 if decrement else 1) * color_increments[channel]
            lst = list(color)
            lst[channel] = clamp(lst[channel] + amount)
            set_color((lst[0], lst[1], lst[2]))

    set_pensize()
    if pen_color:
        t.pencolor(pen_color)
    if fill_color:
        t.fillcolor(fill_color)
    if gif:
        save_frame()

    for i, c in enumerate(string):
        if max_chars is not None and i >= max_chars:
            break
        if swap_cases and c.isalpha():
            c = c.lower() if c.isupper() else c.upper()

        # Length:
        if 'A' <= c <= 'Z':
            if pen_color and t.pensize():
                t.pendown()
            else:
                t.penup()
            t.forward(length)
            gif_handler()
        elif 'a' <= c <= 'z':
            t.penup()
            t.forward(length)
        elif c == '_':
            length = initial_length
        elif c == '^':
            length += length_increment
        elif c == '%':
            length -= length_increment
        elif c == '*':
            length *= length_scalar
        elif c == '/':
            length /= length_scalar
        # Angle:
        elif c == '+':
            (t.right if swap_signs else t.left)(angle)
        elif c == '-':
            (t.left if swap_signs else t.right)(angle)
        elif c == '&':
            swap_signs = not swap_signs
        elif c == '|':
            t.right(circle/2.0)
        elif c == '~':
            angle = initial_angle
        elif c == ')':
            angle += angle_increment
        elif c == '(':
            angle -= angle_increment
        # Thickness:
        elif c == '=':
            thickness = initial_thickness
            set_pensize()
        elif c == '>':
            thickness += thickness_increment
            set_pensize()
        elif c == '<':
            thickness -= thickness_increment
            set_pensize()
        # Color:
        elif '0' <= c <= '9':
            set_color(colors[int(c)])
        elif c == '#':
            modify_fill = True
        elif c == '.':
            increment_color(0)
        elif c == ',':
            increment_color(0, True)
        elif c == ':':
            increment_color(1)
        elif c == ';':
            increment_color(1, True)
        elif c == '!':
            increment_color(2)
        elif c == '?':
            increment_color(2, True)
        # Other:
        elif c == '{':
            if fill_color:
                t.begin_fill()
        elif c == '}':
            if fill_color:
                t.end_fill()
            gif_handler()
        elif c == '@':
            if fill_color:
                t.dot(None, fill_color)
            gif_handler()
        elif c == '`':
            swap_cases = not swap_cases
        elif c == '"':
            orient(t, position)
        elif c == "'":
            orient(t, None, heading)
        elif c == '$':
            stack.clear()
        elif c == '[':
            stack.append(State((t.xcor(), t.ycor()), t.heading(), angle, length, thickness,
                               pen_color, fill_color, swap_signs, swap_cases, modify_fill))
        elif c == ']':
            if stack:
                state = stack.pop()
                orient(t, state.position, state.heading)
                angle, length = state.angle, state.length
                swap_signs, swap_cases, modify_fill = state.swap_signs, state.swap_cases, state.modify_fill
                pen_color, fill_color = state.pen_color, state.fill_color

        if not isinstance(frame_every, int) and c in frame_every:
            save_frame()

        if callback and callback(c, t) or c == '\\':
            break

    if gif:
        if isinstance(frame_every, int) and draws % frame_every != 0:
            save_frame()  # Save frame of final changes unless nothing has changed.
        message(f'Prepped {len(eps_paths)} gif frames of {frames_attempted} attempted for {draws + 1} draws.')

    return eps_paths, size


if __name__ == '__main__':
    try:
        init((600, 800))
        ss, tt = draw()
        tt.clear()
        draw(background_color=(255, 255, 255))
        wait()
    except (turtle.Terminator, TclError):
        pass
