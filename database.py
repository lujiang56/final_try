"""SQLite 数据库初始化和 CRUD 操作"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'final_try.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS exam (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            exam_date TEXT,
            exam_type TEXT DEFAULT '闭卷',
            daily_hours REAL DEFAULT 4,
            risk_level TEXT DEFAULT 'medium',
            target_score REAL DEFAULT 60,
            current_score REAL,
            credit_weight REAL DEFAULT 1,
            priority INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exam_section (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER REFERENCES exam(id) ON DELETE CASCADE,
            section_type TEXT,
            section_label TEXT,
            score REAL DEFAULT 0,
            count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS knowledge_point (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER REFERENCES exam(id) ON DELETE CASCADE,
            chapter TEXT DEFAULT '',
            topic TEXT NOT NULL,
            frequency INTEGER DEFAULT 0,
            difficulty INTEGER DEFAULT 1,
            score_impact REAL DEFAULT 0,
            raid_value TEXT DEFAULT '争取',
            is_mastered INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS plan_task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER REFERENCES exam(id) ON DELETE CASCADE,
            phase INTEGER DEFAULT 1,
            task TEXT,
            estimated_minutes INTEGER DEFAULT 30,
            priority INTEGER DEFAULT 0,
            is_done INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS mistake (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER REFERENCES exam(id) ON DELETE CASCADE,
            question TEXT,
            wrong_answer TEXT,
            correct_answer TEXT,
            reason TEXT,
            knowledge_tag TEXT,
            reviewed INTEGER DEFAULT 0
        );
    ''')
    conn.commit()
    conn.close()


# ─── Exam CRUD ────────────────────────────────────────────

def create_exam(data: dict) -> int:
    conn = get_db()
    cur = conn.execute('''
        INSERT INTO exam (name, exam_date, exam_type, daily_hours,
                          risk_level, target_score, current_score, credit_weight, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('name', ''),
        data.get('exam_date', ''),
        data.get('exam_type', '闭卷'),
        data.get('daily_hours', 4),
        data.get('risk_level', 'medium'),
        data.get('target_score', 60),
        data.get('current_score', None),
        data.get('credit_weight', 1),
        data.get('notes', '')
    ))
    conn.commit()
    eid = cur.lastrowid
    conn.close()

    # 自动创建默认题型
    _create_default_sections(eid)
    return eid


def _create_default_sections(exam_id: int):
    defaults = [
        ('choice', '选择题', 0, 0),
        ('fill', '填空题', 0, 0),
        ('calculation', '计算题', 0, 0),
        ('short_answer', '简答题', 0, 0),
        ('essay', '论述题', 0, 0),
    ]
    conn = get_db()
    for st, sl, sc, cnt in defaults:
        conn.execute('''
            INSERT INTO exam_section (exam_id, section_type, section_label, score, count)
            VALUES (?, ?, ?, ?, ?)
        ''', (exam_id, st, sl, sc, cnt))
    conn.commit()
    conn.close()


def get_all_exams():
    conn = get_db()
    rows = conn.execute(
        'SELECT *, (SELECT COUNT(*) FROM plan_task WHERE exam_id=exam.id AND is_done=1) as done_tasks,'
        ' (SELECT COUNT(*) FROM plan_task WHERE exam_id=exam.id) as total_tasks'
        ' FROM exam ORDER BY exam_date ASC'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_exam(exam_id: int):
    conn = get_db()
    row = conn.execute('SELECT * FROM exam WHERE id = ?', (exam_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_exam(exam_id: int, data: dict):
    conn = get_db()
    conn.execute('''
        UPDATE exam SET name=?, exam_date=?, exam_type=?, daily_hours=?,
                        risk_level=?, target_score=?, current_score=?, credit_weight=?, notes=?
        WHERE id=?
    ''', (
        data.get('name', ''),
        data.get('exam_date', ''),
        data.get('exam_type', '闭卷'),
        data.get('daily_hours', 4),
        data.get('risk_level', 'medium'),
        data.get('target_score', 60),
        data.get('current_score', None),
        data.get('credit_weight', 1),
        data.get('notes', ''),
        exam_id
    ))
    conn.commit()
    conn.close()


def delete_exam(exam_id: int):
    conn = get_db()
    conn.execute('DELETE FROM exam WHERE id = ?', (exam_id,))
    conn.commit()
    conn.close()


# ─── Section CRUD ─────────────────────────────────────────

def get_sections(exam_id: int):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM exam_section WHERE exam_id = ?', (exam_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_section(section_id: int, score: float, count: int):
    conn = get_db()
    conn.execute(
        'UPDATE exam_section SET score=?, count=? WHERE id=?',
        (score, count, section_id)
    )
    conn.commit()
    conn.close()


# ─── Knowledge Point CRUD ─────────────────────────────────

def get_knowledge_points(exam_id: int):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM knowledge_point WHERE exam_id = ? ORDER BY score_impact DESC',
        (exam_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_kp(exam_id: int, chapter: str, topic: str,
              frequency: int = 0, difficulty: int = 1,
              score_impact: float = 0, raid_value: str = '争取'):
    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM knowledge_point WHERE exam_id=? AND topic=?',
        (exam_id, topic)
    ).fetchone()
    if existing:
        conn.execute('''
            UPDATE knowledge_point
            SET chapter=?, frequency=?, difficulty=?, score_impact=?, raid_value=?
            WHERE id=?
        ''', (chapter, frequency, difficulty, score_impact, raid_value, existing['id']))
    else:
        conn.execute('''
            INSERT INTO knowledge_point (exam_id, chapter, topic, frequency, difficulty, score_impact, raid_value)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (exam_id, chapter, topic, frequency, difficulty, score_impact, raid_value))
    conn.commit()
    conn.close()


def clear_knowledge_points(exam_id: int):
    conn = get_db()
    conn.execute('DELETE FROM knowledge_point WHERE exam_id = ?', (exam_id,))
    conn.commit()
    conn.close()


def toggle_kp_mastered(kp_id: int):
    conn = get_db()
    conn.execute(
        'UPDATE knowledge_point SET is_mastered = 1 - is_mastered WHERE id = ?',
        (kp_id,)
    )
    conn.commit()
    conn.close()


def delete_kp(kp_id: int):
    conn = get_db()
    conn.execute('DELETE FROM knowledge_point WHERE id = ?', (kp_id,))
    conn.commit()
    conn.close()


# ─── Plan Task CRUD ───────────────────────────────────────

def get_plan_tasks(exam_id: int):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM plan_task WHERE exam_id = ? ORDER BY phase, sort_order',
        (exam_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_plan_tasks(exam_id: int):
    conn = get_db()
    conn.execute('DELETE FROM plan_task WHERE exam_id = ?', (exam_id,))
    conn.commit()
    conn.close()


def add_plan_task(exam_id: int, phase: int, task: str,
                  estimated_minutes: int = 30, priority: int = 0, sort_order: int = 0):
    conn = get_db()
    conn.execute('''
        INSERT INTO plan_task (exam_id, phase, task, estimated_minutes, priority, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (exam_id, phase, task, estimated_minutes, priority, sort_order))
    conn.commit()
    conn.close()


def toggle_plan_task(task_id: int):
    conn = get_db()
    conn.execute(
        'UPDATE plan_task SET is_done = 1 - is_done WHERE id = ?',
        (task_id,)
    )
    conn.commit()
    conn.close()


# ─── Mistake CRUD ─────────────────────────────────────────

def get_mistakes(exam_id: int):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM mistake WHERE exam_id = ? ORDER BY reviewed ASC',
        (exam_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_mistake(exam_id: int, question: str, wrong_answer: str = '',
                correct_answer: str = '', reason: str = '', knowledge_tag: str = ''):
    conn = get_db()
    conn.execute('''
        INSERT INTO mistake (exam_id, question, wrong_answer, correct_answer, reason, knowledge_tag)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (exam_id, question, wrong_answer, correct_answer, reason, knowledge_tag))
    conn.commit()
    conn.close()


def toggle_mistake_reviewed(mid: int):
    conn = get_db()
    conn.execute(
        'UPDATE mistake SET reviewed = 1 - reviewed WHERE id = ?',
        (mid,)
    )
    conn.commit()
    conn.close()


def delete_mistake(mid: int):
    conn = get_db()
    conn.execute('DELETE FROM mistake WHERE id = ?', (mid,))
    conn.commit()
    conn.close()


# ─── Stats ────────────────────────────────────────────────

def get_exam_stats(exam_id: int) -> dict:
    conn = get_db()
    kps = conn.execute(
        'SELECT raid_value, COUNT(*) as cnt FROM knowledge_point WHERE exam_id=? GROUP BY raid_value',
        (exam_id,)
    ).fetchall()
    tasks = conn.execute(
        'SELECT COUNT(*) as total, SUM(is_done) as done FROM plan_task WHERE exam_id=?',
        (exam_id,)
    ).fetchone()
    conn.close()

    return {
        'kp_must': sum(r['cnt'] for r in kps if r['raid_value'] == '必拿'),
        'kp_try': sum(r['cnt'] for r in kps if r['raid_value'] == '争取'),
        'kp_skip': sum(r['cnt'] for r in kps if r['raid_value'] == '可弃'),
        'tasks_total': tasks['total'] or 0,
        'tasks_done': tasks['done'] or 0,
    }
