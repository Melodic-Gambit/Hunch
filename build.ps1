#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# ── 1. Version: branch -> tag -> version.txt ──────────────────────────────────
Write-Host ""
Write-Host "=== Hunch - determining version ===" -ForegroundColor Cyan

$version = $null

# 1a. Current branch name: task/#26/V.5.0.0 -> "5.0.0"
$branch = (& git -C $root rev-parse --abbrev-ref HEAD 2>$null).Trim()
if ($LASTEXITCODE -eq 0 -and $branch -match 'V\.(\d+\.\d+(?:\.\d+)*)') {
    $version = $Matches[1]
    Write-Host "  Branch  : $branch  ->  version $version" -ForegroundColor Green
}

# 1b. Git tag fallback
if (-not $version) {
    $gitTagRaw = & git -C $root describe --tags --abbrev=0 2>$null
    if ($LASTEXITCODE -eq 0 -and $gitTagRaw) {
        $gitTag = "$gitTagRaw".Trim()
        $version = $gitTag.TrimStart("v")
        Write-Host "  Git tag : $gitTag  ->  version $version" -ForegroundColor Green
    }
}

# 1c. version.txt fallback
if (-not $version) {
    $versionFile = Join-Path $root "version.txt"
    if (Test-Path $versionFile) {
        $version = (Get-Content $versionFile -Encoding UTF8 -Raw).Trim()
        Write-Warning "  No branch version / git tag, using version.txt: $version"
    } else {
        $version = "0.0.0"
        Write-Warning "  Version unknown, using: $version"
    }
}

# ── 2. Update version.txt ─────────────────────────────────────────────────────
Set-Content -Path (Join-Path $root "version.txt") -Value $version -Encoding UTF8 -NoNewline
Write-Host "  version.txt updated: $version"

# ── 3. Regenerate version_info.txt (Windows EXE Properties) ──────────────────
$parts = $version -split '\.'
$major = if ($parts.Count -gt 0) { [int]$parts[0] } else { 0 }
$minor = if ($parts.Count -gt 1) { [int]$parts[1] } else { 0 }
$patch = if ($parts.Count -gt 2) { [int]$parts[2] } else { 0 }
$build = 0
$ver4  = "$major.$minor.$patch.$build"

$vinfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($major, $minor, $patch, $build),
    prodvers=($major, $minor, $patch, $build),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u''),
         StringStruct(u'FileDescription', u'Hunch'),
         StringStruct(u'FileVersion', u'$ver4'),
         StringStruct(u'InternalName', u'Hunch'),
         StringStruct(u'LegalCopyright', u'Copyright 2026'),
         StringStruct(u'OriginalFilename', u'Hunch.exe'),
         StringStruct(u'ProductName', u'Hunch'),
         StringStruct(u'ProductVersion', u'$ver4')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
  ]
)
"@
Set-Content -Path (Join-Path $root "version_info.txt") -Value $vinfo -Encoding UTF8
Write-Host "  version_info.txt updated: $ver4"

# ── 4. Clean ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Cleaning dist\ and build\ ===" -ForegroundColor Cyan
Remove-Item -Recurse -Force (Join-Path $root "dist")  -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $root "build") -ErrorAction SilentlyContinue

# ── 5. PyInstaller: installer build ──────────────────────────────────────────
Write-Host ""
Write-Host "=== PyInstaller (installer) ===" -ForegroundColor Cyan
Push-Location $root
try {
    $ErrorActionPreference = "Continue"
    pyinstaller main.spec --noconfirm
    $pyExit = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($pyExit -ne 0) { throw "PyInstaller (installer) failed with code $pyExit" }
} finally {
    $ErrorActionPreference = "Stop"
    Pop-Location
}

# ── 6. Verify installer ───────────────────────────────────────────────────────
$exePath = Join-Path $root "dist\Hunch\Hunch.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "BUILD FAILED: $exePath not found" -ForegroundColor Red
    exit 1
}

