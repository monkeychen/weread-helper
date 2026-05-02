from weread.utils import sanitize_filename


def test_sanitize_normal_name():
    assert sanitize_filename("认知觉醒") == "认知觉醒"


def test_sanitize_strips_illegal_chars():
    assert sanitize_filename('认知/觉醒:第一版') == "认知_觉醒_第一版"


def test_sanitize_strips_whitespace():
    assert sanitize_filename("  认知觉醒  ") == "认知觉醒"


def test_sanitize_collapses_underscores():
    assert sanitize_filename("a///b") == "a_b"


def test_sanitize_empty_string():
    assert sanitize_filename("") == "untitled"


def test_sanitize_only_illegal_chars():
    assert sanitize_filename("///") == "untitled"
