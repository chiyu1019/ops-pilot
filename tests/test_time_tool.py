"""时间工具单元测试"""

import re

from app.tools.time_tool import get_current_time


def test_get_current_time_format():
    result = get_current_time.invoke({})
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", result)


def test_get_current_time_bad_timezone_returns_error():
    result = get_current_time.invoke({"timezone": "Not/AZone"})
    assert "失败" in result
