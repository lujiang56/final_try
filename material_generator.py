"""复习资料生成引擎 — 基于考点+错题+计划生成结构化复习资料"""

import re
from datetime import datetime
from database import (
    get_exam, get_knowledge_points, get_mistakes, get_plan_tasks,
    create_material
)


def generate_summary(exam_id: int) -> str:
    """
    生成按章节组织的复习总结 HTML。

    Returns:
        结构化HTML字符串，包含章节分组、考点详情和突击建议
    """
    exam = get_exam(exam_id)
    if not exam:
        return '<p class="text-muted">科目不存在</p>'

    kps = get_knowledge_points(exam_id)
    if not kps:
        return '<p class="text-muted">还没有考点数据，请先上传PPT或粘贴真题进行分析。</p>'

    # 按章节分组
    chapters = {}
    for kp in kps:
        ch = kp['chapter'] or '未分类'
        if ch not in chapters:
            chapters[ch] = []
        chapters[ch].append(kp)

    # 统计
    must_count = sum(1 for k in kps if k['raid_value'] == '必拿')
    try_count = sum(1 for k in kps if k['raid_value'] == '争取')
    skip_count = sum(1 for k in kps if k['raid_value'] == '可弃')
    total_score_impact = sum(k['score_impact'] for k in kps)

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    # 构建HTML
    parts = []
    parts.append(f'''
    <div class="review-material">
        <div class="material-header mb-4 border-bottom pb-3">
            <h3>{exam['name']} — 复习总结</h3>
            <p class="text-muted mb-1">
                生成时间: {now_str} | 共 {len(kps)} 个考点 | 覆盖 {total_score_impact:.0f} 分
            </p>
            <p class="text-muted small">
                目标 {exam['target_score']} 分 | 每日 {exam['daily_hours']}h |
                考试日期 {exam['exam_date'] or '待定'}
            </p>
            {f'<p class="small text-muted">{exam["notes"]}</p>' if exam.get('notes') else ''}
        </div>
    ''')

    # 突击价值总览
    parts.append(f'''
        <div class="row g-3 mb-4 text-center">
            <div class="col-4">
                <div class="border rounded p-3 bg-danger-subtle">
                    <div class="fs-3 fw-bold text-danger">{must_count}</div>
                    <small class="text-muted">必拿考点</small>
                </div>
            </div>
            <div class="col-4">
                <div class="border rounded p-3 bg-warning-subtle">
                    <div class="fs-3 fw-bold text-warning">{try_count}</div>
                    <small class="text-muted">争取考点</small>
                </div>
            </div>
            <div class="col-4">
                <div class="border rounded p-3 bg-light">
                    <div class="fs-3 fw-bold text-secondary">{skip_count}</div>
                    <small class="text-muted">可弃考点</small>
                </div>
            </div>
        </div>
    ''')

    # 按章节展开
    for chapter, chapter_kps in chapters.items():
        chapter_score = sum(k['score_impact'] for k in chapter_kps)
        raid_class = 'border-danger' if any(k['raid_value'] == '必拿' for k in chapter_kps) else \
                     'border-warning' if any(k['raid_value'] == '争取' for k in chapter_kps) else \
                     'border-secondary'

        parts.append(f'''
        <div class="chapter-block mb-4 p-3 border rounded {raid_class}" style="border-left:4px solid;">
            <h5 class="chapter-title">
                {chapter}
                <span class="badge bg-secondary ms-2">{len(chapter_kps)} 考点</span>
                <small class="text-muted ms-2">约 {chapter_score:.0f} 分</small>
            </h5>
            <div class="row g-3 mt-2">
        ''')

        for kp in chapter_kps:
            raid_color = {
                '必拿': 'border-danger bg-danger bg-opacity-10',
                '争取': 'border-warning bg-warning bg-opacity-10',
                '可弃': 'border-secondary bg-light'
            }.get(kp['raid_value'], 'border-secondary bg-light')

            mastered_badge = '✅ 已掌握' if kp['is_mastered'] else '⬜ 待攻克'
            mastery_class = 'text-success' if kp['is_mastered'] else 'text-muted'

            parts.append(f'''
                <div class="col-md-6">
                    <div class="p-2 border-start border-3 {raid_color} rounded-end">
                        <strong>{kp['topic']}</strong>
                        <span class="small {mastery_class} ms-1">{mastered_badge}</span>
                        <div class="small text-muted mt-1">
                            出现 {kp['frequency']} 次 |
                            预估 {kp['score_impact']} 分 |
                            难度 {'⭐' * kp['difficulty']}
                            <span class="badge ms-1
                                {"bg-danger" if kp['raid_value'] == '必拿' else
                                 "bg-warning text-dark" if kp['raid_value'] == '争取' else
                                 "bg-light text-dark"}">
                                {kp['raid_value']}
                            </span>
                        </div>
                    </div>
                </div>
            ''')

        parts.append('</div></div>')

    # 突击策略建议
    parts.append(f'''
        <hr>
        <div class="strategy-section mt-4">
            <h5>突击策略建议</h5>
            <div class="row g-3 mt-2">
    ''')

    if must_count > 0:
        parts.append(f'''
            <div class="col-md-4">
                <div class="card border-danger">
                    <div class="card-header bg-danger-subtle">Phase 1 — 必拿 ({must_count}个)</div>
                    <div class="card-body small">
                        <p class="mb-1">✅ 优先攻克，确保得分</p>
                        <p class="mb-1">✅ 做至少3道真题/每个考点</p>
                        <p class="mb-1">✅ 总结解题SOP模板</p>
                        <p class="mb-0">预计投入 <strong>40%</strong> 时间</p>
                    </div>
                </div>
            </div>
        ''')

    if try_count > 0:
        parts.append(f'''
            <div class="col-md-4">
                <div class="card border-warning">
                    <div class="card-header bg-warning-subtle">Phase 2 — 争取 ({try_count}个)</div>
                    <div class="card-body small">
                        <p class="mb-1">🔶 在必拿之后攻克</p>
                        <p class="mb-1">🔶 每考点做2道典型题</p>
                        <p class="mb-1">🔶 掌握核心解法即可</p>
                        <p class="mb-0">预计投入 <strong>35%</strong> 时间</p>
                    </div>
                </div>
            </div>
        ''')

    parts.append(f'''
            <div class="col-md-4">
                <div class="card border-secondary">
                    <div class="card-header bg-light">Phase 3 — 冲刺</div>
                    <div class="card-body small">
                        <p class="mb-1">📋 错题重做回顾</p>
                        <p class="mb-1">📋 默写核心公式清单</p>
                        <p class="mb-1">📋 限时模拟考1套</p>
                        <p class="mb-0">预计投入 <strong>25%</strong> 时间</p>
                    </div>
                </div>
            </div>
    ''')

    parts.append('</div></div>')

    # 错题统计(如果有)
    mistakes = get_mistakes(exam_id)
    if mistakes:
        reviewed = sum(1 for m in mistakes if m['reviewed'])
        parts.append(f'''
        <hr>
        <div class="mt-4">
            <h5>错题统计</h5>
            <p class="text-muted small">
                共 {len(mistakes)} 道错题 | 已复习 {reviewed} 道 |
                剩余 {len(mistakes) - reviewed} 道待攻克
            </p>
        </div>
        ''')

    parts.append('</div>')
    return '\n'.join(parts)


