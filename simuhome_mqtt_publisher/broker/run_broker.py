"""常驻运行 amqtt broker：读同目录 broker.yaml，Ctrl+C 优雅退出。"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
from pathlib import Path

import yaml
from amqtt.broker import Broker


CONFIG_PATH = Path(__file__).with_name("broker.yaml")
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def load_config(path: Path) -> dict:
    """读取并解析 broker 配置。"""

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def setup_logging() -> None:
    """日志同时写控制台与文件，文件按大小滚动，重启不覆盖历史。"""

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "broker.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handlers.append(file_handler)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


async def serve(config: dict) -> None:
    """启动 broker 并一直运行，收到中断后关闭。"""

    broker = Broker(config)
    await broker.start()
    logging.getLogger("amqtt").info("broker 已启动，监听 %s", config["listeners"]["default"]["bind"])
    stop = asyncio.Event()
    try:
        loop = asyncio.get_running_loop()
        for sig in (getattr(__import__("signal"), "SIGINT", None), getattr(__import__("signal"), "SIGTERM", None)):
            if sig is not None:
                try:
                    loop.add_signal_handler(sig, stop.set)
                except NotImplementedError:  # Windows 上部分信号不支持
                    pass
        await stop.wait()
    except asyncio.CancelledError:
        pass
    finally:
        await broker.shutdown()
        logging.getLogger("amqtt").info("broker 已关闭")


def main() -> None:
    """入口：配置日志并跑事件循环。"""

    setup_logging()
    config = load_config(CONFIG_PATH)
    try:
        asyncio.run(serve(config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
