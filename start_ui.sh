#!/usr/bin/env bash
# Open Matrix Publisher — Web 控制台启动器
#
# 运行环境说明：
#   本工具依赖 social-auto-upload（SAU）提供上传引擎与浏览器自动化能力
#   （patchright / playwright / sau CLI）。
#   SAU 定位优先级：
#     1. 环境变量 SAU_ROOT（显式指定）
#     2. 常见安装位置自动检测（~/social-auto-upload 等）
#     3. 仍找不到时，在交互终端引导一键安装（clone + venv + 依赖 + 浏览器）
#
# 用法:
#   ./start_ui.sh                       启动控制台（自动检测 / 引导安装 SAU）
#   ./start_ui.sh --check               只检测环境并打印结果，不启动服务
#   SAU_ROOT=/path/to/sau ./start_ui.sh 显式指定 SAU 安装路径

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

SAU_REPO_URL="https://github.com/dreammis/social-auto-upload.git"
SAU_DEFAULT_DIR="$HOME/social-auto-upload"

info() { printf '\033[0;34m%s\033[0m\n' "$*"; }
ok()   { printf '\033[0;32m%s\033[0m\n' "$*"; }
warn() { printf '\033[0;33m%s\033[0m\n' "$*"; }
err()  { printf '\033[0;31m%s\033[0m\n' "$*" >&2; }

# ── 判断某个目录是否为可用的 SAU 安装 ──
# 可用 = 存在 .venv/bin/python，且具备 SAU 引擎特征（sau CLI 可执行文件或源码目录）
sau_looks_valid() {
    local root="$1"
    [ -n "$root" ] || return 1
    [ -d "$root" ] || return 1
    [ -x "$root/.venv/bin/python" ] || return 1
    if [ -x "$root/.venv/bin/sau" ] || [ -f "$root/pyproject.toml" ] || [ -d "$root/uploader" ] || [ -f "$root/sau_cli.py" ]; then
        return 0
    fi
    return 1
}

# ── 在常见位置自动检测 SAU ──
detect_sau() {
    local cand
    for cand in \
        "$SAU_DEFAULT_DIR" \
        "$DIR/../social-auto-upload" \
        "$DIR/deps/social-auto-upload" \
        "/opt/social-auto-upload"; do
        if sau_looks_valid "$cand"; then
            echo "$cand"
            return 0
        fi
    done
    return 1
}

# ── 引导安装 SAU（git clone + venv + 依赖 + patchright Chromium）──
install_sau() {
    local target="$1"

    if ! command -v git >/dev/null 2>&1; then
        err "未找到 git，无法自动安装。请先安装 git，或手动安装 SAU 后设置 SAU_ROOT。"
        exit 1
    fi

    info "开始安装 social-auto-upload → $target"
    if [ -d "$target" ]; then
        warn "目录已存在（内容可能不完整），将基于它补齐环境..."
    else
        git clone --depth 1 "$SAU_REPO_URL" "$target" || {
            err "克隆失败，请检查网络后重试；或手动安装后通过 SAU_ROOT 指定路径。"
            exit 1
        }
    fi

    cd "$target" || exit 1
    local PY="$target/.venv/bin/python"

    if [ ! -x "$PY" ]; then
        info "创建虚拟环境 $target/.venv ..."
        python3 -m venv .venv || {
            err "创建虚拟环境失败（需要 Python 3.10+）。请手动安装 SAU 后设置 SAU_ROOT。"
            exit 1
        }
    fi

    if command -v uv >/dev/null 2>&1; then
        info "检测到 uv，使用官方推荐方式安装主线依赖（uv pip install -e .）..."
        uv pip install --python "$PY" -e . \
            || { warn "uv 安装失败，回退到 pip requirements.txt 路径..."; "$PY" -m pip install -r requirements.txt || exit 1; }
    else
        info "未检测到 uv，使用 pip 安装兼容依赖（requirements.txt）..."
        "$PY" -m pip install -r requirements.txt || exit 1
    fi

    info "安装 patchright Chromium（如网络较慢，可先执行：export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright）..."
    "$PY" -m patchright install chromium || warn "Chromium 安装未完成，可稍后手动执行：$PY -m patchright install chromium"

    # 复制 SAU 配置文件（不存在时才复制）
    if [ ! -f "$target/conf.py" ] && [ -f "$target/conf.example.py" ]; then
        cp "$target/conf.example.py" "$target/conf.py"
    fi

    cd "$DIR" || exit 1
    if sau_looks_valid "$target"; then
        ok "SAU 安装完成：$target"
        export SAU_ROOT="$target"
    else
        err "SAU 环境仍有缺失，请检查上方报错。修复后重新运行 ./start_ui.sh。"
        exit 1
    fi
}

