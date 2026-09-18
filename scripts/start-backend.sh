#!/bin/bash
# ============================================
# 启动 FastAPI 后端开发服务
#
# 使用方法:
#   ./scripts/start-backend.sh
#
# 功能:
#   - 自动检测并激活 conda 环境（mylearn）
#   - 检查依赖是否安装
#   - 以自动重载模式启动 uvicorn
# ============================================

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# ---- 检测 Python 环境 ----
PYTHON_BIN="python"

if command -v conda &> /dev/null; then
    source "$(conda info --base)/etc/profile.d/conda.sh"
    if conda env list | grep -q "^mylearn "; then
        conda activate mylearn
        PYTHON_BIN="python"
        echo "✅ 已激活 conda 环境: mylearn"
    else
        echo "⚠️  未找到 mylearn 环境，使用当前 Python 环境"
    fi
else
    echo "⚠️  未检测到 conda，使用当前 Python 环境"
fi

echo "   Python 路径: $(which $PYTHON_BIN)"
echo "   Python 版本: $($PYTHON_BIN --version 2>&1)"

# ---- 检查核心依赖 ----
if ! $PYTHON_BIN -c "import fastapi" &> /dev/null; then
    echo ""
    echo "⚠️  依赖可能未安装，建议先运行: pip install -r requirements.txt"
    echo ""
fi

# ---- 启动 ----
echo ""
echo "🚀 启动 FastAPI 服务..."
echo "   地址:    http://localhost:8000"
echo "   Swagger: http://localhost:8000/docs"
echo "   模式:    开发（自动重载）"
echo ""
echo "按 Ctrl+C 停止"
echo ""

exec $PYTHON_BIN -m uvicorn app_server:app --host 0.0.0.0 --port 8000 --reload
