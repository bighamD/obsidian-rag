from obsidian_rag.debugging import is_debug_breakpoint_enabled


def test_debug_breakpoint_enabled_for_all():
    assert is_debug_breakpoint_enabled("ask.after_retrieval", "all")


def test_debug_breakpoint_enabled_for_named_stage():
    assert is_debug_breakpoint_enabled("ask.after_retrieval", "ingest.after_chunks, ask.after_retrieval")


def test_debug_breakpoint_disabled_when_name_is_missing():
    assert not is_debug_breakpoint_enabled("ask.after_retrieval", "ingest.after_chunks")


def test_debug_breakpoint_disabled_when_setting_is_empty():
    assert not is_debug_breakpoint_enabled("ask.after_retrieval", "")
