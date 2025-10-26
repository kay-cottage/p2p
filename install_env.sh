#!/bin/bash
# ============================================
# Ubuntu 一键安装 Python 3.9 + 常用第三方库
# 作者: Kyle Ward
# 用法: sudo bash install_env.sh
# ============================================

set -e

echo "🚀 正在更新系统..."
sudo apt update -y && sudo apt upgrade -y

echo "🐍 安装 Python 3.9 及依赖..."
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update -y
sudo apt install -y python3.9 python3.9-venv python3.9-dev python3.9-distutils curl build-essential

echo "⚙️ 设置默认 python3 指向 Python3.9..."
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1

echo "📦 安装 pip..."
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.9
pip3 install --upgrade pip setuptools wheel

echo "✅ Python & pip 安装完成:"
python3 --version
pip3 --version

echo "🧰 开始安装常用 Python 库..."
pip3 install -U \
aiohttp \
beautifulsoup4 \
requests \
openai \
flask \
flask-cors \
numpy \
seaborn \
tqdm \
rich \
uvicorn \
fastapi \
PyYAML \
playwright \
openpyxl \
pyecharts \
pytest

echo "⚙️ 安装 Playwright 浏览器依赖..."
python3 -m playwright install --with-deps

echo "🎉 环境安装完成！"
echo "✅ 已安装 Python 版本：$(python3 --version)"
echo "✅ 已安装 pip 版本：$(pip3 --version)"
echo "✅ 常用库示例："
pip3 list | grep -E "flask|openai|numpy|torch|requests|fastapi"

echo "✅ 完成：你现在可以开始 Python 开发啦！"
