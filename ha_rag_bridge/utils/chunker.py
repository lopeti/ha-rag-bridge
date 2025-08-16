import textwrap
import unicodedata
from typing import Iterable

TOKEN_LIMIT = 512


def split_text(text: str, width: int = TOKEN_LIMIT) -> Iterable[str]:
    """
    Split the input text into chunks of at most ``width`` characters, ensuring safe Unicode handling.

    Parameters:
        text (str): The input string to be split into chunks.
        width (int): The maximum number of characters in each chunk. Defaults to TOKEN_LIMIT.

    Returns:
        Iterable[str]: An iterable of string chunks, each with a maximum length of ``width`` characters.

    Notes:
        The function ensures "safe" handling of Unicode by normalizing the input text to NFC (Normalization Form C),
        which ensures a consistent representation of characters before splitting.
    """
    safe = unicodedata.normalize("NFC", text)
    for chunk in textwrap.wrap(safe, width=width, break_long_words=False):
        yield chunk
