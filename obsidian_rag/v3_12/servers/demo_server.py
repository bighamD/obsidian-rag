from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


mcp = FastMCP(
    "obsidian-rag-v3.12-demo",
    instructions="提供低风险、只读、确定性的 MCP 学习工具。",
    log_level="ERROR",
)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True), structured_output=True)
def lookup_food_temperature(food: str) -> dict[str, Any]:
    """查询常见食品建议的最低中心温度，单位为摄氏度。"""

    normalized = food.strip().lower()
    temperatures = {
        "chicken": (74, "鸡肉和其他禽肉"),
        "turkey": (74, "火鸡和其他禽肉"),
        "ground_meat": (71, "碎牛肉、碎猪肉等绞肉"),
        "fish": (63, "鱼类"),
        "leftovers": (74, "剩菜再次加热"),
    }
    matched = temperatures.get(normalized)
    if matched is None:
        return {
            "found": False,
            "food": food,
            "supported_foods": sorted(temperatures),
        }
    temperature_c, label = matched
    return {
        "found": True,
        "food": normalized,
        "label": label,
        "minimum_internal_temperature_c": temperature_c,
        "note": "学习示例；实际操作应以适用地区的权威食品安全指南为准。",
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True), structured_output=True)
def get_server_time(timezone: str = "Asia/Shanghai") -> dict[str, Any]:
    """返回指定 IANA 时区的当前时间。"""

    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"未知 IANA timezone: {timezone}") from exc
    now = datetime.now(zone)
    return {"timezone": timezone, "iso_time": now.isoformat()}


if __name__ == "__main__":
    mcp.run(transport="stdio")
