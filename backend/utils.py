import json
import secrets
import string
from typing import Any

from django.utils.safestring import mark_safe, SafeText
from pygments import highlight
from pygments.formatters import HtmlFormatter  # pylint: disable=no-name-in-module
from pygments.lexers import JsonLexer  # pylint: disable=no-name-in-module


def generate_secret_key(length: int = 128) -> str:
    if length < 16:
        raise ValueError('Secret key with less then 16 symbols is not secure')
    alphabet = string.ascii_letters + string.digits
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (
                any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and sum(c.isdigit() for c in password) >= 3
        ):
            return password


def pretty_json(data: Any) -> SafeText:
    # Convert the data to sorted, indented JSON
    response = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
    # Get the Pygments formatter
    formatter = HtmlFormatter(style='colorful')
    # Highlight the data
    response = highlight(response, JsonLexer(), formatter)
    # Get the stylesheet
    style = "<style>" + formatter.get_style_defs() + "</style><br>"
    # Safe the output
    return mark_safe(style + response)
