from __future__ import annotations
import re
from html import unescape as _html_unescape
from html.parser import HTMLParser
from io import StringIO

_X_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/\d+",
    re.IGNORECASE,
)
_TCO_PATTERN = re.compile(r"https?://t\.co/\w+", re.IGNORECASE)

def is_x_video_url(text: str) -> bool:
    if not text:
        return False
    return bool(_X_URL_PATTERN.search(text) or _TCO_PATTERN.search(text))

def extract_url(text: str) -> str | None:
    m = _X_URL_PATTERN.search(text) or _TCO_PATTERN.search(text)
    return m.group(0) if m else None

async def resolve_t_co(url: str) -> str:
    import httpx
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.head(url)
        return str(resp.url)

_ALLOWED_TAGS = {"b", "i", "u", "s", "a", "code", "pre"}
_ALLOWED_ATTRS = {"a": {"href"}}

_BARE_LT = re.compile(
    r"<(?!/?\s*(?:" + "|".join(_ALLOWED_TAGS) + r")[\s>/])",
    re.IGNORECASE,
)

def _pre_escape_bare_angles(text: str) -> str:
    result = _BARE_LT.sub("&lt;", text)
    result = re.sub(r"(?<![\"'\w/])>", "&gt;", result)
    return result

class _HTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.result = StringIO()
        self.plain_text = StringIO()

    def handle_starttag(self, tag, attrs):
        if tag in _ALLOWED_TAGS:
            allowed = _ALLOWED_ATTRS.get(tag, set())
            attr_str = ""
            for name, value in attrs:
                if name in allowed and value is not None:
                    safe_val = value.replace('"', "&quot;")
                    attr_str += f' {name}="{safe_val}"'
            self.result.write(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        if tag in _ALLOWED_TAGS:
            self.result.write(f"</{tag}>")

    def handle_data(self, data):
        escaped = data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.result.write(escaped)
        self.plain_text.write(data)

    def handle_entityref(self, name):
        entity = f"&{name};"
        self.result.write(entity)
        self.plain_text.write(_html_unescape(entity))

    def handle_charref(self, name):
        ref = f"&#{name};"
        self.result.write(ref)
        self.plain_text.write(_html_unescape(ref))

def sanitize_caption(html: str) -> tuple[str, str | None]:
    preprocessed = _pre_escape_bare_angles(html)
    sanitizer = _HTMLSanitizer()
    sanitizer.feed(preprocessed)
    result = sanitizer.result.getvalue()
    plain_len = len(sanitizer.plain_text.getvalue())
    if plain_len > 1024:
        return result, f"Caption too long ({plain_len}/1024 chars). Please shorten and resend."
    return result, None
