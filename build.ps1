#requires -Version 5.1
<#
.SYNOPSIS
    Ordina / 归序 — Windows 打包脚本（仅 GUI）

.DESCRIPTION
    用 PyInstaller 把 Ordina 打成 dist\Ordina\Ordina.exe（图形界面，无控制台窗口）。
    可选单文件模式，可选 UPX 压缩，可选再压一份便携 ZIP。

    构建环境优先级：项目 .venv  系统 Python  -Python 手动指定。
    推荐用 .venv（干净、可复现）——系统 Python 里若装过 numpy / pandas 之类的
    大包，有误被间接带入产物的风险。

.EXAMPLE
    .\build.ps1
        默认：单目录模式 + UPX 压缩

    .\build.ps1 -Mode onefile
        打成单个 exe（启动稍慢，但只有一个文件）

    .\build.ps1 -NoUpx
        关闭 UPX 压缩（排查启动故障时用它）

    .\build.ps1 -Clean -Zip
        清空旧产物后重新打包，并额外产出便携 ZIP

.NOTES
    必须用带 tkinter 的 Python（python.org 官方安装包默认自带）。
#>
[CmdletBinding()]
param(
    [ValidateSet('onedir', 'onefile')]
    [string]$Mode = 'onedir',

    # 打包前清空 build/ 与 dist/，并强制 PyInstaller 重建缓存
    [switch]$Clean,

    # 额外产出 dist\Ordina-v<版本>-win64.zip 便携包
    [switch]$Zip,

    # 关闭 UPX 压缩
    [switch]$NoUpx,

    # UPX 所在目录（内含 upx.exe）；默认自动探测，本机为 H:\upx
    [string]$UpxDir = '',

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
Write-Step '检查构建环境'

function Test-Python {
    param([string]$Exe)
    if ([string]::IsNullOrWhiteSpace($Exe)) { return $false }
    if (-not (Test-Path $Exe)) { return $false }
    $probe = 'import sys, tkinter, PyInstaller'
    try {
        & $Exe -c $probe 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

$candidates = New-Object System.Collections.ArrayList
if ($Python) { [void]$candidates.Add($Python) }
# 项目专属虚拟环境优先：干净、可复现
[void]$candidates.Add((Join-Path $Root '.venv\Scripts\python.exe'))
$cmd = Get-Command python -ErrorAction SilentlyContinue
if ($cmd) { [void]$candidates.Add($cmd.Source) }
foreach ($v in 'Python312', 'Python313', 'Python311') {
    [void]$candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Python\$v\python.exe"))
}

$Py = $null
$VenvPy = Join-Path $Root '.venv\Scripts\python.exe'
foreach ($c in $candidates) {
    if (Test-Python -Exe $c) { $Py = $c; break }
}

if (-not $Py) {
    Write-Host ''
    Write-Host '    没有找到可用的 Python，需要同时满足：' -ForegroundColor Yellow
    Write-Host '      1) 已安装 PyInstaller    :  pip install pyinstaller' -ForegroundColor Yellow
    Write-Host '      2) 带 tkinter（GUI 必需，python.org 官方安装包自带）' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '    建议先建一个干净的构建环境：' -ForegroundColor Yellow
    Write-Host '      python -m venv .venv' -ForegroundColor Yellow
    Write-Host '      .venv\Scripts\pip install pyinstaller' -ForegroundColor Yellow
    Stop-Build 'Python 环境不满足打包要求'
}

$pyVer = (& $Py -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])').Trim()
$fromVenv = ($Py -eq $VenvPy)
$pyNote = if ($fromVenv) { '(项目 .venv)' } else { '(系统解释器，建议改用 .venv)' }
Write-Ok "解释器: $Py  Python $pyVer $pyNote"
if (-not $fromVenv) {
    Write-Warn '未在 .venv 中构建：系统环境的第三方包有误打包风险'
}

# ───────────────────────── 2. 读取版本 ─────────────────────────
$version = (& $Py -c "import sys; sys.path.insert(0, r'$Root'); import ordina; print(ordina.__version__)").Trim()
if (-not $version) { Stop-Build '无法从 ordina/__init__.py 读取版本号' }
Write-Ok "项目版本: v$version"

# ───────────────────────── 3. UPX 探测 ─────────────────────────
$upxArgs = @()
if ($NoUpx) {
    Write-Info 'UPX: 已按 -NoUpx 关闭'
} else {
    $upxExe = 'upx.exe'
    $found = ''
    $search = @()
    if ($UpxDir) { $search += $UpxDir }
    $search += @('H:\upx', 'C:\upx', 'C:\Program Files\upx', 'C:\tools\upx')
    # PATH 兜底
    foreach ($d in ($env:PATH -split ';')) {
        $d = $d.Trim().Trim('"')
        if ($d) { $search += $d }
    }
    foreach ($d in $search) {
        if ($d -and (Test-Path (Join-Path $d $upxExe))) { $found = $d; break }
    }

    if ($found) {
        $uv = (& (Join-Path $found $upxExe) --version 2>$null | Select-Object -First 1)
        $uv = ($uv -replace '^upx\s+', '').Trim()
        Write-Ok "UPX: $found  (v$uv)"
        $upxArgs = @('--upx-dir', $found)
    } else {
        Write-Warn '未找到 UPX，跳过压缩（产物会明显更大）'
        Write-Info '可手动指定：.\build.ps1 -UpxDir "D:\path\to\upx"'
    }
}

# ───────────────────────── 4. 清理旧产物 ─────────────────────────
if ($Clean) {
    Write-Step '清理旧产物'
    Remove-Item -Recurse -Force $BuildPath -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $DistPath -ErrorAction SilentlyContinue
    Write-Ok '已清空 build/ 与 dist/'
}
$cleanFlag = if ($Clean) { @('--clean') } else { @() }
$env:ORDINA_ONEFILE = if ($Mode -eq 'onefile') { '1' } else { '0' }
Write-Info "打包模式: $Mode"

# ───────────────────────── 5. 执行打包 ─────────────────────────
Write-Step '打包 GUI'
$specPath = Join-Path $Packaging 'ordina.spec'
if (-not (Test-Path $specPath)) { Stop-Build "找不到 spec 文件: $specPath" }

$work = Join-Path $BuildPath 'gui'
# 注意：调用的是原生命令（python.exe），参数要用数组变量直接展开（$cleanFlag / $upxArgs）；
#      @cleanFlag 是 PowerShell 命令的 splatting 语法，在 5.1 里传给原生命令会解析失败。
& $Py -m PyInstaller --noconfirm $cleanFlag $upxArgs --log-level WARN `
    --distpath $DistPath --workpath $work $specPath

if ($LASTEXITCODE -ne 0) { Stop-Build "打包失败（退出码 $LASTEXITCODE）" }
Write-Ok '打包完成'

# ───────────────────────── 6. 产物校验 ─────────────────────────
Write-Step '校验产物'

if ($Mode -eq 'onefile') {
    $guiExe = Join-Path $DistPath 'Ordina.exe'
    $outDir = $DistPath
} else {
    $guiExe = Join-Path $DistPath 'Ordina\Ordina.exe'
    $outDir = Join-Path $DistPath 'Ordina'
}

if (-not (Test-Path $guiExe)) { Stop-Build "未找到产物: $guiExe" }

$exeSize = [math]::Round((Get-Item $guiExe).Length / 1MB, 2)
$dirSize = if ($Mode -eq 'onefile') { $exeSize } else {
    [math]::Round((Get-ChildItem $outDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
}
Write-Ok "主程序: $guiExe  ($exeSize MB)"
Write-Ok "目录合计: $dirSize MB"

# 版本资源
$vi = (Get-Item $guiExe).VersionInfo
Write-Info "版本资源: $($vi.ProductName) $($vi.FileVersion)"

# ───────────────────── 7. GUI 冒烟测试（启动 4 秒后关闭） ─────────────────────
Write-Step '运行 GUI 冒烟测试'
$proc = Start-Process -FilePath $guiExe -PassThru
Start-Sleep -Seconds 4
$alive = -not $proc.HasExited
$title = $proc.MainWindowTitle
$mem = [math]::Round($proc.WorkingSet64 / 1MB, 1)
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue

if ($alive -and $title) {
    Write-Ok "窗口已创建: 「$title」  内存 $mem MB"
} else {
    Write-Warn "GUI 启动异常（存活=$alive，标题='$title'）—— 可加 -NoUpx 重打排查"
}

# ───────────────────────── 8. 便携 ZIP ─────────────────────────
if ($Zip) {
    Write-Step '生成便携 ZIP'
    $stage = Join-Path $DistPath "Ordina-v$version-win64"
    Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $stage -Force | Out-Null

    if ($Mode -eq 'onefile') {
        Copy-Item $guiExe $stage -Force
    } else {
        Copy-Item $outDir $stage -Recurse -Force
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
Write-Host "  产物: $guiExe" -ForegroundColor White
Write-Host ''
Write-Host '  下一步:' -ForegroundColor Cyan
Write-Host '    · 双击 Ordina.exe 启动（首次可能被 SmartScreen 拦截，选"仍要运行"）' -ForegroundColor White
Write-Host '    · 命令行用法仍可用源码：python -m ordina cli organize --path ...' -ForegroundColor White
if (-not $Zip) {
    Write-Host '    · 想要压缩包：.\build.ps1 -Zip' -ForegroundColor White
}
Write-Host ''
