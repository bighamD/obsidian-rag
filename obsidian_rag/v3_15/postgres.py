from __future__ import annotations

import getpass
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class PostgresStateSettings:
    """V3.15 Checkpoint 与 HITL Runtime 共用的 PostgreSQL 配置。"""

    dsn: str
    schema: str = "public"
    pool_min_size: int = 1
    pool_max_size: int = 8
    pool_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.schema):
            raise ValueError("RAG_V3_15_POSTGRES_SCHEMA 必须是合法的 PostgreSQL identifier。")
        if self.pool_min_size < 1 or self.pool_max_size < self.pool_min_size:
            raise ValueError("PostgreSQL pool size 必须满足 1 <= min_size <= max_size。")
        if self.pool_timeout_seconds <= 0:
            raise ValueError("PostgreSQL pool timeout 必须大于 0。")

    @classmethod
    def from_env(cls) -> "PostgresStateSettings":
        load_dotenv()
        default_dsn = (
            f"postgresql://{getpass.getuser()}@127.0.0.1:5432/obsidian_rag_v315"
        )
        return cls(
            dsn=os.getenv("RAG_V3_15_POSTGRES_DSN", default_dsn),
            schema=os.getenv("RAG_V3_15_POSTGRES_SCHEMA", "public"),
            pool_min_size=int(os.getenv("RAG_V3_15_POSTGRES_POOL_MIN_SIZE", "1")),
            pool_max_size=int(os.getenv("RAG_V3_15_POSTGRES_POOL_MAX_SIZE", "8")),
            pool_timeout_seconds=float(os.getenv("RAG_V3_15_POSTGRES_POOL_TIMEOUT_SECONDS", "10")),
        )

    def display_location(self) -> str:
        """返回不包含密码的连接位置，供 Swagger 和日志观察。"""

        values = conninfo_to_dict(self.dsn)
        user = values.get("user") or getpass.getuser()
        host = values.get("host") or "127.0.0.1"
        port = values.get("port") or "5432"
        database = values.get("dbname") or values.get("database") or "postgres"
        return f"postgresql://{user}@{host}:{port}/{database}"

    @property
    def database(self) -> str:
        values = conninfo_to_dict(self.dsn)
        return str(values.get("dbname") or values.get("database") or "postgres")


def create_postgres_pool(settings: PostgresStateSettings) -> ConnectionPool:
    """创建线程安全连接池；PostgresSaver 要求 autocommit 与 prepare_threshold=0。"""

    pool = ConnectionPool(
        conninfo=settings.dsn,
        min_size=max(1, settings.pool_min_size),
        max_size=settings.pool_max_size,
        timeout=settings.pool_timeout_seconds,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": f"-c search_path={settings.schema}",
        },
        name="obsidian-rag-v3-15",
        open=False,
    )
    pool.open(wait=True, timeout=settings.pool_timeout_seconds)
    return pool
