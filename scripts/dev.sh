#!/usr/bin/env bash
# 一键启动开发环境：后端 uvicorn + 前端 vite，并打印手机可访问的局域网地址。
#
# 用法（在仓库根目录）：bash scripts/dev.sh
#
# 端口已占用时会跳过对应的启动，而不是报错退出 —— 方便只重启其中一个。
# Ctrl+C 停止全部。

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# 虚拟环境位置，按优先级找：
#   1. backend/.venv —— uv sync 的标准产物（README 记录的布局）
#   2. .venv          —— 仓库根目录的旧布局，保留兼容
# Windows 下在 Scripts/，*nix 在 bin/
VENV_PY=""
for cand in \
  "$ROOT/backend/.venv/Scripts/python.exe" \
  "$ROOT/.venv/Scripts/python.exe" \
  "$ROOT/backend/.venv/bin/python" \
  "$ROOT/.venv/bin/python"
do
  if [ -x "$cand" ]; then VENV_PY="$cand"; break; fi
done

if [ -z "$VENV_PY" ]; then
  echo "找不到虚拟环境 python。" >&2
  echo "请先在 backend/ 下执行：uv sync" >&2
  exit 1
fi

# 局域网 IP。用 node 读网卡而不是 grep ipconfig：
# Windows 的 ipconfig 输出是 GBK，grep 中文关键字经常失灵。
# 排除 169.254.*（网卡没拿到 DHCP 时的自动地址，连不通）。
LAN_IP="$(node -e '
const os = require("os");
const hits = [];
for (const addrs of Object.values(os.networkInterfaces())) {
  for (const a of addrs || []) {
    if (a.family === "IPv4" && !a.internal && !a.address.startsWith("169.254.")) {
      hits.push(a.address);
    }
  }
}
console.log(hits[0] || "");
' 2>/dev/null)"

port_busy() {
  netstat -ano 2>/dev/null | grep -q ":$1 .*LISTENING"
}

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo
  echo "正在停止…"
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  wait 2>/dev/null
  echo "已停止。"
}
trap cleanup INT TERM

echo "=== 后端 uvicorn :$BACKEND_PORT ==="
echo "    虚拟环境 $VENV_PY"
if port_busy "$BACKEND_PORT"; then
  echo "    端口已占用，跳过（复用已在跑的实例）"
else
  # 显式绑 127.0.0.1：手机不需要直连后端 —— vite 在电脑本机把 /api 代理过去，
  # 所以这里不要改成 0.0.0.0，那样只会把后端也暴露到局域网。
  (cd "$ROOT/backend" && "$VENV_PY" -m uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT") &
  BACKEND_PID=$!
fi

echo "=== 前端 vite :$FRONTEND_PORT ==="
if port_busy "$FRONTEND_PORT"; then
  echo "    端口已占用，跳过（复用已在跑的实例）"
else
  (cd "$ROOT/frontend" && npm run dev) &
  FRONTEND_PID=$!
fi

# 等 vite 打印出监听地址，避免地址表比服务先出现
sleep 6

echo
echo "──────────────────────────────────────────────"
echo "  电脑访问   http://localhost:$FRONTEND_PORT"
if [ -n "$LAN_IP" ]; then
  echo "  手机访问   http://$LAN_IP:$FRONTEND_PORT"
  echo "            （手机连同一个 Wi-Fi，注意是 http 不是 https）"
else
  echo "  手机访问   未检测到局域网 IP，请手动执行 ipconfig 查看 IPv4 地址"
fi
echo "──────────────────────────────────────────────"
echo "  Ctrl+C 停止全部"
echo

wait
