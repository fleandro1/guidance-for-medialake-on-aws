# Install script for Media Lake DaVinci Resolve Plugin on Windows
# Run this script in PowerShell as Administrator

param(
    [switch]$SkipVenv,
    [switch]$SkipFFmpeg,
    [switch]$CreateShortcut
)

$ErrorActionPreference = "Stop"

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Media Lake Resolve Plugin Installer" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Host "Project directory: $ProjectDir"
Write-Host ""

# Check for Python 3.10+
function Test-PythonVersion {
    try {
        $pythonVersion = & python --version 2>&1
        if ($pythonVersion -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 10) {
                Write-Host "✓ $pythonVersion found" -ForegroundColor Green
                return $true
            }
        }
    } catch {}
    
    Write-Host "✗ Python 3.10 or higher is required" -ForegroundColor Red
    Write-Host "  Please install Python from https://www.python.org/downloads/"
    exit 1
}

Test-PythonVersion

# Create virtual environment
$VenvDir = Join-Path $ProjectDir "venv"

if (-not $SkipVenv) {
    if (Test-Path $VenvDir) {
        Write-Host "Virtual environment already exists"
        $recreate = Read-Host "Do you want to recreate it? (y/N)"
        if ($recreate -eq "y" -or $recreate -eq "Y") {
            Remove-Item -Recurse -Force $VenvDir
            Write-Host "Creating new virtual environment..."
            & python -m venv $VenvDir
        }
    } else {
        Write-Host "Creating virtual environment..."
        & python -m venv $VenvDir
    }
}

# Activate virtual environment
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
. $ActivateScript

# Upgrade pip
Write-Host ""
Write-Host "Upgrading pip..."
& pip install --upgrade pip

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..."
$RequirementsFile = Join-Path $ProjectDir "requirements.txt"
& pip install -r $RequirementsFile

# Install the package in development mode
Write-Host ""
Write-Host "Installing Media Lake Resolve Plugin..."
& pip install -e $ProjectDir

# Download FFmpeg if not present
if (-not $SkipFFmpeg) {
    $FFmpegDir = Join-Path $ProjectDir "medialake_resolve\ffmpeg\bin"
    $FFmpegExe = Join-Path $FFmpegDir "ffmpeg.exe"
    
    if (-not (Test-Path $FFmpegExe)) {
        Write-Host ""
        Write-Host "FFmpeg not found."
        Write-Host "Note: FFmpeg is optional. If you have it installed system-wide, it will be used automatically."
        Write-Host ""
        
        $downloadFFmpeg = Read-Host "Download FFmpeg? (y/N)"
        
        if ($downloadFFmpeg -eq "y" -or $downloadFFmpeg -eq "Y") {
            Write-Host ""
            Write-Host "Please download FFmpeg manually from: https://www.gyan.dev/ffmpeg/builds/"
            Write-Host "Download 'ffmpeg-release-essentials.zip' and extract:"
            Write-Host "  - ffmpeg.exe"
            Write-Host "  - ffprobe.exe"
            Write-Host "To: $FFmpegDir"
            Write-Host ""
            
            # Create directory
            New-Item -ItemType Directory -Force -Path $FFmpegDir | Out-Null
        }
    }
}

# Create launch script
$LaunchScript = Join-Path $ProjectDir "launch_medialake.bat"
$LaunchContent = @"
@echo off
cd /d "$ProjectDir"
call "$VenvDir\Scripts\activate.bat"
python -m medialake_resolve %*
"@
Set-Content -Path $LaunchScript -Value $LaunchContent

# Create PowerShell launch script
$LaunchPS1 = Join-Path $ProjectDir "launch_medialake.ps1"
$LaunchPS1Content = @"
`$ErrorActionPreference = "Stop"
Set-Location "$ProjectDir"
. "$VenvDir\Scripts\Activate.ps1"
python -m medialake_resolve `$args
"@
Set-Content -Path $LaunchPS1 -Value $LaunchPS1Content

# Create desktop shortcut
if ($CreateShortcut) {
    Write-Host ""
    Write-Host "Creating desktop shortcut..."
    
    $WshShell = New-Object -ComObject WScript.Shell
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = Join-Path $Desktop "Media Lake for Resolve.lnk"
    
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "powershell.exe"
    $Shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$LaunchPS1`""
    $Shortcut.WorkingDirectory = $ProjectDir
    $Shortcut.Description = "Media Lake Plugin for DaVinci Resolve"
    $Shortcut.Save()
    
    Write-Host "✓ Desktop shortcut created" -ForegroundColor Green
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run the plugin:"
Write-Host "  $LaunchScript"
Write-Host ""
Write-Host "Or from PowerShell:"
Write-Host "  . $VenvDir\Scripts\Activate.ps1"
Write-Host "  medialake-resolve"
Write-Host ""
Write-Host "Make sure DaVinci Resolve is running before launching the plugin."
