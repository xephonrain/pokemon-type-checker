@echo off
cd /d "%~dp0"

echo Step 1/5: pokemon_base.json
python collect_pokemon_base.py
if errorlevel 1 ( echo ERROR: Step1 failed & pause & exit /b 1 )

echo Step 2/5: pokemon_moves.json
python collect_pokemon_moves.py
if errorlevel 1 ( echo ERROR: Step2 failed & pause & exit /b 1 )

echo Step 3/5: move_db.json
python collect_move_db.py
if errorlevel 1 ( echo ERROR: Step3 failed & pause & exit /b 1 )

echo Step 4/5: pokemon_usage.json
python collect_pokemon_usage.py
if errorlevel 1 ( echo ERROR: Step4 failed & pause & exit /b 1 )

echo Step 5/5: pokemon_db_output.txt
python build_db.py
if errorlevel 1 ( echo ERROR: Step5 failed & pause & exit /b 1 )

echo Done.
pause
