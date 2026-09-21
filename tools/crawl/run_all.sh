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
# 注：JS 渲染页面（统计局/人社局智能云搜索、政民互动答复页）用 browser_fetch.py 单独取
python stage7_national.py
python stage9_calendar.py
python stage10_beijing_params.py
python stage11_injury_params.py
python stage13_national_income.py
python stage15_beijing_yearbook.py
python stage16_beijing_2024_estimate.py
python stage14_cap_basis_evidence.py
python stage17_working_hours_regs.py
python stage18_beijing_social_insurance.py
python stage19_shanxi_social_insurance.py
python stage6_indexes.py
python verify.py
