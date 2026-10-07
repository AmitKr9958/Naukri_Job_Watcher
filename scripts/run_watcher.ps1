Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH=(Get-Location).Path+'\src'
python .\src\main.py
