"""SQLite 数据库初始化和 CRUD 操作"""

import sqlite3
import os
from flask import g, current_app
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'final_try.db')

_SCHEMA = '''
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

    CREATE TABLE IF NOT EXISTS uploaded_file (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER REFERENCES exam(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        original_name TEXT,
        file_size INTEGER DEFAULT 0,
        content_text TEXT,
        slide_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS review_material (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER REFERENCES exam(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        material_type TEXT DEFAULT 'summary',
        content_html TEXT,
        content_text TEXT,
        is_from_ppt INTEGER DEFAULT 0,
        source_file_id INTEGER REFERENCES uploaded_file(id) ON DELETE SET NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS llm_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        provider TEXT DEFAULT 'anthropic',
        api_key_encrypted TEXT,
        api_base_url TEXT,
        model_name TEXT,
        is_configured INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ppt_analysis_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER REFERENCES exam(id) ON DELETE CASCADE,
        session_key TEXT UNIQUE NOT NULL,
        slide_data TEXT,
        analysis_result TEXT,
        chat_history TEXT DEFAULT '[]',
        status TEXT DEFAULT 'idle',
        ppt_filename TEXT,
        slide_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
'''


def init_db():
    """初始化数据库表结构 — 仅在应用启动时调用一次"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()


def get_db():
    """获取当前请求的数据库连接（Flask g-scoped）。

    每个请求第一次调用时创建连接，请求结束时自动关闭。
    在没有 Flask context 的场景（脚本、测试）下回退到创建新连接，
    调用方需自行关闭。
    """
    try:
        if 'db' not in g or g.db is None:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g.db = conn
        return g.db
    except RuntimeError:
        # 没有 Flask application context（脚本/测试场景）
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def close_db(exception=None):
    """请求结束时关闭数据库连接 — 注册为 teardown_appcontext"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


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


def get_all_exams():
    conn = get_db()
    rows = conn.execute(
        'SELECT *, (SELECT COUNT(*) FROM plan_task WHERE exam_id=exam.id AND is_done=1) as done_tasks,'
        ' (SELECT COUNT(*) FROM plan_task WHERE exam_id=exam.id) as total_tasks'
        ' FROM exam ORDER BY exam_date ASC'
    ).fetchall()
    return [dict(r) for r in rows]


def get_exam(exam_id: int):
    conn = get_db()
    row = conn.execute('SELECT * FROM exam WHERE id = ?', (exam_id,)).fetchone()
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


def delete_exam(exam_id: int):
    conn = get_db()
    conn.execute('DELETE FROM exam WHERE id = ?', (exam_id,))
    conn.commit()


# ─── Section CRUD ─────────────────────────────────────────

def get_sections(exam_id: int):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM exam_section WHERE exam_id = ?', (exam_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def update_section(section_id: int, score: float, count: int):
    conn = get_db()
    conn.execute(
        'UPDATE exam_section SET score=?, count=? WHERE id=?',
        (score, count, section_id)
    )
    conn.commit()


# ─── Knowledge Point CRUD ─────────────────────────────────

def get_knowledge_points(exam_id: int):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM knowledge_point WHERE exam_id = ? ORDER BY score_impact DESC',
        (exam_id,)
    ).fetchall()
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


def clear_knowledge_points(exam_id: int):
    conn = get_db()
    conn.execute('DELETE FROM knowledge_point WHERE exam_id = ?', (exam_id,))
    conn.commit()


def toggle_kp_mastered(kp_id: int):
    conn = get_db()
    conn.execute(
        'UPDATE knowledge_point SET is_mastered = 1 - is_mastered WHERE id = ?',
        (kp_id,)
    )
    conn.commit()


def delete_kp(kp_id: int):
    conn = get_db()
    conn.execute('DELETE FROM knowledge_point WHERE id = ?', (kp_id,))
    conn.commit()


# ─── Plan Task CRUD ───────────────────────────────────────

