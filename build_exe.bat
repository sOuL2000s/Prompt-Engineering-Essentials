@echo off
echo ====================================================
echo STEP 1: Creating Virtual Environment...
echo ====================================================
python -m venv venv

echo.
echo ====================================================
echo STEP 2: Installing Dependencies (pathspec, pyinstaller)...
echo ====================================================
call venv\Scripts\activate
pip install pathspec pyinstaller

echo.
echo ====================================================
echo STEP 3: Building Standalone Executable...
echo ====================================================
:: --noconsole hides the black terminal box
:: --onefile bundles everything into one .exe
:: --clean clears temporary cache
pyinstaller --noconsole --onefile --clean project_combiner.py

echo.
echo ====================================================
echo DONE! 
echo Your standalone file is in the "dist" folder.
echo ====================================================
pause
