"""Conversion between ANSI SGR escape sequences and HTML spans.

Strict mode is the default: any escape sequence or HTML construct we don't
have a mapping for raises ConversionError. --lenient (see cli.py) trades
that safety for best-effort output, which is what you want when the input
is somebody else's log dump rather than something you control.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape as html_escape
from html.parser import HTMLParser
from typing import List, Optional, Tuple, Union


class ConversionError(ValueError):
    """Raised when input can't be converted under the active strictness rules."""


_RESET = 0
_STYLE_ON = {1: "bold", 3: "italic", 4: "underline"}
_STYLE_OFF = {22: "bold", 23: "italic", 24: "underline"}
_FG_NAMED = {
    30: "black", 31: "red", 32: "green", 33: "yellow",
    34: "blue", 35: "magenta", 36: "cyan", 37: "white",
    90: "bright-black", 91: "bright-red", 92: "bright-green", 93: "bright-yellow",
    94: "bright-blue", 95: "bright-magenta", 96: "bright-cyan", 97: "bright-white",
}
_BG_NAMED = {
    40: "black", 41: "red", 42: "green", 43: "yellow",
    44: "blue", 45: "magenta", 46: "cyan", 47: "white",
    100: "bright-black", 101: "bright-red", 102: "bright-green", 103: "bright-yellow",
    104: "bright-blue", 105: "bright-magenta", 106: "bright-cyan", 107: "bright-white",
}
_FG_DEFAULT = 39
_BG_DEFAULT = 49
_FG_EXTENDED = 38
_BG_EXTENDED = 48
_FG_CODE_BY_NAME = {name: code for code, name in _FG_NAMED.items()}
_BG_CODE_BY_NAME = {name: code for code, name in _BG_NAMED.items()}

_DEFAULT_CLASS_PREFIX = "ansi-"

