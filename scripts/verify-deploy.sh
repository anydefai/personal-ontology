#!/bin/bash
# 校验"已安装副本"与"工作区源码"是否一致。
#
#   scripts/verify-deploy.sh [已安装目录]     默认 ~/personal-ontology
#
# 动机：多次出现"源码改了但没同步到已装目录"，导致改动看起来没生效；也曾因文档被覆盖
#      而未被发现（docs 原先不在校验范围内）。
#      （例如界面导航项、README、status.sh）。
set -u
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DST="${1:-$HOME/personal-ontology}"
status=0
if [ ! -d "$DST" ]; then echo "找不到已安装目录：$DST"; exit 2; fi
for sub in backend web ontology docs schemas; do
  [ -d "$SRC/$sub" ] || continue
  for f in "$SRC/$sub"/*; do
    [ -f "$f" ] || continue
    b="$(basename "$f")"
    case "$b" in *.pyc) continue ;; esac
    if [ ! -f "$DST/$sub/$b" ]; then
      echo "  缺失：$sub/$b"; status=1
    elif ! diff -q "$f" "$DST/$sub/$b" >/dev/null 2>&1; then
      echo "  不一致：$sub/$b"; status=1
    fi
  done
done
if [ "$status" -eq 0 ]; then
  echo "✔ 已安装副本与工作区源码一致"
else
  echo "⚠ 存在差异：请同步（重跑 install.sh，或复制上述文件）"
  echo "  提示：后端改动同步后需重启 —— launchctl kickstart -k gui/\$(id -u)/personalontology.personal-ontology.backend"
fi
exit "$status"
