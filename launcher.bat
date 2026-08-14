::[Bat To Exe Converter]
::
::YAwzoRdxOk+EWAjk
::fBw5plQjdCmDJNZYHBq/9PJwSReJKGSqOpMV5O3o0/mEsEQNQN0vdJrc07qyJO8E5EnrdJIS2WhdmcUFFh5KQhakeQE4pm9GiWuXMMaSuhXkWAaA5URQ
::YAwzuBVtJxjWCl3EqQJgSA==
::ZR4luwNxJguZRRnk
::Yhs/ulQjdF+5
::cxAkpRVqdFKZSDk=
::cBs/ulQjdF+5
::ZR41oxFsdFKZSDk=
::eBoioBt6dFKZSDk=
::cRo6pxp7LAbNWATEpCI=
::egkzugNsPRvcWATEpCI=
::dAsiuh18IRvcCxnZtBJQ
::cRYluBh/LU+EWAnk
::YxY4rhs+aU+JeA==
::cxY6rQJ7JhzQF1fEqQJQ
::ZQ05rAF9IBncCkqN+0xwdVs0
::ZQ05rAF9IAHYFVzEqQJQ
::eg0/rx1wNQPfEVWB+kM9LVsJDGQ=
::fBEirQZwNQPfEVWB+kM9LVsJDGQ=
::cRolqwZ3JBvQF1fEqQJQ
::dhA7uBVwLU+EWDk=
::YQ03rBFzNR3SWATElA==
::dhAmsQZ3MwfNWATElA==
::ZQ0/vhVqMQ3MEVWAtB9wSA==
::Zg8zqx1/OA3MEVWAtB9wSA==
::dhA7pRFwIByZRRnk
::Zh4grVQjdCmDJNZYHBq/9PJwSReJKGSqOpMV5O3o0/mEsEQNQN0vdJrc07qyJO8E5EnrdJIS2WhdmcUFFh5KQh6qewE3oWtQ+GGdMqc=
::YB416Ek+ZG8=
::
::
::978f952a14a936cc963da21a135fa983
@echo off
title Download Organizer Tool v3.0

cd /d "%~dp0"

echo ============================================
echo   Download Folder Organizer v3.0
echo ============================================
echo.
echo Starting, please wait...
echo.

python gui.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start! Error code: %errorlevel%
    echo.
    pause
)
