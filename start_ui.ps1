<#
Open Matrix Publisher — Windows 启动器（start_ui.ps1）

SAU 定位优先级：
  1. 环境变量 SAU_ROOT（显式指定）
  2. 常见位置自动检测（%USERPROFILE%\social-auto-upload 等）
  3. 交互引导一键安装（git clone + venv + 依赖 + patchright chromium）

用法:
  .\start_ui.ps1                启动控制台（自动检测 / 引导安装 SAU）
  .\start_ui.ps1 -Check         只检测环境并打印结果，不启动服务
  $env:SAU_ROOT="C:\path\to\sau"; .\start_ui.ps1   显式指定 SAU 安装路径

提示：直接双击 start_ui.bat 即可，无需手动打开 PowerShell。
#>
param([switch]$Check)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$SAU_REPO_URL = "https://github.com/dreammis/social-auto-upload.git"
$SAU_DEFAULT_DIR = Join-Path $env:USERPROFILE "social-auto-upload"

function Test-SauValid([string]$root) {
    if (-not $root) { return $false }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { return $false }
    $py = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $py)) { return $false }
    $markers = @(
        (Join-Path $root ".venv\Scripts\sau.exe"),
        (Join-Path $root "pyproject.toml"),
        (Join-Path $root "uploader"),
        (Join-Path $root "sau_cli.py")
    )
    foreach ($m in $markers) { if (Test-Path -LiteralPath $m) { return $true } }
    return $false
}

function Find-Sau {
    $candidates = @(
        $SAU_DEFAULT_DIR,
        (Join-Path (Split-Path $PSScriptRoot -Parent) "social-auto-upload"),
        (Join-Path $PSScriptRoot "deps\social-auto-upload"),
        "C:\social-auto-upload"
    )
    foreach ($c in $candidates) { if (Test-SauValid $c) { return $c } }
    return $null
}

function Install-Sau([string]$target) {
    Write-Host "开始安装 social-auto-upload → $target"
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "未找到 git，请先安装 https://git-scm.com/ 后重试。" -ForegroundColor Red
        exit 1
    }
    if (Test-Path -LiteralPath $target) {
        Write-Host "目录已存在（内容可能不完整），将基于它补齐环境..." -ForegroundColor Yellow
    } else {
        git clone --depth 1 $SAU_REPO_URL $target
        if ($LASTEXITCODE -ne 0) {
            Write-Host "克隆失败，请检查网络后重试；或手动安装后通过 SAU_ROOT 指定路径。" -ForegroundColor Red
            exit 1
        }
    }
    Push-Location $target
    $py = Join-Path $target ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $py)) {
        Write-Host "创建虚拟环境 $target\.venv ..."
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            Write-Host "创建虚拟环境失败（需要 Python 3.10+）。请手动安装 SAU 后设置 SAU_ROOT。" -ForegroundColor Red
            exit 1
        }
    }
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Write-Host "检测到 uv，使用官方推荐方式安装主线依赖（uv pip install -e .）..."
        uv pip install --python $py -e .
        if ($LASTEXITCODE -ne 0) {
            Write-Host "uv 安装失败，回退到 pip requirements.txt 路径..." -ForegroundColor Yellow
            & $py -m pip install -r requirements.txt
        }
    } else {
        Write-Host "未检测到 uv，使用 pip 安装兼容依赖（requirements.txt）..."
        & $py -m pip install -r requirements.txt
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "依赖安装失败，请查看上方报错。" -ForegroundColor Red
        exit 1
    }
    Write-Host "安装 patchright Chromium（网络慢可先执行：`$env:PLAYWRIGHT_DOWNLOAD_HOST='https://npmmirror.com/mirrors/playwright'）..."
    & $py -m patchright install chromium
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Chromium 安装未完成，可稍后手动执行：& $py -m patchright install chromium" -ForegroundColor Yellow
    }
    if (-not (Test-Path (Join-Path $target "conf.py")) -and (Test-Path (Join-Path $target "conf.example.py"))) {
        Copy-Item (Join-Path $target "conf.example.py") (Join-Path $target "conf.py")
    }
    Pop-Location
    if (Test-SauValid $target) {
        Write-Host "SAU 安装完成：$target" -ForegroundColor Green
        $script:SAU_ROOT = $target
    } else {
        Write-Host "SAU 环境仍有缺失，请检查上方报错。修复后重新运行 .\start_ui.bat。" -ForegroundColor Red
        exit 1
    }
}

