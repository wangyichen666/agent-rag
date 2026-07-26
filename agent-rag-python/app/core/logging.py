"""日志初始化：结构化单行格式，便于采集。"""
import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # 压低三方库噪音
    for noisy in ("httpx", "httpcore", "pymilvus", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
