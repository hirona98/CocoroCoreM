@echo off
chcp 65001 > nul
echo CocoroCore2 Build Tool

REM Activate virtual environment
echo Activating virtual environment...
call .\.venv\Scripts\activate

REM Check Python version
python -c "import sys; print(f'Python {sys.version}')"

REM Execute build script with UTF-8 mode
echo Running build script...
python -X utf8 build_cocoro2.py

REM Deactivate virtual environment
call deactivate

echo.
echo Build process completed. Press any key to exit.
pause > nul