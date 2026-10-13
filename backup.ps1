# Convenience PowerShell wrapper for Garmin Backup
param (
    [string]$Source = "",
    [string]$Destination = "$HOME\GarminBackups",
    [switch]$Zip,
    [switch]$Full
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "garmin_backup.py"

$ArgsList = @()
if ($Source) { $ArgsList += "-s", $Source }
if ($Destination) { $ArgsList += "-d", $Destination }
if ($Zip) { $ArgsList += "--zip" }
if ($Full) { $ArgsList += "--full" }

Write-Host "Running Garmin Backup..." -ForegroundColor Cyan
python $PythonScript @ArgsList
