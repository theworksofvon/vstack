import check

FRAME = 1 / 30


def trace(levels):
    return [(i * FRAME, level) for i, level in enumerate(levels)]


def test_more_than_3_flashes_in_1_second_is_a_strobe():
    assert check.strobes(trace([200, 20] * 5 + [200] * 30)) == [FRAME]


def test_3_flashes_in_1_second_pass():
    assert check.strobes(trace([200, 20] * 3 + [200] * 30)) == []


def test_black_between_2_bright_pages_is_a_cut_through_black():
    assert check.dips(trace([200, 200, 0, 0, 200, 200])) == [2 * FRAME]


def test_a_fade_from_a_dark_page_is_not():
    assert check.dips(trace([60, 60, 0, 0, 200, 200])) == []


def test_sound_and_picture_of_different_length_fail():
    found = check.faults({"video": [10.0], "audio": [10.5]}, [], [], -18.0)

    assert found == ["picture is 10.00 s and sound is 10.50 s"]
