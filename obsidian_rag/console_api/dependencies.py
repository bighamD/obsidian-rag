from functools import lru_cache

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.core.mysql_memory import MySQLConversationMemoryStore


def get_console_config() -> RagConfig:
    return load_config()


@lru_cache(maxsize=1)
def get_console_memory_store() -> MySQLConversationMemoryStore:
    return MySQLConversationMemoryStore()