print_manual_install_hint() {
    err "未检测到 social-auto-upload (SAU) 引擎，无法启动。"
    echo ""
    echo "两种解决方式："
    echo "  方式一（推荐）：运行本脚本时选择自动安装： ./start_ui.sh"
    echo "  方式二（手动）："
    echo "    git clone ${SAU_REPO_URL} ${SAU_DEFAULT_DIR}"
    echo "    cd ${SAU_DEFAULT_DIR} && python3 -m venv .venv"
    echo "    .venv/bin/pip install -r requirements.txt        # 或 uv pip install -e ."
    echo "    .venv/bin/python -m patchright install chromium"
    echo "    cd - && ./start_ui.sh"
    echo "  或把 SAU 装在其它位置后用 SAU_ROOT 指定：SAU_ROOT=/path/to/sau ./start_ui.sh"
}

# ── 解析参数 ──
CHECK_MODE=0
for arg in "$@"; do
    case "$arg" in
        --check) CHECK_MODE=1 ;;
        *) warn "忽略未知参数: $arg" ;;
    esac
done

# ── 定位 SAU ──
PY=""
if [ -n "$SAU_ROOT" ]; then
    if sau_looks_valid "$SAU_ROOT"; then
        PY="$SAU_ROOT/.venv/bin/python"
    else
        warn "SAU_ROOT='$SAU_ROOT' 不可用，尝试自动检测..."
        SAU_ROOT=""
    fi
fi
if [ -z "$PY" ]; then
    FOUND="$(detect_sau)"
    if [ -n "$FOUND" ]; then
        info "自动检测到 social-auto-upload：$FOUND"
        export SAU_ROOT="$FOUND"
        PY="$FOUND/.venv/bin/python"
    else
        if [ "$CHECK_MODE" = "1" ]; then
            print_manual_install_hint
            exit 1
        fi
        warn "未检测到 social-auto-upload (SAU) 引擎。"
        if [ -t 0 ] && [ -z "$OMP_SKIP_SAU_INSTALL" ]; then
            INSTALL_ANS=""
            read -r -p "是否现在自动安装到 ${SAU_DEFAULT_DIR}？[Y/n] " INSTALL_ANS
            case "$INSTALL_ANS" in
                n|N|no|NO) INSTALL_SAU=0 ;;
                *) INSTALL_SAU=1 ;;
            esac
        else
            INSTALL_SAU=0
            warn "非交互环境，跳过自动安装。"
        fi
        if [ "$INSTALL_SAU" = "1" ]; then
            install_sau "$SAU_DEFAULT_DIR"
            PY="$SAU_DEFAULT_DIR/.venv/bin/python"
        fi
    fi
fi

if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    print_manual_install
    exit 1
fi

# ── --check：只打印环境检测结果 ──
if [ "$CHECK_MODE" = "1" ]; then
    echo "=========================================================="
    echo "✅ SAU 引擎已就绪"
    echo "   SAU_ROOT   = ${SAU_ROOT}"
    echo "   Python     = ${PY}"
    if [ -x "$SAU_ROOT/.venv/bin/sau" ]; then
        echo "   sau CLI    = $("$SAU_ROOT/.venv/bin/sau" --version 2>/dev/null || echo "存在（版本信息不可用）")"
    else
        echo "   sau CLI    : 未找到（部分平台走源码导入，不影响控制台启动）"
    fi
    echo "   Cookie 目录 = ${SAU_ROOT}/cookies/"
    echo "   已登录 Cookie = $(ls "${SAU_ROOT}"/cookies/*_default.json 2>/dev/null | wc -l | tr -d ' ') 个"
    echo "=========================================================="
    exit 0
fi

# ── 补全控制台依赖（若 SAU venv 缺 flask / browser_cookie3 则静默安装）──
"$PY" -c "import flask, browser_cookie3" 2>/dev/null || "$PY" -m pip install -q flask browser_cookie3

echo "=========================================================="
echo "🚀 正在启动 Open Matrix Publisher 可视化 Web 控制台..."
echo "=========================================================="
echo "🌐 后端 API 服务运行于 http://localhost:5001"
echo "💻 即将自动打开 Web 控制台页面..."
echo "提示：按 Ctrl+C 可停止控制台服务"
echo "----------------------------------------------------------"

# 1.5 秒后自动打开浏览器（macOS 用 open，Linux 用 xdg-open，其它平台仅提示）
( sleep 1.5; if command -v open >/dev/null 2>&1; then open "http://localhost:5001"; elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://localhost:5001"; fi ) &

"$PY" local_bridge_server.py