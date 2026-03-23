import pytest
from bot.utils.validators import is_x_video_url, sanitize_caption

class TestIsXVideoUrl:
    def test_x_com_status_url(self):
        assert is_x_video_url("https://x.com/user/status/1234567890") is True
    def test_twitter_com_status_url(self):
        assert is_x_video_url("https://twitter.com/user/status/1234567890") is True
    def test_x_com_with_query_params(self):
        assert is_x_video_url("https://x.com/user/status/123?s=20") is True
    def test_t_co_short_link(self):
        assert is_x_video_url("https://t.co/abc123") is True
    def test_invalid_url(self):
        assert is_x_video_url("https://youtube.com/watch?v=abc") is False
    def test_plain_text(self):
        assert is_x_video_url("hello world") is False
    def test_empty_string(self):
        assert is_x_video_url("") is False
    def test_x_com_without_status(self):
        assert is_x_video_url("https://x.com/user") is False

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
