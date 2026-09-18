#!/bin/bash
# ============================================
# 启动 Vue3 前端开发服务
#
# 使用方法:
#   ./scripts/start-frontend.sh
#
# 功能:
#   - 检查 Node.js 环境
#   - 首次启动自动安装依赖
#   - 以 HMR 热更新模式启动 Vite 开发服务器
# ============================================

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$PROJECT_ROOT/chat-web"

cd "$WEB_DIR"

# ---- 检查 Node ----
if ! command -v node &> /dev/null; then
    echo "❌ 未检测到 Node.js"
    echo "   请先安装 Node 20 LTS: https://nodejs.org/"
    echo "   注意：Node 24 与 esbuild 不兼容，建议使用 Node 20"
    exit 1
fi

NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
echo "📦 Node 版本: $(node --version)"
echo "📦 npm  版本: $(npm --version)"

if [ "$NODE_MAJOR" -ge 24 ]; then
    echo "⚠️  检测到 Node $NODE_MAJOR，可能与 esbuild 不兼容，建议降级到 Node 20"
fi

# ---- 安装依赖（首次） ----
if [ ! -d "node_modules" ]; then
    echo ""
    echo "📥 首次启动，安装依赖..."
    npm install
    echo "✅ 依赖安装完成"
fi

# ---- 启动 ----
echo ""
echo "🚀 启动 Vite 开发服务..."
echo "   地址:    http://localhost:5173"
echo "   API 代理: /chat, /agent -> http://localhost:8000"
echo "   模式:    开发（HMR 热更新）"
echo ""
echo "按 Ctrl+C 停止"
echo ""

exec npm run dev
