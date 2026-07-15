from obsidian_rag.config import load_config
from obsidian_rag.v3_11_2.service import FrameworkComparisonService


def get_framework_comparison_service() -> FrameworkComparisonService:
    return FrameworkComparisonService(load_config())
