#requires -Version 5.1
<#
.SYNOPSIS
    Ordina / 归序 — Windows 打包脚本

.DESCRIPTION
    用 PyInstaller 把 Ordina 打成两个可执行文件：
      - Ordina.exe     图形界面（无控制台窗口）
      - ordina-cli.exe 命令行（保留控制台，不打包 tkinter）
    可选单文件 / 单目录模式，可选再压一份便携 ZIP。

.EXAMPLE
    .\build.ps1
        默认：单目录模式，GUI + CLI 都打

    .\build.ps1 -Mode onefile
        打成单个 exe（启动稍慢，但只有一个文件）

    .\build.ps1 -Target cli
        只打命令行版

    .\build.ps1 -Clean -Zip
        清空旧产物后重新打包，并额外产出便携 ZIP

.NOTES
    必须用带 tkinter 的 Python（python.org 官方安装包默认自带）打 GUI 版，
    托管/嵌入式 Python 通常没有 tkinter，只能打 CLI 版。
#>
[CmdletBinding()]
param(
    [ValidateSet('all', 'gui', 'cli')]
    [string]$Target = 'all',

    [ValidateSet('onedir', 'onefile')]
    [string]$Mode = 'onedir',

    # 打包前清空 build/ 与 dist/，并强制 PyInstaller 重建缓存
    [switch]$Clean,

    # 额外产出 dist\Ordina-v<版本>-win64.zip 便携包
    [switch]$Zip,

    # 手动指定 Python 解释器路径
    [string]$Python = ''
)

$ErrorActionPreference = 'Stop'

$Root = $PSScriptRoot
$Packaging = Join-Path $Root 'packaging'
$DistPath = Join-Path $Root 'dist'
$BuildPath = Join-Path $Root 'build'

