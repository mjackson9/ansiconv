from ansiconv.cli import main


def test_to_html_reads_file_and_writes_output(tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("\x1b[32mok\x1b[0m")
    out = tmp_path / "out.html"

    exit_code = main(["to-html", str(src), "-o", str(out)])

    assert exit_code == 0
    assert out.read_text() == '<span class="ansi-fg-green">ok</span>\n'


def test_strict_mode_reports_error_and_mentions_lenient_flag(tmp_path, capsys):
    src = tmp_path / "in.txt"
    src.write_text("\x1b[5mx\x1b[0m")

    exit_code = main(["to-html", str(src)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "lenient" in captured.err


def test_lenient_flag_recovers_from_unsupported_codes(tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("\x1b[5mx\x1b[0m")
    out = tmp_path / "out.html"

    exit_code = main(["to-html", str(src), "-o", str(out), "--lenient"])

    assert exit_code == 0
    assert out.read_text() == "x\n"


def test_to_ansi_round_trips_through_html(tmp_path):
    src = tmp_path / "in.html"
    src.write_text('<span class="ansi-bold ansi-fg-red">ERROR</span>: build failed')
    out = tmp_path / "out.txt"

    exit_code = main(["to-ansi", str(src), "-o", str(out)])

    assert exit_code == 0
    assert out.read_text() == "\x1b[0;1;31mERROR\x1b[0m: build failed\x1b[0m\n"
