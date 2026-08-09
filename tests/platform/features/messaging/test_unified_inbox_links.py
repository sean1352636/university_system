from education_system.platform.features.messaging.unified_inbox import _message_segments


def test_message_segments_hides_markdown_url_behind_clickable_label():
    body = "Before [Press here](https://example.test/reset?token=abc) after"

    assert list(_message_segments(body)) == [
        ("text", "Before ", None),
        ("link", "Press here", "https://example.test/reset?token=abc"),
        ("text", " after", None),
    ]


def test_message_segments_does_not_activate_non_http_links():
    body = "[Open](javascript:alert(1))"

    assert list(_message_segments(body)) == [("text", body, None)]
