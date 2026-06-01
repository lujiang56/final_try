"""突击计划生成器 — 根据考点和剩余时间生成三阶段计划"""

from datetime import datetime, date
from database import (
    get_exam, get_knowledge_points, clear_plan_tasks, add_plan_task, get_sections
)


def generate_plan(exam_id: int):
    """
    为一个科目生成三阶段突击计划。

    Phase 1 (40%): 真题套路解析 → "必拿"考点
    Phase 2 (35%): 中等强度练习 → "争取"考点
    Phase 3 (25%): 错题回顾 + 考前速记
    """
    exam = get_exam(exam_id)
    if not exam:
        return None

    clear_plan_tasks(exam_id)

    kps = get_knowledge_points(exam_id)
    sections = get_sections(exam_id)

    # 计算可用时间
    days_left = _calc_days_left(exam.get('exam_date', ''))
    hours_per_day = exam.get('daily_hours', 4)
    total_hours = max(days_left * hours_per_day, 2)  # 最少2小时
    total_minutes = total_hours * 60

    # 三阶段时间分配
    phase1_minutes = int(total_minutes * 0.40)
    phase2_minutes = int(total_minutes * 0.35)
    phase3_minutes = int(total_minutes * 0.25)

    sort_order = 0

    # ── Phase 1: 必拿考点 → 真题套路解析 ──
    must_kps = [kp for kp in kps if kp['raid_value'] == '必拿']
    if must_kps:
        per_kp_min = max(phase1_minutes // len(must_kps), 15)
        for kp in must_kps:
            add_plan_task(exam_id, 1,
                          f'【{kp["chapter"]}】真题套路解析 — 做3道典型题，总结解题SOP',
                          per_kp_min, priority=10, sort_order=sort_order)
            sort_order += 1
            add_plan_task(exam_id, 1,
                          f'【{kp["chapter"]}】默写核心公式 + 快速刷5道同类题巩固',
                          per_kp_min, priority=8, sort_order=sort_order)
            sort_order += 1
    else:
        # 没有必拿考点 → 先梳理框架
        add_plan_task(exam_id, 1,
                      '快速浏览所有章节框架，建立知识地图（只看标题和公式）',
                      max(phase1_minutes // 2, 20), priority=5, sort_order=sort_order)
        sort_order += 1

    # ── Phase 2: 争取考点 → 中等强度练习 ──
    try_kps = [kp for kp in kps if kp['raid_value'] == '争取']
    if try_kps:
        per_kp_min = max(phase2_minutes // len(try_kps), 10)
        for kp in try_kps:
            add_plan_task(exam_id, 2,
                          f'【{kp["chapter"]}】做2道经典题，理解核心解法',
                          per_kp_min, priority=5, sort_order=sort_order)
            sort_order += 1
    else:
        add_plan_task(exam_id, 2,
                      '对Phase1的必拿考点做第二轮强化，提高解题速度和准确率',
                      phase2_minutes, priority=5, sort_order=sort_order)
        sort_order += 1

    # 按题型做专项训练
    active_sections = [s for s in sections if s.get('score', 0) > 0]
    if active_sections:
        for sec in sorted(active_sections, key=lambda s: s.get('score', 0), reverse=True)[:3]:
            add_plan_task(exam_id, 2,
                          f'【{sec["section_label"]}专项】限时刷10道{sec["section_label"]}，目标正确率80%',
                          max(phase2_minutes // max(len(active_sections), 1), 15),
                          priority=6, sort_order=sort_order)
            sort_order += 1

    # ── Phase 3: 考前冲刺 ──
    add_plan_task(exam_id, 3,
                  '翻一遍所有真题错题，重做错题（限时完成）',
                  max(phase3_minutes // 4, 15), priority=9, sort_order=sort_order)
    sort_order += 1
    add_plan_task(exam_id, 3,
                  '默写核心公式清单 + 关键词速记卡（A4纸默写法）',
                  max(phase3_minutes // 4, 15), priority=9, sort_order=sort_order)
    sort_order += 1
    add_plan_task(exam_id, 3,
                  '限时模拟考1套完整卷子（严格计时，模拟考场压力）',
                  max(phase3_minutes // 2, 30), priority=10, sort_order=sort_order)
    sort_order += 1
    add_plan_task(exam_id, 3,
                  '考前最后浏览：选择题蒙题口诀 + 大题解题SOP回顾',
                  max(phase3_minutes // 4, 10), priority=7, sort_order=sort_order)

    # ── 每日节奏建议 ──
    if days_left >= 3:
        add_plan_task(exam_id, 0,
                      f'🕐 每日节奏建议：上午重点攻克(2h) → 下午刷题(1.5h) → 晚上回顾+错题(0.5h)',
                      0, priority=0, sort_order=999)

    return get_knowledge_points(exam_id)  # Return refreshed KPs


def _calc_days_left(exam_date_str: str) -> int:
    """计算距考试还有多少天"""
    if not exam_date_str:
        return 3  # 默认3天
    try:
        exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        days = (exam_date - date.today()).days
        return max(days, 1)  # 最少1天
    except ValueError:
        return 3
