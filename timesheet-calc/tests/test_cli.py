import pytest

from timesheet_calc.cli import EXIT_OK, EXIT_USAGE, main


def test_calc_page_example(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["calc", "7:45-11", "12:10-3", "4-4:30"]) == EXIT_OK
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        " 7:45 -> 11:00  3:15",
        "12:10 ->  3:00  2:50",
        " 4:00 ->  4:30  0:30",
        "         Total  6:35",
    ]


def test_calc_strict_decimal(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["calc", "2200-0600", "--mode", "strict", "--decimal"]) == EXIT_OK
    assert capsys.readouterr().out.splitlines()[-1] == "         Total  8:00 (8.00 h)"


def test_sum(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["sum", "6:35", "8:15", "26:15", "--decimal"]) == EXIT_OK
    assert capsys.readouterr().out == "Total  41:05 (41.08 h)\n"


@pytest.mark.parametrize("argv", [["calc", "6-6"], ["calc", "7:60-8"], ["sum", "abc"]])
def test_bad_input_exits_usage(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv) == EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("timesheet: error:")


def test_missing_subcommand_exits_usage() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == EXIT_USAGE
