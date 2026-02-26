@echo off
chcp 65001 >nul
title 安装后端依赖
:: 切换到脚本所在目录
cd /d "%~dp0"
echo 当前目录：%CD%

:: 检查 requirements.txt 是否存在
if not exist "requirements.txt" (
    echo ❌ 错误：在当前目录下未找到 requirements.txt 文件！
    echo 请确保该文件与批处理脚本放在同一目录。
    pause
    exit /b 1
)

:: 检查 Python 是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未找到，请安装 Python 3.8 并添加到 PATH。
    pause
    exit /b 1
)

:: 升级 pip（重要，因为你的 pip 版本 19.2.3 太旧）
echo 正在升级 pip...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 安装依赖库（使用清华镜像加速）
echo 正在安装依赖库...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if errorlevel 1 (
    echo ❌ 依赖安装失败，请检查网络或手动执行：pip install -r requirements.txt
) else (
    echo ✅ 所有依赖安装成功！
)

pause