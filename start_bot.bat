@echo off
chcp 65001 >nul
title Запуск Arus Chess AI
color 0A

echo ====================================================
echo              ARUS CHESS AI - ЗАПУСК
echo ====================================================
echo.

:: Проверка наличия Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ОШИБКА: Python не установлен!
    echo Скачай его с https://www.python.org/downloads/
    echo При установке ОБЯЗАТЕЛЬНО поставь галочку "Add Python to PATH"
    echo.
    pause
    exit
)

echo [*] Python найден. Проверка библиотек...
echo.

:: Проверка и установка библиотек
echo [*] Проверяю pyTelegramBotAPI...
python -c "import chess" >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] Библиотека python-chess не найдена. Устанавливаю...
    python -m pip install chess
) else (
    echo [+] python-chess уже установлена.
)

python -c "import chess.engine" >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] Библиотека python-chess.engine не найдена. Устанавливаю...
    python -m pip install chess
)

python -c "import selenium" >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] Библиотека Selenium не найдена. Устанавливаю...
    python -m pip install selenium
) else (
    echo [+] Selenium уже установлена.
)

python -c "import webdriver_manager" >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] Библиотека webdriver-manager не найдена. Устанавливаю...
    python -m pip install webdriver-manager
) else (
    echo [+] webdriver-manager уже установлена.
)

python -c "import tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ВНИМАНИЕ: Tkinter не найден.
    echo Если ты ставил Python с официального сайта, попробуй переустановить его,
    echo поставив галочку "tcl/tk and IDLE".
)

echo.
echo ====================================================
echo   Все библиотеки готовы. Запускаю Arus Chess AI...
echo ====================================================
echo.

:: Запуск самого бота
python Arus_Chess_AI.py

:: Если бот закрылся с ошибкой, окно не закроется, чтобы ты увидел лог
echo.
echo [*] Бот закрыт. Нажми любую клавишу для выхода...
pause >nul