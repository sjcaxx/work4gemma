#!/usr/bin/env bash
# 一键恢复本地开发环境：venv + 依赖 + 外部仓库克隆 + mini_repo git 初始化
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> 项目根目录: $ROOT"

# 1. Python venv
if [ ! -d .venv ]; then
  echo "==> 创建 venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> 安装依赖"
pip install -q --upgrade pip
pip install -q networkx numpy pytest pytest-asyncio \
  "markdown-it-py>=2.2.0" "pygments>=2.13.0,<3.0.0" attrs

# 2. 外部仓库（不纳入本仓库版本控制）
mkdir -p examples/repos examples/refs

if [ ! -d examples/repos/rich/.git ]; then
  echo "==> 克隆 rich（含完整历史，供 benchmark 挖任务）"
  git clone -q https://github.com/Textualize/rich.git examples/repos/rich
fi

clone_ref() {
  local name="$1" url="$2"
  if [ ! -d "examples/refs/$name/.git" ]; then
    echo "==> 克隆参考仓库 $name"
    git clone -q --depth 1 "$url" "examples/refs/$name"
  fi
}
clone_ref Gemma-coding-agent        https://github.com/JGM-droid/Gemma-coding-agent.git
clone_ref gemma4-graph-toolkit-audit https://github.com/Yuxiang-Ren-HUB/gemma4-graph-toolkit-audit.git
clone_ref gemma4-swe-harness-audit   https://github.com/bsw0610/gemma4-swe-harness-audit.git

# 3. mini_repo 的 git（测试需要干净的 base commit）
if [ ! -d examples/mini_repo/.git ]; then
  echo "==> 初始化 examples/mini_repo git"
  git -C examples/mini_repo init -q
  git -C examples/mini_repo add -A
  git -C examples/mini_repo -c user.email=dev@local -c user.name=dev \
    commit -qm "base: mini_repo 初始状态"
fi

echo
echo "==> 完成。验证:"
echo "    source .venv/bin/activate"
echo "    python examples/test_tools.py"
echo "    python bench/run_eval.py --oracle"