def generate_cheatsheet(exam_id: int) -> str:
    """
    生成考前速查表 — 紧凑单页排版，适合考前快速浏览。

    Returns:
        紧凑HTML字符串
    """
    exam = get_exam(exam_id)
    if not exam:
        return '<p class="text-muted">科目不存在</p>'

    kps = get_knowledge_points(exam_id)
    if not kps:
        return '<p class="text-muted">还没有考点数据。</p>'

    must_kps = [k for k in kps if k['raid_value'] == '必拿']
    try_kps = [k for k in kps if k['raid_value'] == '争取']

    now_str = datetime.now().strftime('%m/%d %H:%M')
    parts = []

    parts.append(f'''
    <div class="review-material">
        <div class="material-header mb-3 border-bottom pb-2">
            <h4>{exam['name']} — 考前速查表</h4>
            <small class="text-muted">{now_str} | 目标 {exam['target_score']} 分</small>
        </div>
    ''')

    if must_kps:
        parts.append('''
        <div class="mb-4">
            <h5 class="text-danger">必拿考点 TOP</h5>
            <table class="table table-sm table-bordered">
                <thead><tr><th>章节</th><th>知识点</th><th>分值</th><th>掌握</th></tr></thead>
                <tbody>
        ''')
        for kp in must_kps[:10]:
            state = '已掌握' if kp['is_mastered'] else '待攻克'
            parts.append(
                f'<tr><td>{kp["chapter"]}</td><td>{kp["topic"]}</td>'
                f'<td>{kp["score_impact"]}分</td><td>{state}</td></tr>'
            )
        parts.append('</tbody></table></div>')

    if try_kps:
        parts.append('''
        <div class="mb-4">
            <h5 class="text-warning">争取考点</h5>
            <table class="table table-sm table-bordered">
                <thead><tr><th>章节</th><th>知识点</th><th>分值</th></tr></thead>
                <tbody>
        ''')
        for kp in try_kps[:10]:
            parts.append(
                f'<tr><td>{kp["chapter"]}</td><td>{kp["topic"]}</td>'
                f'<td>{kp["score_impact"]}分</td></tr>'
            )
        parts.append('</tbody></table></div>')

    # 错题速查
    mistakes = get_mistakes(exam_id)
    unreviewed = [m for m in mistakes if not m['reviewed']]
    if unreviewed:
        parts.append('''
        <div class="mb-4">
            <h5>待复习错题摘要</h5>
            <div class="list-group list-group-flush">
        ''')
        for m in unreviewed[:5]:
            reason_tag = f'<span class="badge bg-secondary ms-1">{m["reason"]}</span>' if m['reason'] else ''
            parts.append(
                f'<div class="list-group-item small py-1 px-0 border-0">'
                f'Q: {m["question"][:100]}{"..." if len(m.get("question","") or "")>100 else ""}'
                f'{reason_tag}</div>'
            )
        parts.append('</div></div>')

    # 计划任务汇总
    tasks = get_plan_tasks(exam_id)
    if tasks:
        done = sum(1 for t in tasks if t['is_done'])
        parts.append(f'''
        <div class="alert alert-light border small">
            <strong>进度:</strong> {done}/{len(tasks)} 任务已完成 ({int(done/max(len(tasks),1)*100)}%)
        </div>
        ''')

    parts.append('</div>')
    return '\n'.join(parts)


