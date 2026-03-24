import pytest
from bot.utils.validators import extract_url, sanitize_caption

class TestExtractUrl:
    def test_x_com_status_url(self):
        assert extract_url("https://x.com/user/status/1234567890") == "https://x.com/user/status/1234567890"
    def test_twitter_com_status_url(self):
        assert extract_url("https://twitter.com/user/status/1234567890") == "https://twitter.com/user/status/1234567890"
    def test_youtube_url(self):
        assert extract_url("https://youtube.com/watch?v=abc") == "https://youtube.com/watch?v=abc"
    def test_tiktok_url(self):
        assert extract_url("https://www.tiktok.com/@user/video/123") == "https://www.tiktok.com/@user/video/123"
    def test_instagram_url(self):
        assert extract_url("https://www.instagram.com/reel/abc123/") == "https://www.instagram.com/reel/abc123/"
    def test_t_co_short_link(self):
        assert extract_url("https://t.co/abc123") == "https://t.co/abc123"
    def test_url_in_text(self):
        assert extract_url("check this https://example.com/video ok") == "https://example.com/video"
    def test_plain_text(self):
        assert extract_url("hello world") is None
    def test_empty_string(self):
        assert extract_url("") is None

class TestSanitizeCaption:
    def test_allowed_tags_preserved(self):
        html = "<b>bold</b> <i>italic</i> <u>underline</u>"
        result, error = sanitize_caption(html)
        assert "<b>bold</b>" in result
        assert "<i>italic</i>" in result
        assert error is None
    def test_disallowed_tags_stripped(self):
        html = "<div>text</div><script>alert(1)</script>"
        result, error = sanitize_caption(html)
        assert "<div>" not in result
        assert "<script>" not in result
        assert "text" in result
        assert error is None
    def test_bare_ampersand_escaped(self):
        html = "A & B"
        result, error = sanitize_caption(html)
        assert "&amp;" in result
        assert error is None
    def test_bare_angle_brackets_escaped(self):
        html = "1 < 2 > 0"
        result, error = sanitize_caption(html)
        assert "&lt;" in result
        assert "&gt;" in result
        assert error is None
    def test_a_tag_with_href_preserved(self):
        html = '<a href="https://example.com">link</a>'
        result, error = sanitize_caption(html)
        assert 'href="https://example.com"' in result
        assert error is None
    def test_caption_at_limit(self):
        text = "a" * 1024
        result, error = sanitize_caption(text)
        assert error is None
    def test_caption_over_limit(self):
        text = "a" * 1025
        result, error = sanitize_caption(text)
        assert error is not None
        assert "1025" in error
        assert "1024" in error
    def test_tags_not_counted_in_length(self):
        html = "<b>" + "a" * 1024 + "</b>"
        result, error = sanitize_caption(html)
        assert error is None
    def test_code_and_pre_preserved(self):
        html = "<code>x=1</code> <pre>block</pre>"
        result, error = sanitize_caption(html)
        assert "<code>x=1</code>" in result
        assert "<pre>block</pre>" in result
        assert error is None
    def test_s_tag_preserved(self):
        html = "<s>strikethrough</s>"
        result, error = sanitize_caption(html)
        assert "<s>strikethrough</s>" in result
        assert error is None

    def test_entity_ref_counted_as_one_char(self):
        # &amp; renders as 1 char, so 1023 + 1 = 1024 (at limit)
        html = "a" * 1023 + "&amp;"
        result, error = sanitize_caption(html)
        assert error is None

    def test_char_ref_counted_as_one_char(self):
        # &#60; renders as 1 char (<), so 1023 + 1 = 1024
        html = "a" * 1023 + "&#60;"
        result, error = sanitize_caption(html)
        assert error is None

    def test_entity_over_limit(self):
        # 1024 + 1 rendered char = over limit
        html = "a" * 1024 + "&amp;"
        result, error = sanitize_caption(html)
        assert error is not None
        assert "1025" in error

    def test_entity_preserved_in_output(self):
        result, error = sanitize_caption("&amp;")
        assert "&amp;" in result
        assert error is None
