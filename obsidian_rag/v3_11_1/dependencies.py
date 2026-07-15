from obsidian_rag.config import load_config
from obsidian_rag.v3_11_1.service import DoclingLearningService


def get_docling_service() -> DoclingLearningService:
    return DoclingLearningService(load_config())
