@echo off
rem Runs frameledger by name, so `frameledger report run.csv` works once
rem this file's folder is on PATH. In the release it sits beside
rem frameledger.pyz and runs that. In a source checkout it sits in
rem launcher\ and runs src\frameledger, the same modules unbundled.
rem
rem The py launcher is used where it is installed: it picks the newest
rem Python 3. Otherwise python on PATH. Exit 9009 means no real Python
rem was found: often `python` is only the Microsoft Store's stand-in.
rem
rem This file needs CRLF line endings, or goto may miss its label: the
rem release ships it so, and .gitattributes checks it out so.
rem No ( ) blocks: %* is expanded when a block is read, so an argument
rem holding a ")", such as a path under "Program Files (x86)", would end
rem the block early.
setlocal
set "analyser=%~dp0frameledger.pyz"
if not exist "%analyser%" set "analyser=%~dp0..\src\frameledger"
where py >nul 2>nul && goto py
python -I "%analyser%" %*
exit /b %errorlevel%
:py
py -3 -I "%analyser%" %*
exit /b %errorlevel%
