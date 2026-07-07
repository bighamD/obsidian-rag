from obsidian_rag.cli import _print_sources


def test_print_sources_skips_empty_sources(capsys):
    _print_sources([])

    assert capsys.readouterr().out == ""


def test_print_sources_prints_deduplicated_sources(capsys):
    _print_sources(["a.md", "b.md"])

    assert capsys.readouterr().out == "\nSources:\n- a.md\n- b.md\n"
