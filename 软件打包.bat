@echo off
chcp 65001 >nul
title 打包前端程序 3.8.1
setlocal enabledelayedexpansion

:: 获取脚本所在目录，并切换到该目录
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
echo 当前目录：%CD%

:: 检查主程序文件是否存在
set "MAIN_FILE=main_3.14.py"
if not exist "%MAIN_FILE%" (
    echo ❌ 错误：找不到 %MAIN_FILE%！
    echo 请确保该文件与打包脚本在同一目录。
    echo 当前目录下的 .py 文件有：
    dir *.py /b
    pause
    exit /b 1
)

echo ✅ 找到主程序文件：%MAIN_FILE%

:: 可选：激活虚拟环境（如果使用）
if exist ".venv\Scripts\activate.bat" (
    echo 激活虚拟环境...
    call .venv\Scripts\activate.bat
)

:: 安装 PyInstaller（如果没有）
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 安装 PyInstaller...
    pip install pyinstaller
)

:: 清理旧构建
echo 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /f /q *.spec

:: 执行打包
echo 开始打包...
pyinstaller --onefile --windowed ^
  --name "木子的PDF转换器_4.0" ^
  --icon "my_icon.ico" ^
  --add-data "my_icon.ico;." ^
  --hidden-import pdf2docx ^
  --hidden-import PyPDF2 ^
  --hidden-import queue ^
  --hidden-import urllib.parse ^
  --collect-submodules pdf2docx ^
  --collect-submodules PyPDF2 ^
  "%MAIN_FILE%"

:: 检查打包结果
if errorlevel 1 (
    echo ❌ 打包失败，请查看上方错误信息。
    pause
    exit /b 1
) else (
    echo ✅ 打包成功！exe 位于 dist 目录：
    dir dist\*.exe
    pause
)