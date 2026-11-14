$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Build on Windows.' }

$root = $PSScriptRoot
$output = Join-Path $root 'output'
$release = Join-Path $output ('windows-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
$toolsPath = Join-Path $output 'packaging-tools'
$previousPythonPath = $env:PYTHONPATH
if (Test-Path -LiteralPath $toolsPath) {
    $env:PYTHONPATH = $toolsPath
}

try {
    & python -B -m PyInstaller --version
    if ($LASTEXITCODE -ne 0) {
        throw 'Install the build dependencies listed in DEPLOY.md.'
    }
    New-Item -ItemType Directory -Path $release | Out-Null
    $icon = Join-Path $root 'car-reminder.ico'
    $source = Join-Path $root 'car_reminder.py'
    & python -B -m PyInstaller --onedir --windowed --name CarReminder --icon $icon --add-data "$icon;." --distpath $release --workpath (Join-Path $output 'build') --specpath $output $source
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    $archive = Join-Path $release 'CarReminder-Windows.zip'
    Compress-Archive -LiteralPath (Join-Path $release 'CarReminder') -DestinationPath $archive
    Get-Item -LiteralPath $archive
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
