@echo off
rem Runs frameledger.pyz from the folder this file is in, so
rem `frameledger report run.csv` works once that folder is on PATH.
rem
rem The py launcher is used where it is installed: it picks the newest
rem Python 3. Otherwise python on PATH. The release ships this file with
rem CRLF line endings, which cmd needs for goto to find its label.
rem No ( ) blocks: %* is expanded when a block is read, so an argument
rem holding a ")", such as a path under "Program Files (x86)", would end
rem the block early.
setlocal
where py >nul 2>nul && goto py
python -I "%~dp0frameledger.pyz" %*
exit /b %errorlevel%
:py
py -3 -I "%~dp0frameledger.pyz" %*
exit /b %errorlevel%
