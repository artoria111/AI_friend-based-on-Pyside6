@echo off
echo 正在切换工作目录...
cd /d D:\MyProgram\AI_friend

echo 正在激活虚拟环境...
call .venv\Scripts\activate.bat

echo 正在启动 AI friend...
python main.py

pause