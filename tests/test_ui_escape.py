"""UI escaping tests: untrusted text is HTML-escaped before unsafe_allow_html.

These tests import ui.app only (streamlit, pandas, altair, requests are
installed); they do not touch the FastAPI app.
"""
from ui.app import _esc


def test_html_escapes_xss_payload():
    payload = '<img src=x onerror=alert(1)>'
    assert _esc(payload) == (
        "&lt;img src=x onerror=alert(1)&gt;"
    )


def test_html_escapes_script_and_quotes():
    payload = '<script>evil()</script> & "quoted"'
    assert _esc(payload) == (
        "&lt;script&gt;evil()&lt;/script&gt; &amp; &quot;quoted&quot;"
    )


def test_html_escapes_none_and_empty():
    assert _esc(None) == ""
    assert _esc("") == ""
    assert _esc(42) == "42"
