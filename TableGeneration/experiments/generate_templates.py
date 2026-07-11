"""
Generate 50+ table templates via a single LLM API call.
Each template: domain, scenario, topic, headers, group_headers, row_headers.

Usage:
  # Default: 50 templates, topics NOT constrained to "telecommunications"
  python generate_templates.py --output templates.json

  # With domain constraint
  python generate_templates.py --domain medical --output templates_medical.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.tools.adapters.llm_header_client import LLMHeaderClient
from agents.tools.adapters.llm_topic_client import LLMTopicClient

DEFAULT_PROMPT = """You are a table template generator. Generate {count} diverse table templates.
Each template must be a JSON object with these fields:
- domain: industry domain (telecommunications, medical, finance, education, logistics, manufacturing, retail, energy, agriculture, hospitality)
- semantic_scenario: specific business scenario name (snake_case)
- topic: Chinese table title (8-20 chars)
- headers: list of 4-8 Chinese column header names
- group_headers: list of 2-4 Chinese group header names (for complex tables)
- row_headers: list of 4-6 Chinese row header names

Rules:
1. Cover AT LEAST 6 different domains across the {count} templates
2. Each template has a unique topic (no duplicates)
3. Headers must be diverse and realistic for the domain
4. Return a JSON array of {count} objects, nothing else
5. Use ONLY Chinese for header/topic/row_header values

