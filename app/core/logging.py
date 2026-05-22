import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(level: str = "INFO") -> None:
    """初始化应用日志：控制台（stdout）+ 文件轮转（logs/drama.log）。

    控制台 Handler 直接输出到 stdout；文件 Handler 按大小轮转（10 MB × 5 个备份），
    日志目录自动创建。该函数只应被调用一次（在应用入口或 lifespan 中）。
    """

    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "drama.log")

    log_level = getattr(logging, level.upper(), logging.INFO)
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler],
        force=True,
    )

    logging.getLogger(__name__).info(
        "日志系统已初始化，日志文件：%s，级别：%s",
        log_file,
        level.upper(),
    )
