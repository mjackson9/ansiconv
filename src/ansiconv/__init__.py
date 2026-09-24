"""ansiconv: convert between ANSI SGR escape sequences and HTML."""

from .core import ConversionError, ansi_to_html, ansi_to_plain, html_to_ansi

__version__ = "0.1.0"
__all__ = ["ansi_to_html", "ansi_to_plain", "html_to_ansi", "ConversionError", "__version__"]
