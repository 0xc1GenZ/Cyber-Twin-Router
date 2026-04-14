# ================================================
# Cyber-Twin Router + IoT + Blockchain
# Windows PowerShell One-Click Setup â€” PROFESSIONAL FIXED v3.3
# ================================================

Write-Host "Cyber-Twin Router Full Setup (Windows + WSL) â€” FIXED v3.3" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

# Check for Admin rights
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Please run this script as Administrator!" -ForegroundColor Red
    exit 1
}

# 1. Install WSL if not present
if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Windows Subsystem for Linux..." -ForegroundColor Yellow
    wsl --install
    Write-Host "WSL installed. RESTART your PC now and run this script again." -ForegroundColor Green
    exit 0
}

# 2. Install Ubuntu if missing
$distros = wsl --list --quiet
if ($distros -notmatch "Ubuntu") {
    Write-Host "Installing Ubuntu distro..." -ForegroundColor Yellow
    wsl --install -d Ubuntu
    Write-Host "Ubuntu is installing. This may take 1-2 minutes." -ForegroundColor Green
    Start-Sleep -Seconds 30
}

# 3. Set Ubuntu as default
wsl --set-default Ubuntu
Write-Host "Ubuntu set as default WSL distro" -ForegroundColor Green

Write-Host "Updating WSL..." -ForegroundColor Cyan
wsl --update

$currentPath = Get-Location
$wsldir = "/mnt/" + $currentPath.Drive.Name.ToLower() + $currentPath.Path.Substring(2).Replace("\", "/")

Write-Host "Detected project folder inside WSL: $wsldir" -ForegroundColor Yellow
Write-Host "Launching deployment inside WSL..." -ForegroundColor Cyan

# Super safe command - no && chain at all
wsl -d Ubuntu -e bash -c "cd '$$wsldir' && chmod +x deploy-all.sh && ./deploy-all.sh"

Write-Host "
Setup completed successfully!" -ForegroundColor Green
Write-Host "Watch the WSL terminal that just opened." -ForegroundColor Cyan
Write-Host "When finished, open browser: http://localhost:5000" -ForegroundColor Cyan
Write-Host "To simulate attack later (inside WSL): python3 scripts/simulate-iot-attack.py" -ForegroundColor White
