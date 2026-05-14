@echo off
REM 切换到当前批处理文件所在目录（确保路径正确）
cd /d "%~dp0"

REM 激活 Conda 环境（如果环境变量已配置，直接激活）
call conda activate zt2025

REM 检查环境是否激活成功
if errorlevel 1 (
    echo 错误：Conda 环境 zt2025 激活失败！
    echo 可能原因：
    echo 1. 环境名称错误（当前环境列表：conda env list）
    echo 2. Conda 未添加到系统 PATH 环境变量
    pause
    exit /b
)

REM 运行 Python 脚本
python main.py

REM 执行完毕后保持窗口不关闭
pause