def get_plan_tasks(exam_id: int):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM plan_task WHERE exam_id = ? ORDER BY phase, sort_order',
        (exam_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def clear_plan_tasks(exam_id: int):
    conn = get_db()
    conn.execute('DELETE FROM plan_task WHERE exam_id = ?', (exam_id,))
    conn.commit()


def add_plan_task(exam_id: int, phase: int, task: str,
                  estimated_minutes: int = 30, priority: int = 0, sort_order: int = 0):
    conn = get_db()
    conn.execute('''
        INSERT INTO plan_task (exam_id, phase, task, estimated_minutes, priority, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (exam_id, phase, task, estimated_minutes, priority, sort_order))
    conn.commit()


def toggle_plan_task(task_id: int):
    conn = get_db()
    conn.execute(
        'UPDATE plan_task SET is_done = 1 - is_done WHERE id = ?',
        (task_id,)
    )
    conn.commit()


# ─── Mistake CRUD ─────────────────────────────────────────

def get_mistakes(exam_id: int):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM mistake WHERE exam_id = ? ORDER BY reviewed ASC',
        (exam_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def add_mistake(exam_id: int, question: str, wrong_answer: str = '',
                correct_answer: str = '', reason: str = '', knowledge_tag: str = ''):
    conn = get_db()
    conn.execute('''
        INSERT INTO mistake (exam_id, question, wrong_answer, correct_answer, reason, knowledge_tag)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (exam_id, question, wrong_answer, correct_answer, reason, knowledge_tag))
    conn.commit()


def toggle_mistake_reviewed(mid: int):
    conn = get_db()
    conn.execute(
        'UPDATE mistake SET reviewed = 1 - reviewed WHERE id = ?',
        (mid,)
    )
    conn.commit()


def delete_mistake(mid: int):
    conn = get_db()
    conn.execute('DELETE FROM mistake WHERE id = ?', (mid,))
    conn.commit()


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

    return {
        'kp_must': sum(r['cnt'] for r in kps if r['raid_value'] == '必拿'),
        'kp_try': sum(r['cnt'] for r in kps if r['raid_value'] == '争取'),
        'kp_skip': sum(r['cnt'] for r in kps if r['raid_value'] == '可弃'),
        'tasks_total': tasks['total'] or 0,
        'tasks_done': tasks['done'] or 0,
    }


# ─── Uploaded File CRUD ───────────────────────────────────

def create_uploaded_file(exam_id: int, filename: str, original_name: str,
                         file_size: int = 0, content_text: str = '',
                         slide_count: int = 0) -> int:
    """保存上传的PPT文件记录，返回插入ID"""
    conn = get_db()
    cur = conn.execute('''
        INSERT INTO uploaded_file (exam_id, filename, original_name, file_size, content_text, slide_count)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (exam_id, filename, original_name, file_size, content_text, slide_count))
    conn.commit()
    return cur.lastrowid


def get_uploaded_files(exam_id: int) -> list:
    """获取某个科目的所有上传文件"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM uploaded_file WHERE exam_id = ? ORDER BY created_at DESC',
        (exam_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Review Material CRUD ─────────────────────────────────

def create_material(exam_id: int, title: str, material_type: str = 'summary',
                    content_html: str = '', content_text: str = '',
                    is_from_ppt: int = 0, source_file_id: int = None) -> int:
    """创建复习资料，返回插入ID"""
    conn = get_db()
    cur = conn.execute('''
        INSERT INTO review_material (exam_id, title, material_type, content_html, content_text, is_from_ppt, source_file_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (exam_id, title, material_type, content_html, content_text, is_from_ppt, source_file_id))
    conn.commit()
    return cur.lastrowid


def get_materials(exam_id: int = None) -> list:
    """
    获取复习资料列表。
    exam_id=None 时返回所有科目的资料（含科目名称）。
    """
    conn = get_db()
    if exam_id is None:
        rows = conn.execute('''
            SELECT rm.*, e.name as exam_name
            FROM review_material rm
            JOIN exam e ON rm.exam_id = e.id
            ORDER BY rm.created_at DESC
        ''').fetchall()
    else:
        rows = conn.execute(
            'SELECT rm.*, e.name as exam_name'
            ' FROM review_material rm JOIN exam e ON rm.exam_id = e.id'
            ' WHERE rm.exam_id = ? ORDER BY rm.created_at DESC',
            (exam_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_material(material_id: int) -> dict:
    """获取单个复习资料"""
    conn = get_db()
    row = conn.execute('''
        SELECT rm.*, e.name as exam_name
        FROM review_material rm JOIN exam e ON rm.exam_id = e.id
        WHERE rm.id = ?
    ''', (material_id,)).fetchone()
    return dict(row) if row else None


def delete_material(material_id: int):
    """删除复习资料"""
    conn = get_db()
    conn.execute('DELETE FROM review_material WHERE id = ?', (material_id,))
    conn.commit()


# ─── LLM Settings CRUD ─────────────────────────────────────

def get_llm_settings() -> dict:
    """获取 LLM 配置（不含完整 API Key）"""
    conn = get_db()
    row = conn.execute('SELECT * FROM llm_settings WHERE id = 1').fetchone()
    if not row:
        return {
            'provider': 'anthropic',
            'api_base_url': '',
            'model_name': '',
            'is_configured': False,
            'has_key': False,
        }
    d = dict(row)
    return {
        'provider': d.get('provider', 'anthropic'),
        'api_base_url': d.get('api_base_url', '') or '',
        'model_name': d.get('model_name', '') or '',
        'is_configured': bool(d.get('is_configured', 0)),
        'has_key': bool(d.get('api_key_encrypted')),
    }


def get_llm_api_key() -> str | None:
    """获取解密后的 API Key（仅在服务端调用）"""
    conn = get_db()
    row = conn.execute('SELECT api_key_encrypted FROM llm_settings WHERE id = 1').fetchone()
    if not row or not row['api_key_encrypted']:
        return None
    from llm_config import decrypt_api_key
    return decrypt_api_key(row['api_key_encrypted'])


def save_llm_settings(provider: str, api_key: str = '',
                      api_base_url: str = '', model_name: str = '') -> bool:
    """
    保存 LLM 配置。如果 api_key 为空字符串，保留已有的 key 不变。
    """
    from llm_config import encrypt_api_key
    conn = get_db()

    existing = conn.execute('SELECT * FROM llm_settings WHERE id = 1').fetchone()

    if existing:
        if api_key:
            encrypted = encrypt_api_key(api_key)
            conn.execute('''
                UPDATE llm_settings
                SET provider=?, api_key_encrypted=?, api_base_url=?,
                    model_name=?, is_configured=1, updated_at=CURRENT_TIMESTAMP
                WHERE id=1
            ''', (provider, encrypted, api_base_url, model_name))
        else:
            conn.execute('''
                UPDATE llm_settings
                SET provider=?, api_base_url=?, model_name=?,
                    is_configured=1, updated_at=CURRENT_TIMESTAMP
                WHERE id=1
            ''', (provider, api_base_url, model_name))
    else:
        encrypted = encrypt_api_key(api_key) if api_key else ''
        conn.execute('''
            INSERT INTO llm_settings (id, provider, api_key_encrypted, api_base_url, model_name, is_configured)
            VALUES (1, ?, ?, ?, ?, 1)
        ''', (provider, encrypted, api_base_url, model_name))

    conn.commit()
    return True


def clear_llm_settings():
    """清除 LLM 配置（API Key + 设置）"""
    conn = get_db()
    conn.execute('DELETE FROM llm_settings WHERE id = 1')
    conn.commit()


# ─── PPT Analysis Session CRUD ───────────────────────────────

def create_analysis_session(exam_id: int, session_key: str, ppt_filename: str,
                            slide_data: str, slide_count: int = 0,
                            status: str = 'idle') -> int:
    """创建 PPT 分析会话，返回新行 ID"""
    conn = get_db()
    cur = conn.execute('''
        INSERT INTO ppt_analysis_session
            (exam_id, session_key, ppt_filename, slide_data, slide_count, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (exam_id, session_key, ppt_filename, slide_data, slide_count, status))
    conn.commit()
    return cur.lastrowid


def get_analysis_session(session_key: str) -> dict | None:
    """通过 session_key 获取分析会话"""
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM ppt_analysis_session WHERE session_key = ?',
        (session_key,)
    ).fetchone()
    return dict(row) if row else None


def get_analysis_session_by_exam(exam_id: int) -> dict | None:
    """获取某个科目的最近一次分析会话"""
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM ppt_analysis_session WHERE exam_id = ? ORDER BY updated_at DESC LIMIT 1',
        (exam_id,)
    ).fetchone()
    return dict(row) if row else None


def update_analysis_session(session_key: str, **fields):
    """
    更新分析会话字段。
    自动将 dict/list 类型的字段 json.dumps，并更新 updated_at。
    """
    import json as _json
    conn = get_db()

    # 构建 SET 子句
    set_parts = []
    values = []
    json_fields = {'slide_data', 'analysis_result', 'chat_history'}
    for key, value in fields.items():
        if key in json_fields and isinstance(value, (dict, list)):
            value = _json.dumps(value, ensure_ascii=False)
        set_parts.append(f'{key} = ?')
        values.append(value)

    # 始终更新 updated_at
    set_parts.append('updated_at = CURRENT_TIMESTAMP')
    values.append(session_key)

    conn.execute(
        f'UPDATE ppt_analysis_session SET {", ".join(set_parts)} WHERE session_key = ?',
        values
    )
    conn.commit()


def delete_analysis_session(session_key: str):
    """删除分析会话"""
    conn = get_db()
    conn.execute('DELETE FROM ppt_analysis_session WHERE session_key = ?', (session_key,))
    conn.commit()