Example template:
{{
    "domain": "medical",
    "semantic_scenario": "outpatient_statistics",
    "topic": "2024年第一季度门诊记录汇总",
    "headers": ["患者ID", "诊断结果", "科室", "主治医生", "医疗费用", "报销比例"],
    "group_headers": ["患者信息", "诊疗信息", "费用信息"],
    "row_headers": ["P001", "P002", "P003", "P004", "P005"]
}}
"""

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50, help="Number of templates to generate")
    parser.add_argument("--output", type=Path, default=Path("templates.json"),
                        help="Output JSON path")
    parser.add_argument("--domain", type=str, default=None,
                        help="Constrain to a single domain (omit for multi-domain)")
    return parser.parse_args()


def main():
    args = parse_args()

    # Build prompt
    count = args.count
    prompt = DEFAULT_PROMPT.format(count=count)
    if args.domain:
        prompt = prompt.replace(
            "Cover AT LEAST 6 different domains across the {count} templates".format(count=count),
            f"All templates must be in the '{args.domain}' domain"
        )

    # Use HEADER client (cheap/fast model) since we're generating headers
    client = LLMHeaderClient(
        api_key=None,  # Will load from .env
        base_url=None,
        model=None,
        system_prompt=None,
    )

    print(f"Generating {count} templates via LLM...")
    print(f"  Model: {client.model or 'Auto (from .env)'}")
    print(f"  API:   {client.base_url or 'Auto (from .env)'}")
    print()

    try:
        result = client._chat_completion(prompt, temperature=0.9)
    except Exception as e:
        print(f"API call failed: {e}")
        print("\nFallback: using hardcoded templates instead.")
        result = _fallback_templates(count, args.domain)

    # Parse response (fallback returns list, API returns string)
    if isinstance(result, list):
        templates = result
    else:
        templates = _parse_templates(result, count, args.domain)
    if not templates:
        print("Parsing failed, using fallback templates.")
        templates = _fallback_templates(count, args.domain)

    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(templates, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nSaved {len(templates)} templates to {args.output}")

    # Summary
    domains = set(t["domain"] for t in templates)
    print(f"Domains covered: {sorted(domains)}")
    print(f"Sample template: {json.dumps(templates[0], ensure_ascii=False)}")


def _parse_templates(raw, expected_count, domain_constraint):
    """Parse LLM response into template list."""
    if not raw:
        return []

    text = raw.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        import re
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return []
        else:
            return []

    if not isinstance(data, list):
        data = [data]

    # Validate and clean
    validated = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if not item.get("headers") or not isinstance(item["headers"], list):
            continue
        if domain_constraint and item.get("domain") != domain_constraint:
            item["domain"] = domain_constraint
        validated.append({
            "domain": item.get("domain", "general"),
            "semantic_scenario": item.get("semantic_scenario", "custom_scenario"),
            "topic": item.get("topic", "数据汇总表"),
            "headers": [str(h).strip() for h in item["headers"] if h],
            "group_headers": [str(g).strip() for g in (item.get("group_headers") or []) if g],
            "row_headers": [str(r).strip() for r in (item.get("row_headers") or []) if r],
        })

    return validated


def _fallback_templates(count, domain):
    """Hardcoded fallback if API is unavailable."""
    templates = []
    domains = {
        "telecommunications": [
            {"scenario": "base_station_maintenance", "topic": "基站巡检与告警处理记录",
             "headers": ["基站编号", "所属区域", "巡检日期", "告警次数", "处理时长", "维护人员", "维护状态"],
             "group": ["站点信息", "巡检记录", "告警处理"], "row": ["宏站A", "宏站B", "室分点", "边缘站"]},
            {"scenario": "broadband_installation", "topic": "宽带装机与故障修复统计",
             "headers": ["装机区域", "预约量", "完成量", "超时单", "修复时长", "客户评分"],
             "group": ["区域信息", "装机进度", "服务评价"], "row": ["东区", "西区", "南区", "北区"]},
        ],
        "medical": [
            {"scenario": "outpatient_records", "topic": "门诊就诊记录汇总",
             "headers": ["患者ID", "诊断结果", "科室", "主治医生", "医疗费用", "报销比例"],
             "group": ["患者信息", "诊疗信息", "费用信息"], "row": ["P001", "P002", "P003", "P004"]},
            {"scenario": "drug_inventory", "topic": "药品库存与消耗统计",
             "headers": ["药品编码", "药品名称", "库存数量", "月消耗量", "供应商", "有效期"],
             "group": ["药品信息", "库存信息", "供应信息"], "row": ["D001", "D002", "D003", "D004"]},
        ],
        "finance": [
            {"scenario": "budget_execution", "topic": "部门预算执行情况表",
             "headers": ["部门", "年度预算", "已支出", "执行率", "剩余额度", "负责人"],
             "group": ["部门信息", "预算信息", "执行情况"], "row": ["研发部", "市场部", "运营部", "财务部"]},
        ],
        "education": [
            {"scenario": "exam_scores", "topic": "期末考试成绩汇总表",
             "headers": ["学号", "姓名", "班级", "语文", "数学", "英语", "总分", "排名"],
             "group": ["基本信息", "各科成绩", "综合"], "row": ["S001", "S002", "S003", "S004"]},
        ],
        "logistics": [
            {"scenario": "warehouse_inventory", "topic": "仓库库存与周转统计",
             "headers": ["仓库编号", "存储区域", "货品种类", "库存量", "周转率", "盘点日期"],
             "group": ["仓库信息", "库存信息", "运营数据"], "row": ["WH001", "WH002", "WH003", "WH004"]},
        ],
    }

    domain_list = [domain] if domain else list(domains.keys())
    i = 0
    while len(templates) < count:
        d = domain_list[i % len(domain_list)]
        templates_in_domain = domains.get(d, domains["telecommunications"])
        t = templates_in_domain[i // len(domain_list) % len(templates_in_domain)]
        suffix = (i // (len(domain_list) * len(templates_in_domain))) + 1
        templates.append({
            "domain": d,
            "semantic_scenario": t["scenario"],
            "topic": f"{t['topic']}（{suffix}）" if suffix > 1 else t["topic"],
            "headers": list(t["headers"]),
            "group_headers": list(t["group"]),
            "row_headers": list(t["row"]),
        })
        i += 1
    return templates


if __name__ == "__main__":
    main()
