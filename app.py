"""期末突击 Web 应用 — Flask 主入口"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
from database import (
    init_db, create_exam, get_all_exams, get_exam, update_exam, delete_exam,
    get_sections, update_section,
    get_knowledge_points, upsert_kp, toggle_kp_mastered, delete_kp,
    get_plan_tasks, clear_plan_tasks, toggle_plan_task,
    get_mistakes, add_mistake, toggle_mistake_reviewed, delete_mistake,
    get_exam_stats
)
from analyzer import analyze_materials, manual_add_kp
from planner import generate_plan
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'final-try-secret-2024'


@app.before_request
def setup():
    init_db()


# ─── 首页：快速诊断表单 ──────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', ''),
            'exam_date': request.form.get('exam_date', ''),
            'exam_type': request.form.get('exam_type', '闭卷'),
            'daily_hours': float(request.form.get('daily_hours', 4)),
            'risk_level': request.form.get('risk_level', 'medium'),
            'target_score': float(request.form.get('target_score', 60)),
            'current_score': request.form.get('current_score', '') or None,
            'credit_weight': float(request.form.get('credit_weight', 1)),
            'notes': request.form.get('notes', ''),
        }
        exam_id = create_exam(data)

        # 保存题型分值
        section_scores = request.form.getlist('section_score')
        section_counts = request.form.getlist('section_count')
        sections = get_sections(exam_id)
        for i, sec in enumerate(sections):
            if i < len(section_scores):
                update_section(sec['id'],
                               float(section_scores[i] or 0),
                               int(section_counts[i] or 0))

        return redirect(url_for('dashboard'))

    return render_template('index.html')


# ─── 仪表盘 ───────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    exams = get_all_exams()
    today = datetime.now().date()
    for exam in exams:
        eid = exam['id']
        # 计算天数
        try:
            ed = datetime.strptime(exam['exam_date'], '%Y-%m-%d').date()
            exam['days_left'] = (ed - today).days
        except (ValueError, TypeError):
            exam['days_left'] = '?'
        # 计算进度
        stats = get_exam_stats(eid)
        exam['kp_must'] = stats['kp_must']
        exam['kp_try'] = stats['kp_try']
        exam['kp_skip'] = stats['kp_skip']
        exam['tasks_total'] = stats['tasks_total']
        exam['tasks_done'] = stats['tasks_done']
        exam['progress'] = int(stats['tasks_done'] / max(stats['tasks_total'], 1) * 100)

    # 按优先级排序: P0(距考近+高风险) > P1 > P2
    def priority_key(e):
        d = e['days_left'] if isinstance(e['days_left'], int) else 999
        r = {'high': 0, 'medium': 1, 'low': 2}.get(e.get('risk_level', 'medium'), 1)
        return (d, r)
    exams.sort(key=priority_key)

    return render_template('dashboard.html', exams=exams)


# ─── 单科详情 ─────────────────────────────────────────────

@app.route('/exam/<int:exam_id>', methods=['GET', 'POST'])
def subject(exam_id):
    exam = get_exam(exam_id)
    if not exam:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # 更新题型分值
        section_ids = request.form.getlist('section_id')
        section_scores = request.form.getlist('section_score')
        section_counts = request.form.getlist('section_count')
        for i, sid in enumerate(section_ids):
            if i < len(section_scores):
                update_section(int(sid),
                               float(section_scores[i] or 0),
                               int(section_counts[i] or 0))
        return redirect(url_for('subject', exam_id=exam_id))

    sections = get_sections(exam_id)
    kps = get_knowledge_points(exam_id)
    mistakes = get_mistakes(exam_id)
    stats = get_exam_stats(exam_id)

    # 计算总分
    total_score = sum(s['score'] for s in sections)

    return render_template('subject.html',
                           exam=exam, sections=sections, kps=kps,
                           mistakes=mistakes, stats=stats, total_score=total_score)


# ─── 材料分析页面 ─────────────────────────────────────────

@app.route('/exam/<int:exam_id>/materials', methods=['GET', 'POST'])
def materials(exam_id):
    exam = get_exam(exam_id)
    if not exam:
        return redirect(url_for('dashboard'))

    result = None
    if request.method == 'POST':
        raw_text = request.form.get('raw_text', '')
        total_score = float(request.form.get('total_score', 100) or 100)

        if raw_text.strip():
            from analyzer import analyze_materials as am
            chapter_stats = am(exam_id, raw_text, total_score)
            result = chapter_stats

    kps = get_knowledge_points(exam_id)
    return render_template('materials.html', exam=exam, kps=kps, result=result)


# ─── 手动添加考点 ─────────────────────────────────────────

@app.route('/exam/<int:exam_id>/add_kp', methods=['POST'])
def add_kp(exam_id):
    chapter = request.form.get('chapter', '')
    topic = request.form.get('topic', '')
    difficulty = int(request.form.get('difficulty', 1))
    score_impact = float(request.form.get('score_impact', 0) or 0)
    frequency = int(request.form.get('frequency', 0) or 0)
    raid_value = request.form.get('raid_value', '争取')
    manual_add_kp(exam_id, chapter, topic, difficulty, score_impact, frequency, raid_value)
    return redirect(request.referrer or url_for('subject', exam_id=exam_id))


# ─── 切换考点掌握状态 ─────────────────────────────────────

@app.route('/exam/<int:exam_id>/kp/<int:kp_id>/toggle', methods=['POST'])
def kp_toggle(exam_id, kp_id):
    toggle_kp_mastered(kp_id)
    return redirect(request.referrer or url_for('subject', exam_id=exam_id))


# ─── 删除考点 ─────────────────────────────────────────────

@app.route('/exam/<int:exam_id>/kp/<int:kp_id>/delete', methods=['POST'])
def kp_delete(exam_id, kp_id):
    delete_kp(kp_id)
    return redirect(request.referrer or url_for('subject', exam_id=exam_id))


# ─── 突击计划页面 ─────────────────────────────────────────

@app.route('/exam/<int:exam_id>/plan')
def plan(exam_id):
    exam = get_exam(exam_id)
    if not exam:
        return redirect(url_for('dashboard'))

    tasks = get_plan_tasks(exam_id)
    if not tasks:
        generate_plan(exam_id)
        tasks = get_plan_tasks(exam_id)

    # 按阶段分组
    phase_tasks = {0: [], 1: [], 2: [], 3: []}
    for t in tasks:
        phase_tasks[t['phase']].append(t)

    # 计算进度
    total = len(tasks)
    done = sum(1 for t in tasks if t['is_done'])
    progress = int(done / max(total, 1) * 100)

    # 估算总时间
    total_minutes = sum(t['estimated_minutes'] for t in tasks)
    total_hours = total_minutes // 60
    remaining_min = total_minutes % 60

    return render_template('plan.html', exam=exam, phase_tasks=phase_tasks,
                           progress=progress, total=total, done=done,
                           total_hours=total_hours, remaining_min=remaining_min)


@app.route('/exam/<int:exam_id>/plan/regenerate', methods=['POST'])
def plan_regenerate(exam_id):
    generate_plan(exam_id)
    return redirect(url_for('plan', exam_id=exam_id))


@app.route('/exam/<int:exam_id>/plan/toggle/<int:task_id>', methods=['POST'])
def plan_toggle(exam_id, task_id):
    toggle_plan_task(task_id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True})
    return redirect(url_for('plan', exam_id=exam_id))


# ─── 错题管理 ─────────────────────────────────────────────

@app.route('/exam/<int:exam_id>/mistake', methods=['POST'])
def mistake_add(exam_id):
    question = request.form.get('question', '')
    wrong_answer = request.form.get('wrong_answer', '')
    correct_answer = request.form.get('correct_answer', '')
    reason = request.form.get('reason', '')
    knowledge_tag = request.form.get('knowledge_tag', '')
    add_mistake(exam_id, question, wrong_answer, correct_answer, reason, knowledge_tag)
    return redirect(request.referrer or url_for('subject', exam_id=exam_id))


@app.route('/exam/<int:exam_id>/mistake/<int:mid>/toggle', methods=['POST'])
def mistake_toggle(exam_id, mid):
    toggle_mistake_reviewed(mid)
    return redirect(request.referrer or url_for('subject', exam_id=exam_id))


@app.route('/exam/<int:exam_id>/mistake/<int:mid>/delete', methods=['POST'])
def mistake_delete(exam_id, mid):
    delete_mistake(mid)
    return redirect(request.referrer or url_for('subject', exam_id=exam_id))


# ─── 删除科目 ─────────────────────────────────────────────

@app.route('/exam/<int:exam_id>/delete', methods=['POST'])
def exam_delete(exam_id):
    delete_exam(exam_id)
    return redirect(url_for('dashboard'))


# ─── API ──────────────────────────────────────────────────

@app.route('/api/exam/<int:exam_id>/progress')
def api_progress(exam_id):
    stats = get_exam_stats(exam_id)
    return jsonify(stats)


# ─── 启动 ─────────────────────────────────────────────────

if __name__ == '__main__':
    print('期末突击助手已启动 -> http://localhost:5000')
    app.run(debug=True, host='0.0.0.0', port=5000)