function Show-ManualHint {
    Write-Host "未检测到 social-auto-upload (SAU) 引擎，无法启动。" -ForegroundColor Red
    Write-Host ""
    Write-Host "  方式一（推荐）：再次运行 .\start_ui.bat 并选择自动安装"
    Write-Host "  方式二（手动）："
    Write-Host "    git clone $SAU_REPO_URL $SAU_DEFAULT_DIR"
    Write-Host "    cd $SAU_DEFAULT_DIR; python -m venv .venv"
    Write-Host "    .venv\Scripts\pip install -r requirements.txt    # 或 uv pip install -e ."
    Write-Host "    .venv\Scripts\python -m patchright install chromium"
    Write-Host "  或把 SAU 装在其它位置后用 SAU_ROOT 指定：`$env:SAU_ROOT='C:\path\to\sau'"
}

# ── 定位 SAU ──
$script:SAU_ROOT = $env:SAU_ROOT
$py = $null
if ($script:SAU_ROOT) {
    if (Test-SauValid $script:SAU_ROOT) {
        $py = Join-Path $script:SAU_ROOT ".venv\Scripts\python.exe"
    } else {
        Write-Host "SAU_ROOT='$script:SAU_ROOT' 不可用，尝试自动检测..." -ForegroundColor Yellow
        $script:SAU_ROOT = $null
    }
}
if (-not $py) {
    $found = Find-Sau
    if ($found) {
        Write-Host "自动检测到 social-auto-upload：$found"
        $script:SAU_ROOT = $found
        $py = Join-Path $found ".venv\Scripts\python.exe"
    } else {
        if ($Check) { Show-ManualHint; exit 1 }
        Write-Host "未检测到 social-auto-upload (SAU) 引擎。"
        $ans = Read-Host "是否现在自动安装到 $SAU_DEFAULT_DIR ？[Y/n]"
        if ($ans -match "^[nN]") {
            Show-ManualHint
            exit 1
        } else {
            Install-Sau $SAU_DEFAULT_DIR
            $py = Join-Path $SAU_DEFAULT_DIR ".venv\Scripts\python.exe"
        }
    }
}
if (-not $py -or -not (Test-Path -LiteralPath $py)) { Show-ManualHint; exit 1 }

# ── -Check：只打印环境检测结果 ──
if ($Check) {
    Write-Host "=========================================================="
    Write-Host "✅ SAU 引擎已就绪"
    Write-Host "   SAU_ROOT   = $script:SAU_ROOT"
    Write-Host "   Python     = $py"
    $sauExe = Join-Path $script:SAU_ROOT ".venv\Scripts\sau.exe"
    if (Test-Path -LiteralPath $sauExe) {
        Write-Host "   sau CLI    = 存在"
    } else {
        Write-Host "   sau CLI    : 未找到（部分平台走源码导入，不影响控制台启动）"
    }
    $cookieDir = Join-Path $script:SAU_ROOT "cookies"
    $n = if (Test-Path -LiteralPath $cookieDir) { (Get-ChildItem -LiteralPath $cookieDir -Filter "*_default.json" -File).Count } else { 0 }
    Write-Host "   Cookie 目录 = $cookieDir"
    Write-Host "   已登录 Cookie = $n 个"
    Write-Host "=========================================================="
    exit 0
}

# ── 补全控制台依赖（若 SAU venv 缺 flask / browser_cookie3 则静默安装）──
& $py -c "import flask, browser_cookie3" 2>$null
if ($LASTEXITCODE -ne 0) { & $py -m pip install -q flask browser_cookie3 }

Write-Host "=========================================================="
Write-Host "🚀 正在启动 Open Matrix Publisher 可视化 Web 控制台..."
Write-Host "=========================================================="
Write-Host "🌐 后端 API 服务运行于 http://localhost:5001"
Write-Host "💻 即将自动打开浏览器..."
Write-Host "提示：按 Ctrl+C 可停止控制台服务"
Write-Host "----------------------------------------------------------"

Start-Process "http://localhost:5001"
& $py local_bridge_server.py
