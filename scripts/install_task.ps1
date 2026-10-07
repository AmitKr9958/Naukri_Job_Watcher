$root=Split-Path $PSScriptRoot -Parent
$python=Join-Path $root '.venv\Scripts\python.exe'
$task='Naukri Job Watcher'
$action=New-ScheduledTaskAction -Execute $python -Argument '"'+(Join-Path $root 'src\main.py')+'"' -WorkingDirectory $root
$trigger=New-ScheduledTaskTrigger -AtLogOn
$settings=New-ScheduledTaskSettingsSet -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 5) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
Write-Host "Installed: $task"
