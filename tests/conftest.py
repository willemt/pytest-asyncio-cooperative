from typing import List


pytest_plugins = ["pytester"]


def includes_lines(expected_lines: List[str], lines: List[str]) -> bool:
    for line in lines:
        for i, eline in enumerate(list(expected_lines)):
            if eline == line:
                expected_lines.pop(i)
                break

    assert expected_lines == []
    return expected_lines == []


def includes_lines_in_order(expected_lines: List[str], lines: List[str]) -> bool:
    try:
        for line in lines:
            if expected_lines[0] == line:
                expected_lines.pop(0)
    except IndexError:
        pass

    assert expected_lines == []
    return expected_lines == []
