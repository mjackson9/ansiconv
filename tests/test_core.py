import pytest

from ansiconv import ConversionError, ansi_to_html, html_to_ansi


# --- ansi_to_html -----------------------------------------------------

def test_plain_text_is_escaped_but_unstyled():
    assert ansi_to_html("hello & <world>") == "hello &amp; &lt;world&gt;"


def test_bold_and_fg_color():
    result = ansi_to_html("\x1b[1;31mERROR\x1b[0m: build failed")
    assert result == '<span class="ansi-bold ansi-fg-red">ERROR</span>: build failed'


def test_reset_with_no_open_state_is_a_no_op():
    assert ansi_to_html("\x1b[0mhello") == "hello"


def test_fg_and_bg_together():
    result = ansi_to_html("\x1b[32;41mtext\x1b[0m")
    assert result == '<span class="ansi-fg-green ansi-bg-red">text</span>'


def test_fg_default_code_clears_only_foreground():
    result = ansi_to_html("\x1b[31mred\x1b[39mplain\x1b[0m")
    assert result == '<span class="ansi-fg-red">red</span>plain'


def test_strict_rejects_unsupported_sgr_code():
    with pytest.raises(ConversionError):
        ansi_to_html("\x1b[5mblink\x1b[0m")


def test_lenient_drops_unsupported_sgr_code():
    assert ansi_to_html("\x1b[5mblink\x1b[0m", lenient=True) == "blink"


def test_strict_rejects_cursor_movement_sequence():
    with pytest.raises(ConversionError):
        ansi_to_html("\x1b[2Jcleared")


def test_lenient_skips_cursor_movement_sequence():
    assert ansi_to_html("\x1b[2Jcleared", lenient=True) == "cleared"


# --- html_to_ansi -------------------------------------------------------

def test_html_to_ansi_basic_span():
    result = html_to_ansi('<span class="ansi-bold ansi-fg-red">ERROR</span>: build failed')
    assert result == "\x1b[0;1;31mERROR\x1b[0m: build failed\x1b[0m"


def test_html_to_ansi_strict_rejects_unknown_tag():
    with pytest.raises(ConversionError):
        html_to_ansi("<div>x</div>")


def test_html_to_ansi_lenient_skips_unknown_tag():
    result = html_to_ansi("<div>x</div>", lenient=True)
    assert ansi_to_html(result) == "x"


def test_html_to_ansi_strict_rejects_unknown_class():
    with pytest.raises(ConversionError):
        html_to_ansi('<span class="ansi-blink">x</span>')


def test_html_to_ansi_lenient_ignores_unknown_class():
    result = html_to_ansi('<span class="ansi-blink">x</span>', lenient=True)
    assert ansi_to_html(result) == "x"


def test_html_to_ansi_strict_rejects_unmatched_closing_tag():
    with pytest.raises(ConversionError):
        html_to_ansi("</span>text")


def test_html_to_ansi_lenient_ignores_unmatched_closing_tag():
    assert html_to_ansi("</span>text", lenient=True) == "text"


def test_html_to_ansi_strict_rejects_unclosed_tag():
    with pytest.raises(ConversionError):
        html_to_ansi('<span class="ansi-bold">x')


def test_html_to_ansi_lenient_allows_unclosed_tag():
    result = html_to_ansi('<span class="ansi-bold">x', lenient=True)
    assert result == "\x1b[0;1mx\x1b[0m"


# --- round trips ----------------------------------------------------------

ROUND_TRIP_SAMPLES = [
    "\x1b[1;31mERROR\x1b[0m: build failed",
    "\x1b[32mok\x1b[0m",
    "\x1b[1m\x1b[4mbold underline\x1b[0m",
    "plain text with & < > chars",
    "\x1b[35;46mtext\x1b[0m more \x1b[93mtext2\x1b[0m",
    "\x1b[1mBold \x1b[31mBoldRed\x1b[22mRedOnly\x1b[0mplain",
]


@pytest.mark.parametrize("sample", ROUND_TRIP_SAMPLES)
def test_ansi_html_ansi_round_trip_is_idempotent(sample):
    html = ansi_to_html(sample)
    ansi_again = html_to_ansi(html)
    html_again = ansi_to_html(ansi_again)
    assert html_again == html


def test_html_ansi_html_round_trip():
    html = '<span class="ansi-bold ansi-fg-red">ERROR</span>: build failed'
    ansi = html_to_ansi(html)
    assert ansi_to_html(ansi) == html