# ── 5b. PyInstaller: portable (onefile) build ─────────────────────────────────
Write-Host ""
Write-Host "=== PyInstaller (portable) ===" -ForegroundColor Cyan
# Очищаем только build\ — dist\Hunch\ уже готов, не трогаем
Remove-Item -Recurse -Force (Join-Path $root "build") -ErrorAction SilentlyContinue
Push-Location $root
try {
    $ErrorActionPreference = "Continue"
    pyinstaller main_portable.spec --noconfirm
    $pyExit = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($pyExit -ne 0) { throw "PyInstaller (portable) failed with code $pyExit" }
} finally {
    $ErrorActionPreference = "Stop"
    Pop-Location
}

# ── 6b. Verify portable ───────────────────────────────────────────────────────
$exePortablePath = Join-Path $root "dist\Hunch.exe"
if (-not (Test-Path $exePortablePath)) {
    Write-Host "BUILD FAILED: $exePortablePath not found" -ForegroundColor Red
    exit 1
}

# ── 7. Code Signing (optional) ───────────────────────────────────────────────
# Задайте HUNCH_CERT_THUMBPRINT (отпечаток из хранилища) ИЛИ положите codesign.pfx
# рядом со скриптом и задайте HUNCH_CERT_PASSWORD. Без этого шаг пропускается.
Write-Host ""
Write-Host "=== Code Signing ===" -ForegroundColor Cyan

$certThumb = $env:HUNCH_CERT_THUMBPRINT
$pfxFile   = Join-Path $root "codesign.pfx"
$certPass  = $env:HUNCH_CERT_PASSWORD

if (-not $certThumb -and -not (Test-Path $pfxFile)) {
    Write-Host "  Сертификат не настроен — подписание пропущено" -ForegroundColor DarkGray
    Write-Host "  Задайте HUNCH_CERT_THUMBPRINT или положите codesign.pfx + HUNCH_CERT_PASSWORD" -ForegroundColor DarkGray
} else {
    $signtool = $null
    $sdkBin = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
    if (Test-Path $sdkBin) {
        $found = Get-ChildItem $sdkBin -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like "*x64*" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($found) { $signtool = $found.FullName }
    }
    if (-not $signtool) {
        try { $signtool = (Get-Command signtool.exe -ErrorAction Stop).Source } catch {}
    }
    if (-not $signtool) {
        Write-Warning "  signtool.exe не найден. Установите 'Windows SDK Signing Tools for Desktop Apps'"
    } else {
        Write-Host "  signtool : $signtool" -ForegroundColor DarkGray
        $tsUrl = "http://timestamp.digicert.com"

        # Подписываем installer
        if ($certThumb) {
            Write-Host "  Подписание installer: $exePath" -ForegroundColor Yellow
            & $signtool sign /fd SHA256 /sha1 $certThumb /tr $tsUrl /td SHA256 $exePath
            if ($LASTEXITCODE -ne 0) { Write-Warning "  installer: signtool вернул $LASTEXITCODE" } else { Write-Host "  installer подписан" -ForegroundColor Green }
        } elseif ($certPass) {
            Write-Host "  Подписание installer: $exePath" -ForegroundColor Yellow
            & $signtool sign /fd SHA256 /f $pfxFile /p $certPass /tr $tsUrl /td SHA256 $exePath
            if ($LASTEXITCODE -ne 0) { Write-Warning "  installer: signtool вернул $LASTEXITCODE" } else { Write-Host "  installer подписан" -ForegroundColor Green }
        } else {
            Write-Warning "  codesign.pfx найден, но HUNCH_CERT_PASSWORD не задан — пропуск"
        }

        # Подписываем portable
        if ($certThumb) {
            Write-Host "  Подписание portable: $exePortablePath" -ForegroundColor Yellow
            & $signtool sign /fd SHA256 /sha1 $certThumb /tr $tsUrl /td SHA256 $exePortablePath
            if ($LASTEXITCODE -ne 0) { Write-Warning "  portable: signtool вернул $LASTEXITCODE" } else { Write-Host "  portable подписан" -ForegroundColor Green }
        } elseif ($certPass) {
            Write-Host "  Подписание portable: $exePortablePath" -ForegroundColor Yellow
            & $signtool sign /fd SHA256 /f $pfxFile /p $certPass /tr $tsUrl /td SHA256 $exePortablePath
            if ($LASTEXITCODE -ne 0) { Write-Warning "  portable: signtool вернул $LASTEXITCODE" } else { Write-Host "  portable подписан" -ForegroundColor Green }
        }
    }
}

