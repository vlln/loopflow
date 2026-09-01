#!/usr/bin/env bash
# rerun_demo_loop 探针：第一次运行失败（fail-flag 存在时 exit 1 并清 flag），
# 之后成功。配合 workflow 的 validate() 演示 rerun_loop 回退。
set -u
FLAG="${1:-fail-flag.txt}"
if [ -f "$FLAG" ]; then
  rm -f "$FLAG"
  echo "FAIL-ONCE: flag present, failing this run" >&2
  exit 1
fi
echo "rerun_probe OK"
exit 0