# A full CSI SGR sequence, e.g. "\x1b[1;31m".
_CSI_SGR = re.compile(r"\x1b\[([0-9;]*)m")
# Any other escape sequence (CSI, OSC, or a bare two-byte escape) we might meet.
_ANY_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b.")
_HEX_COLOR = re.compile(r"^#([0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class _Color:
    """A resolved foreground/background colour: named (16-colour), 256-colour
    palette index, or 24-bit RGB. Only one representation is active at a time,
    matching how a single SGR 38/48 sequence replaces whatever colour came
    before it."""

    kind: str  # "named", "256", or "rgb"
    value: Union[str, int, Tuple[int, int, int]]

    def class_name(self) -> Optional[str]:
        if self.kind == "named":
            return str(self.value)
        if self.kind == "256":
            return f"256-{self.value}"
        return None

    def css_hex(self) -> Optional[str]:
        if self.kind != "rgb":
            return None
        r, g, b = self.value
        return f"#{r:02x}{g:02x}{b:02x}"


def _color_from_class(spec: str) -> Optional[_Color]:
    if spec in _FG_CODE_BY_NAME:
        return _Color("named", spec)
    if spec.startswith("256-"):
        try:
            n = int(spec[4:])
        except ValueError:
            return None
        if 0 <= n <= 255:
            return _Color("256", n)
    return None


def _color_from_css(value: str) -> Optional[_Color]:
    m = _HEX_COLOR.match(value.strip())
    if not m:
        return None
    hexs = m.group(1)
    r, g, b = int(hexs[0:2], 16), int(hexs[2:4], 16), int(hexs[4:6], 16)
    return _Color("rgb", (r, g, b))


def _sgr_codes_for(color: Optional[_Color], *, is_bg: bool) -> List[int]:
    if color is None:
        return []
    if color.kind == "named":
        table = _BG_CODE_BY_NAME if is_bg else _FG_CODE_BY_NAME
        return [table[color.value]]
    base = _BG_EXTENDED if is_bg else _FG_EXTENDED
    if color.kind == "256":
        return [base, 5, color.value]
    r, g, b = color.value
    return [base, 2, r, g, b]


@dataclass
class _State:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    fg: Optional[_Color] = None
    bg: Optional[_Color] = None

    def is_default(self) -> bool:
        return not (self.bold or self.italic or self.underline or self.fg or self.bg)

    def clone(self) -> "_State":
        return _State(self.bold, self.italic, self.underline, self.fg, self.bg)


def _parse_extended_color(
    params: List[int], i: int, lenient: bool
) -> Tuple[Optional[_Color], int]:
    """Parse a 38/48 (extended colour) SGR sequence starting at params[i].

    Returns (color, params_consumed). color is None if the sequence was
    malformed and lenient mode let it slide by skipping it.
    """
    if i + 1 >= len(params):
        if not lenient:
            raise ConversionError("truncated extended color SGR sequence")
        return None, len(params) - i

    mode = params[i + 1]
    if mode == 5:
        if i + 2 >= len(params):
            if not lenient:
                raise ConversionError("truncated 256-color SGR sequence")
            return None, len(params) - i
        n = params[i + 2]
        if not 0 <= n <= 255:
            if not lenient:
                raise ConversionError(f"256-color index out of range: {n}")
            return None, 3
        return _Color("256", n), 3

    if mode == 2:
        if i + 4 >= len(params):
            if not lenient:
                raise ConversionError("truncated truecolor SGR sequence")
            return None, len(params) - i
        r, g, b = params[i + 2], params[i + 3], params[i + 4]
        if not all(0 <= c <= 255 for c in (r, g, b)):
            if not lenient:
                raise ConversionError(f"truecolor component out of range: {r},{g},{b}")
            return None, 5
        return _Color("rgb", (r, g, b)), 5

    if not lenient:
        raise ConversionError(f"unsupported extended color mode: {mode}")
    return None, 2


def _apply_sgr(state: _State, params: List[int], lenient: bool) -> None:
    i = 0
    while i < len(params):
        code = params[i]
        if code == _RESET:
            state.bold = state.italic = state.underline = False
            state.fg = state.bg = None
            i += 1
        elif code in _STYLE_ON:
            setattr(state, _STYLE_ON[code], True)
            i += 1
        elif code in _STYLE_OFF:
            setattr(state, _STYLE_OFF[code], False)
            i += 1
        elif code in _FG_NAMED:
            state.fg = _Color("named", _FG_NAMED[code])
            i += 1
        elif code in _BG_NAMED:
            state.bg = _Color("named", _BG_NAMED[code])
            i += 1
        elif code == _FG_DEFAULT:
            state.fg = None
            i += 1
        elif code == _BG_DEFAULT:
            state.bg = None
            i += 1
        elif code in (_FG_EXTENDED, _BG_EXTENDED):
            color, consumed = _parse_extended_color(params, i, lenient)
            if color is not None:
                if code == _FG_EXTENDED:
                    state.fg = color
                else:
                    state.bg = color
            i += consumed
        elif not lenient:
            raise ConversionError(f"unsupported SGR code: {code}")
        else:
            # lenient mode: codes we don't model (blink, strike, ...) are
            # silently dropped rather than guessed at.
            i += 1


def _classes_for(state: _State, class_prefix: str) -> List[str]:
    classes = []
    if state.bold:
        classes.append(f"{class_prefix}bold")
    if state.italic:
        classes.append(f"{class_prefix}italic")
    if state.underline:
        classes.append(f"{class_prefix}underline")
    if state.fg:
        name = state.fg.class_name()
        if name:
            classes.append(f"{class_prefix}fg-{name}")
    if state.bg:
        name = state.bg.class_name()
        if name:
            classes.append(f"{class_prefix}bg-{name}")
    return classes


def _styles_for(state: _State) -> List[str]:
    styles = []
    if state.fg and state.fg.kind == "rgb":
        styles.append(f"color:{state.fg.css_hex()}")
    if state.bg and state.bg.kind == "rgb":
        styles.append(f"background-color:{state.bg.css_hex()}")
    return styles


def ansi_to_html(
    text: str,
    *,
    lenient: bool = False,
    self_closing_br: bool = False,
    class_prefix: str = _DEFAULT_CLASS_PREFIX,
) -> str:
    """Convert a string containing ANSI SGR escapes into HTML <span> markup.

    Newlines become <br> tags (or <br /> if self_closing_br is set), mirroring
    how html_to_ansi already turns <br> back into "\\n" - without this the two
    functions wouldn't round-trip on multi-line input.
    """
    br_tag = "<br />" if self_closing_br else "<br>"
    out: List[str] = []
    state = _State()
    pos = 0
    open_span = False

    while pos < len(text):
        m = _CSI_SGR.match(text, pos)
        if m:
            if open_span:
                out.append("</span>")
                open_span = False
            params = [int(p) for p in m.group(1).split(";") if p] or [0]
            _apply_sgr(state, params, lenient)
            if not state.is_default():
                attrs = []
                classes = _classes_for(state, class_prefix)
                if classes:
                    attrs.append(f'class="{" ".join(classes)}"')
                styles = _styles_for(state)
                if styles:
                    attrs.append(f'style="{";".join(styles)}"')
                out.append(f'<span {" ".join(attrs)}>')
                open_span = True
            pos = m.end()
            continue

        m = _ANY_ESCAPE.match(text, pos)
        if m:
            if not lenient:
                raise ConversionError(f"unsupported escape sequence: {m.group(0)!r}")
            pos = m.end()
            continue

        nxt = text.find("\x1b", pos)
        end = nxt if nxt != -1 else len(text)
        out.append(html_escape(text[pos:end]).replace("\n", br_tag))
        pos = end

    if open_span:
        out.append("</span>")
    return "".join(out)


class _AnsiBuilder(HTMLParser):
    def __init__(self, lenient: bool, class_prefix: str) -> None:
        super().__init__(convert_charrefs=True)
        self.lenient = lenient
        self.class_prefix = class_prefix
        self.out: List[str] = []
        self.stack: List[_State] = [_State()]

    @property
    def state(self) -> _State:
        return self.stack[-1]

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "br":
            self.out.append("\n")
            return

        new_state = self.state.clone()
        attrs_dict = dict(attrs)
        prefix = self.class_prefix
        fg_prefix = f"{prefix}fg-"
        bg_prefix = f"{prefix}bg-"
        if tag == "span":
            for cls in attrs_dict.get("class", "").split():
                if cls == f"{prefix}bold":
                    new_state.bold = True
                elif cls == f"{prefix}italic":
                    new_state.italic = True
                elif cls == f"{prefix}underline":
                    new_state.underline = True
                elif cls.startswith(fg_prefix):
                    color = _color_from_class(cls[len(fg_prefix):])
                    if color is not None:
                        new_state.fg = color
                    elif not self.lenient:
                        raise ConversionError(f"unrecognized span class: {cls!r}")
                elif cls.startswith(bg_prefix):
                    color = _color_from_class(cls[len(bg_prefix):])
                    if color is not None:
                        new_state.bg = color
                    elif not self.lenient:
                        raise ConversionError(f"unrecognized span class: {cls!r}")
                elif not self.lenient:
                    raise ConversionError(f"unrecognized span class: {cls!r}")

            style = attrs_dict.get("style") or ""
            for decl in style.split(";"):
                decl = decl.strip()
                if not decl:
                    continue
                prop, _, value = decl.partition(":")
                prop = prop.strip()
                color = _color_from_css(value)
                if prop == "color" and color is not None:
                    new_state.fg = color
                elif prop == "background-color" and color is not None:
                    new_state.bg = color
                elif not self.lenient:
                    raise ConversionError(f"unrecognized style declaration: {decl!r}")
        elif tag == "b":
            new_state.bold = True
        elif tag == "i":
            new_state.italic = True
        elif tag == "u":
            new_state.underline = True
        elif not self.lenient:
            raise ConversionError(f"unsupported tag: <{tag}>")

        self._emit_transition(new_state)
        self.stack.append(new_state)

    def handle_endtag(self, tag: str) -> None:
        if tag == "br":
            return
        if len(self.stack) == 1:
            if not self.lenient:
                raise ConversionError(f"unmatched closing tag: </{tag}>")
            return
        self.stack.pop()
        self._emit_transition(self.state)

    def handle_data(self, data: str) -> None:
        self.out.append(data)

    def _emit_transition(self, new_state: _State) -> None:
        codes = [0]
        if new_state.bold:
            codes.append(1)
        if new_state.italic:
            codes.append(3)
        if new_state.underline:
            codes.append(4)
        codes.extend(_sgr_codes_for(new_state.fg, is_bg=False))
        codes.extend(_sgr_codes_for(new_state.bg, is_bg=True))
        self.out.append("\x1b[" + ";".join(str(c) for c in codes) + "m")


def html_to_ansi(
    markup: str,
    *,
    lenient: bool = False,
    class_prefix: str = _DEFAULT_CLASS_PREFIX,
) -> str:
    """Convert HTML markup (as produced by ansi_to_html) back into ANSI escapes."""
    builder = _AnsiBuilder(lenient, class_prefix)
    builder.feed(markup)
    builder.close()
    if len(builder.stack) != 1 and not lenient:
        raise ConversionError("unclosed tag at end of input")

    result = "".join(builder.out)
    if result and "\x1b[" in result and not result.endswith("\x1b[0m"):
        result += "\x1b[0m"
    return result
