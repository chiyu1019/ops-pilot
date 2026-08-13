"""pytest 全局配置：Windows 下使用 SelectorEventLoop（psycopg 异步要求）"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
