# -*- coding: utf-8 -*-
"""
快捷启动脚本

在项目根目录执行：
  python run.py

服务的监听地址和端口由 .env 文件（或环境变量）中的
APP_HOST / APP_PORT 决定，默认值为 0.0.0.0:9002。
"""

from app.main import start

if __name__ == "__main__":
    print("正在启动 Short Drama Server，监听地址和端口由 .env 文件（或环境变量）中的 APP_HOST / APP_PORT 决定，默认值为")
    start()