def generate_flashcards(exam_id: int) -> str:
    """
    基于错题记录生成 Q&A 闪卡。

    Returns:
        HTML字符串，正反面闪卡布局
    """
    exam = get_exam(exam_id)
    if not exam:
        return '<p class="text-muted">科目不存在</p>'

    mistakes = get_mistakes(exam_id)
    if not mistakes:
        return '<p class="text-muted">还没有错题记录，请先添加错题。</p>'

    # 只使用有正确答案的错题
    valid = [m for m in mistakes if m.get('correct_answer')]
    if not valid:
        return '<p class="text-muted">错题中还没有填写正确答案，请先在考点管理页面补充。</p>'

    now_str = datetime.now().strftime('%Y-%m-%d')
    parts = []

    parts.append(f'''
    <div class="review-material">
        <div class="material-header mb-4">
            <h4>{exam['name']} — 错题闪卡</h4>
            <p class="text-muted small">{now_str} | 共 {len(valid)} 张卡片 | {sum(1 for m in valid if m['reviewed'])} 张已复习</p>
        </div>
        <div class="row g-3">
    ''')

    for i, m in enumerate(valid):
        reviewed_border = 'border-success bg-success-subtle' if m['reviewed'] else 'border'
        parts.append(f'''
            <div class="col-md-6">
                <div class="card {reviewed_border}">
                    <div class="card-header small">
                        <span class="fw-bold">卡片 #{i+1}</span>
                        {'<span class="badge bg-success ms-2">已复习</span>' if m['reviewed'] else ''}
                        {f'<span class="badge bg-secondary ms-1">{m["reason"]}</span>' if m.get('reason') else ''}
                    </div>
                    <div class="card-body p-3">
                        <div class="mb-2">
                            <small class="text-muted">Q:</small>
                            <p class="mb-2">{m['question'][:200]}{'...' if (m.get('question') or '')|length>200 else ''}</p>
                        </div>
                        <div class="border-top pt-2">
                            <small class="text-success fw-bold">A: {m['correct_answer']}</small>
                            {f'<br><small class="text-danger">你的答案: {m["wrong_answer"]}</small>' if m.get('wrong_answer') else ''}
                            {f'<br><small class="text-muted">知识点: {m["knowledge_tag"]}</small>' if m.get('knowledge_tag') else ''}
                        </div>
                    </div>
                </div>
            </div>
        ''')

    parts.append('</div></div>')
    return '\n'.join(parts)


def _strip_html(html_text: str) -> str:
    """将HTML转为纯文本，用于下载"""
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', html_text)
    # 压缩多余空白
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = text.strip()
    return text


def generate_material(exam_id: int, material_type: str = 'summary',
                      is_from_ppt: bool = False, source_file_id: int = None) -> int:
    """
    主入口：生成复习资料并保存到数据库。

    Args:
        exam_id: 科目ID
        material_type: 'summary' | 'cheatsheet' | 'flashcards'
        is_from_ppt: 是否来自PPT分析
        source_file_id: 来源文件ID(如果is_from_ppt=True)

    Returns:
        新建的 review_material.id
    """
    exam = get_exam(exam_id)
    if not exam:
        return 0

    # 根据类型选择生成函数
    generators = {
        'summary': generate_summary,
        'cheatsheet': generate_cheatsheet,
        'flashcards': generate_flashcards,
    }
    generate_fn = generators.get(material_type, generate_summary)

    content_html = generate_fn(exam_id)
    content_text = _strip_html(content_html)

    # 生成标题
    type_labels = {
        'summary': '复习总结',
        'cheatsheet': '考前速查表',
        'flashcards': '错题闪卡',
    }
    material_title = f'{exam["name"]} — {type_labels.get(material_type, "资料")}'

    return create_material(
        exam_id=exam_id,
        title=material_title,
        material_type=material_type,
        content_html=content_html,
        content_text=content_text,
        is_from_ppt=1 if is_from_ppt else 0,
        source_file_id=source_file_id
    )
