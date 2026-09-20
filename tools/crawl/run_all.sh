#!/usr/bin/env bash
# 顺序执行公开资料抓取与索引生成（国家层面 + 北京，幂等，可重复运行）
set -euo pipefail
cd "$(dirname "$0")"
export LABOR_LAWYER_REPO="${LABOR_LAWYER_REPO:-$(cd ../.. && pwd)}"

echo "repo  = $LABOR_LAWYER_REPO"
python stage1_templates_manuals.py
python stage2_institutions.py
python stage3_cases.py
python stage4_regs.py
python stage4b_cases_gov.py
python stage5_guidance.py
python stage7_national.py
python stage6_indexes.py
python verify.py
