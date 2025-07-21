import textwrap
import unicodedata
from typing import Iterable

TOKEN_LIMIT = 512

def split_text(text: str, width: int = TOKEN_LIMIT) -> Iterable[str]:
    """Yield chunks of at most ``width`` characters safely."""
    safe = unicodedata.normalize("NFC", text)
    for chunk in textwrap.wrap(safe, width=width, break_long_words=False):
        yield chunk
