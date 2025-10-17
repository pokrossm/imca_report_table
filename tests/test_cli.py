from __future__ import annotations

import pytest

from imca_report_table import __version__
from imca_report_table.__main__ import parse_args


def test_version_flag_outputs_version_and_exits(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out
