from custom_components.envoy_web import api


def test_browser_header_template_includes_expected_fields() -> None:
    headers = api._browser_header_template(fetch_site="none")

    assert headers["user-agent"] == api._LOGIN_UA
    assert headers["sec-fetch-site"] == "none"
    assert headers["sec-fetch-mode"] == "navigate"
    assert headers["sec-fetch-dest"] == "document"
    assert headers["accept"].startswith("text/html")
    assert headers["accept-language"].startswith("en-US")


def test_browser_header_template_excludes_request_context_headers() -> None:
    headers = api._browser_header_template(fetch_site="same-origin")

    assert "origin" not in headers
    assert "referer" not in headers
    assert "content-type" not in headers
    assert "sec-ch-ua" not in headers
    assert "upgrade-insecure-requests" not in headers