# ───────────────────────── 输出辅助 ─────────────────────────
function Write-Step { param($m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Info { param($m) Write-Host "    $m" -ForegroundColor DarkGray }
function Write-Ok   { param($m) Write-Host "    [OK] $m" -ForegroundColor Green }
function Write-Warn { param($m) Write-Host "    [!]  $m" -ForegroundColor Yellow }
function Stop-Build { param($m) Write-Host "`n[失败] $m" -ForegroundColor Red; exit 1 }

Write-Host ''
Write-Host '  Ordina / 归序 — 打包脚本' -ForegroundColor Yellow
Write-Host '  ──────────────────────────────────────────' -ForegroundColor DarkGray

# ─────────────────────── 1. 选择解释器 ───────────────────────
Write-Step '检查 Python 环境'

$needTk = ($Target -ne 'cli')   # 只有打 GUI 时才需要 tkinter

function Test-Python {
    param([string]$Exe, [bool]$NeedTk)
    if ([string]::IsNullOrWhiteSpace($Exe)) { return $false }
    if (-not (Test-Path $Exe)) { return $false }
    $probe = if ($NeedTk) { 'import sys, tkinter, PyInstaller' } else { 'import sys, PyInstaller' }
    try {
        & $Exe -c $probe 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

$candidates = New-Object System.Collections.ArrayList
if ($Python) { [void]$candidates.Add($Python) }
$cmd = Get-Command python -ErrorAction SilentlyContinue
if ($cmd) { [void]$candidates.Add($cmd.Source) }
[void]$candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'))
[void]$candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'))
[void]$candidates.Add('C:\Python312\python.exe')
[void]$candidates.Add('C:\Python313\python.exe')

$Py = $null
foreach ($c in $candidates) {
    if (Test-Python -Exe $c -NeedTk $needTk) { $Py = $c; break }
}

if (-not $Py) {
    Write-Host ''
    Write-Host '    没有找到可用的 Python，需要满足：' -ForegroundColor Yellow
    Write-Host '      1) 已安装 PyInstaller    :  pip install pyinstaller' -ForegroundColor Yellow
    if ($needTk) {
        Write-Host '      2) 带 tkinter（打 GUI 必需，python.org 官方安装包自带）' -ForegroundColor Yellow
    }
    Write-Host ''
    Write-Host '    也可以用 -Python 手动指定，例如：' -ForegroundColor Yellow
    Write-Host '      .\build.ps1 -Python "C:\Path\To\python.exe"' -ForegroundColor Yellow
    Stop-Build 'Python 环境不满足打包要求'
}

$pyVer = (& $Py -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])').Trim()
Write-Ok "使用解释器: $Py  (Python $pyVer)"

# ───────────────────────── 2. 读取版本 ─────────────────────────
$version = (& $Py -c "import sys; sys.path.insert(0, r'$Root'); import ordina; print(ordina.__version__)").Trim()
if (-not $version) { Stop-Build '无法从 ordina/__init__.py 读取版本号' }
Write-Ok "项目版本: v$version"

# ───────────────────────── 3. 清理旧产物 ─────────────────────────
if ($Clean) {
    Write-Step '清理旧产物'
    Remove-Item -Recurse -Force $BuildPath -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $DistPath -ErrorAction SilentlyContinue
    Write-Ok '已清空 build/ 与 dist/'
}
$cleanFlag = if ($Clean) { @('--clean') } else { @() }
$env:ORDINA_ONEFILE = if ($Mode -eq 'onefile') { '1' } else { '0' }
Write-Info "打包模式: $Mode   (目标: $Target)"

# ───────────────────────── 4. 执行打包 ─────────────────────────
function Invoke-PyInstaller {
    param([string]$Name, [string]$SpecFile)

    $specPath = Join-Path $Packaging $SpecFile
    if (-not (Test-Path $specPath)) { Stop-Build "找不到 spec 文件: $specPath" }

    Write-Step "打包 $Name"
    $work = Join-Path $BuildPath $Name
    # 注意：调用的是原生命令（python.exe），参数要用数组变量直接展开（$cleanFlag）；
    #       @cleanFlag 是 PowerShell 命令的 splatting 语法，在 5.1 里传给原生命令会解析失败。
    & $Py -m PyInstaller --noconfirm $cleanFlag --log-level WARN `
        --distpath $DistPath --workpath $work $specPath

    if ($LASTEXITCODE -ne 0) { Stop-Build "$Name 打包失败（退出码 $LASTEXITCODE）" }
    Write-Ok "$Name 打包完成"
}

if ($Target -eq 'all' -or $Target -eq 'gui') { Invoke-PyInstaller -Name 'gui' -SpecFile 'ordina.spec' }
if ($Target -eq 'all' -or $Target -eq 'cli') { Invoke-PyInstaller -Name 'cli' -SpecFile 'ordina-cli.spec' }

# ───────────────────────── 5. 产物校验 ─────────────────────────
Write-Step '校验产物'

if ($Mode -eq 'onefile') {
    $guiExe = Join-Path $DistPath 'Ordina.exe'
    $cliExe = Join-Path $DistPath 'ordina-cli.exe'
} else {
    $guiExe = Join-Path $DistPath 'Ordina\Ordina.exe'
    $cliExe = Join-Path $DistPath 'Ordina-cli\ordina-cli.exe'
}

$built = @()
if (($Target -eq 'all' -or $Target -eq 'gui') -and (Test-Path $guiExe)) {
    $size = [math]::Round((Get-Item $guiExe).Length / 1MB, 1)
    Write-Ok "GUI  $guiExe  ($size MB)"
    $built += $guiExe
} elseif ($Target -eq 'gui') {
    Stop-Build "未找到 GUI 产物: $guiExe"
}

if (($Target -eq 'all' -or $Target -eq 'cli') -and (Test-Path $cliExe)) {
    $size = [math]::Round((Get-Item $cliExe).Length / 1MB, 1)
    Write-Ok "CLI  $cliExe  ($size MB)"
    $built += $cliExe
} elseif ($Target -eq 'cli') {
    Stop-Build "未找到 CLI 产物: $cliExe"
}

# ───────────────────── 6. CLI 冒烟测试（秒级） ─────────────────────
if (Test-Path $cliExe) {
    Write-Step '运行 CLI 冒烟测试'
    $out = & $cliExe version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Ok ("ordina-cli.exe version → " + ($out -join ' '))
    } else {
        Write-Warn "CLI 冒烟测试未通过: $($out -join ' ')"
    }
}

# ───────────────────────── 7. 便携 ZIP ─────────────────────────
if ($Zip) {
    Write-Step '生成便携 ZIP'
    $stage = Join-Path $DistPath "Ordina-v$version-win64"
    Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $stage -Force | Out-Null

    if ($Mode -eq 'onefile') {
        Copy-Item $guiExe $stage -ErrorAction SilentlyContinue
        Copy-Item $cliExe $stage -ErrorAction SilentlyContinue
    } else {
        if (Test-Path (Join-Path $DistPath 'Ordina')) {
            Copy-Item (Join-Path $DistPath 'Ordina') $stage -Recurse -Force
        }
        if (Test-Path (Join-Path $DistPath 'Ordina-cli')) {
            Copy-Item (Join-Path $DistPath 'Ordina-cli') $stage -Recurse -Force
        }
    }

    # 说明文档（文件名保持 ASCII，压缩包内不出现编码问题）
    if (Test-Path (Join-Path $Packaging 'PORTABLE.md')) {
        Copy-Item (Join-Path $Packaging 'PORTABLE.md') (Join-Path $stage 'README-PORTABLE.md') -Force
    }
    if (Test-Path (Join-Path $Root 'README.md')) {
        Copy-Item (Join-Path $Root 'README.md') (Join-Path $stage 'README.md') -Force
    }

    $zipPath = Join-Path $DistPath "Ordina-v$version-win64.zip"
    Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -CompressionLevel Optimal
    $zsize = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    Write-Ok "便携包: $zipPath  ($zsize MB)"
}

# ───────────────────────── 完成 ─────────────────────────
Write-Host ''
Write-Host '  ──────────────────────────────────────────' -ForegroundColor DarkGray
Write-Host "  打包完成 v$version  ($Mode)" -ForegroundColor Green
Write-Host "  产物目录: $DistPath" -ForegroundColor White
Write-Host ''
Write-Host '  下一步:' -ForegroundColor Cyan
Write-Host '    · GUI：双击 Ordina.exe（首次启动可能被 SmartScreen 拦截，选"仍要运行"）' -ForegroundColor White
Write-Host '    · CLI：ordina-cli.exe organize --path %USERPROFILE%\Downloads' -ForegroundColor White
if (-not $Zip) {
    Write-Host '    · 想要压缩包：.\build.ps1 -Zip' -ForegroundColor White
}
Write-Host ''
