@echo off
chcp 65001 >nul
title 打包后端控制面板
set CURRENT_DIR=%~dp0
cd /d "%CURRENT_DIR%"

echo 安装 PyInstaller...
pip install pyinstaller

echo 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /f /q *.spec

echo 开始打包后端...
pyinstaller --onefile ^
  --name "MinerU-Control" ^
  --add-data "templates;templates" ^
  --add-data "my_icon.ico;." ^
  --hidden-import flask ^
  --hidden-import plotly ^
  --hidden-import pandas ^
  --hidden-import psutil ^
  --hidden-import watchdog ^
  --hidden-import pynvml ^
  --collect-submodules flask ^
  app.py

echo 打包完成！exe 位于 dist 目录
pause