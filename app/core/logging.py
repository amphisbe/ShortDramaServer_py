import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """初始化应用日志。

    后续所有入口统一调用该函数，避免各模块重复配置日志。生产环境可在此扩展为 JSON 日志、
    文件日志或接入 ELK、Loki 等集中式日志系统。
    """

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