# ── 8. ZIP archives ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Archiving (ZIP) ===" -ForegroundColor Cyan

$zipName         = "Hunch_v$version.zip"
$zipPath         = Join-Path $root "dist\$zipName"
$zipPortableName = "Hunch_v${version}_portable.zip"
$zipPortablePath = Join-Path $root "dist\$zipPortableName"

Compress-Archive -Path (Join-Path $root "dist\Hunch\*") `
                 -DestinationPath $zipPath `
                 -Force

Compress-Archive -Path $exePortablePath `
                 -DestinationPath $zipPortablePath `
                 -Force

# ── 9. Installer images ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Installer images (generate_installer_images.py) ===" -ForegroundColor Cyan
$ErrorActionPreference = "Continue"
python (Join-Path $root "generate_installer_images.py")
$imgExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($imgExit -ne 0) {
    Write-Warning "  generate_installer_images.py вернул $imgExit — installer может использовать изображения по умолчанию"
} else {
    Write-Host "  Изображения установщика готовы" -ForegroundColor Green
}

# ── 9b. LATEST_CHANGES.txt for installer ─────────────────────────────────────
Write-Host ""
Write-Host "=== Latest Changes (for installer) ===" -ForegroundColor Cyan

$latestChangesPath = Join-Path $root "LATEST_CHANGES.txt"
$logLines = $null
try {
    $prevTag = (& git -C $root describe --tags --abbrev=0 "HEAD^" 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $prevTag) { throw "no prev tag" }
    $logLines = & git -C $root log "$prevTag..HEAD" --pretty=format:"* %s" --no-merges 2>$null
    if (-not $logLines) { throw "no commits since tag" }
    Write-Host "  Changes since $prevTag" -ForegroundColor DarkGray
} catch {
    $logLines = & git -C $root log --pretty=format:"* %s" --no-merges -n 15 2>$null
    Write-Host "  No previous tag — using last 15 commits" -ForegroundColor DarkGray
}
$content = "Версия v$version`r`n`r`n" + ($logLines -join "`r`n")
Set-Content -Path $latestChangesPath -Value $content -Encoding UTF8
Write-Host "  LATEST_CHANGES.txt written" -ForegroundColor Green

# ── 10. Inno Setup: create installer EXE ─────────────────────────────────────
Write-Host ""
Write-Host "=== Inno Setup (installer EXE) ===" -ForegroundColor Cyan

$iscc = $null
$isccPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "C:\ProgramData\chocolatey\bin\iscc.exe"
)
foreach ($p in $isccPaths) {
    if (Test-Path $p) { $iscc = $p; break }
}
if (-not $iscc) {
    try { $iscc = (Get-Command iscc.exe -ErrorAction Stop).Source } catch {}
}

if (-not $iscc) {
    Write-Warning "  iscc.exe не найден — установщик .exe не создан. Установите Inno Setup 6 или добавьте его в PATH."
} else {
    Write-Host "  iscc : $iscc" -ForegroundColor DarkGray
    $issPath = Join-Path $root "Hunch.iss"
    $ErrorActionPreference = "Continue"
    & $iscc "/DMyAppVersion=$version" $issPath
    $isccExit = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($isccExit -ne 0) { throw "Inno Setup failed with code $isccExit" }
    Write-Host "  Installer EXE создан" -ForegroundColor Green
}

$installerExePath = Join-Path $root "dist\Hunch_v${version}_installer.exe"

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== BUILD OK - Hunch v$version ===" -ForegroundColor Green
Write-Host "  Installer EXE      : $exePath"
Write-Host "  Installer ZIP      : $zipPath"
Write-Host "  Portable EXE       : $exePortablePath"
Write-Host "  Portable ZIP       : $zipPortablePath"
if (Test-Path $installerExePath) {
    Write-Host "  Setup installer    : $installerExePath"
}
Write-Host ""
