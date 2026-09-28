"""Retained comments must survive parsing and remain usable by loaders."""
from io import StringIO

import pytest

from shef.loaders.shared import make_shef_value
from shef.shef_parser import ShefParser


@pytest.mark.parametrize("comment", ['"5:KSMN"', "'5:KSMN'", '"15:OKMN"'])
def test_colon_in_retained_comment_reaches_loader(comment):
    parser = ShefParser(1, reject_problematic=True)
    parser.set_input(StringIO(
        f'.A EDCK1 20260928 C DH1625\n.A00 TACRRZZ 82.99Z{comment}\n'
    ))
    parser.get_next_message()
    records = parser.parse_message()
    assert len(records) == 1
    value = make_shef_value(records[0].format(ShefParser.OutputRecord.SHEFIT_TEXT_V1))
    assert value.location == "EDCK1"
    assert value.parameter_code == "TACRRZZ"
    assert value.value == 82.99
    assert value.obs_time == "21:25:00"
    assert value.comment == comment[1:-1]


@pytest.mark.parametrize("comment", ["", " ", "5:KSMN"])
def test_loader_accepts_empty_and_nonempty_format_1_comments(comment):
    line = (
        'EDCK1     2026-09-28 21:25:00  0000-00-00 00:00:00  '
        'TACRRZZ        82.9900 Z   -1.000  0015 0 0            '
        f'"{comment}"'
    )
    value = make_shef_value(line)
    assert value.value == 82.99
    assert value.comment == comment.strip()


@pytest.mark.parametrize(("line", "expected"), [
    ('TA 82.99 :discard me: / XR 47.66', 'TA 82.99  / XR 47.66'),
    ('TA 82.99 :discard "quoted text": / XR 47.66', 'TA 82.99  / XR 47.66'),
    ('TA 82.99 "5:KSMN" :discard: / XR 47.66', 'TA 82.99 "5:KSMN"  / XR 47.66'),
    ("TA 82.99 'a:b' :discard to end", "TA 82.99 'a:b' "),
    ('TA 82.99 "station\'s:note"', 'TA 82.99 "station\'s:note"'),
])
def test_unretained_comments_still_removed(line, expected):
    assert ShefParser(1).remove_comment_fields(line) == expected
