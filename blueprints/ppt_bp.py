"""PPT 课件对话 — 上传 / SSE 流式聊天 / 复习资料生成"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, Response, current_app
from database import (
    get_all_exams, get_exam, create_exam,
    create_uploaded_file,
    create_analysis_session, get_analysis_session, update_analysis_session,
    create_material,
)
from ppt_handler import allowed_file, extract_text, extract_by_slide
from llm_config import _get_encryption_key
from database import get_llm_settings
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import re
import json
import uuid

ppt_bp = Blueprint('ppt', __name__)


# ─── PPT 智能分析页面 — 独立入口 ─────────────────────────

@ppt_bp.route('/ppt-analysis')
def ppt_analysis_home():
    """PPT 智能分析页面（无 session 时显示上传入口）"""
    llm = get_llm_settings()
    llm_configured = llm.get('is_configured') and llm.get('has_key')
    exams = get_all_exams()
    return render_template('ppt_analysis.html',
                           session=None,
                           llm_configured=llm_configured,
                           exams=exams)


@ppt_bp.route('/ppt-analysis/<session_key>')
def ppt_analysis_session(session_key):
    """PPT 智能分析页面（已有 session 时恢复状态）"""
    session_data = get_analysis_session(session_key)
    if not session_data:
        return redirect(url_for('ppt.ppt_analysis_home'))
    llm = get_llm_settings()
    llm_configured = llm.get('is_configured') and llm.get('has_key')
    exams = get_all_exams()

    # 解析 JSON 字段供模板使用
    if session_data.get('chat_history'):
        try:
            session_data['chat_history'] = json.loads(session_data['chat_history'])
        except (json.JSONDecodeError, TypeError):
            session_data['chat_history'] = []
    else:
        session_data['chat_history'] = []

    if session_data.get('analysis_result'):
        try:
            session_data['analysis_result'] = json.loads(session_data['analysis_result'])
        except (json.JSONDecodeError, TypeError):
            session_data['analysis_result'] = None

    return render_template('ppt_analysis.html',
                           session=session_data,
                           llm_configured=llm_configured,
                           exams=exams)


# ─── PPT 智能分析 API ────────────────────────────────────

@ppt_bp.route('/api/ppt-analysis/create', methods=['POST'])
def api_ppt_analysis_create():
    """上传 PPT 并创建分析会话"""
    if 'ppt_file' not in request.files:
        return jsonify({'ok': False, 'error': '未选择文件'}), 400

    file = request.files['ppt_file']
    if file.filename == '':
        return jsonify({'ok': False, 'error': '未选择文件'}), 400

    if not allowed_file(file.filename):
        return jsonify({'ok': False, 'error': '不支持的文件格式，请上传 .pptx 文件'}), 400

    upload_folder = current_app.config['UPLOAD_FOLDER']
    original_name = file.filename
    safe_name = secure_filename(file.filename)
    filepath = os.path.join(upload_folder, safe_name)
    file.save(filepath)

    # 提取幻灯片
    slides = extract_by_slide(filepath)
    raw_text, slide_count = extract_text(filepath)
    file_size = os.path.getsize(filepath)

    if not slides or slide_count == 0:
        try:
            os.remove(filepath)
        except OSError:
            pass
        return jsonify({'ok': False, 'error': '该 PPT 中未提取到文本内容，请确认文件包含文字'}), 400

    # 确定 exam：用户选择已有科目 或 自动创建
    exam_id_str = request.form.get('exam_id', '')
    if exam_id_str:
        exam_id = int(exam_id_str)
        exam = get_exam(exam_id)
        if not exam:
            exam_id = _get_or_create_exam_for_ppt(original_name)
    else:
        exam_id = _get_or_create_exam_for_ppt(original_name)

    # 保存上传记录
    create_uploaded_file(
        exam_id, safe_name, original_name, file_size,
        raw_text, slide_count
    )

    # 创建分析会话 — 直接 ready
    session_key = str(uuid.uuid4())
    create_analysis_session(
        exam_id=exam_id,
        session_key=session_key,
        ppt_filename=original_name,
        slide_data=json.dumps(slides, ensure_ascii=False),
        slide_count=slide_count,
        status='ready'
    )

    # 清理临时文件
    try:
        os.remove(filepath)
    except OSError:
        pass

    return jsonify({
        'ok': True,
        'session_key': session_key,
        'exam_id': exam_id,
        'slide_count': slide_count,
        'filename': original_name,
    })


def _get_or_create_exam_for_ppt(filename: str) -> int:
    """根据 PPT 文件名查找或创建科目"""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = name.strip() or '未命名课件'

    exams = get_all_exams()
    for e in exams:
        if e['name'] == name:
            return e['id']

    today = datetime.now().strftime('%Y-%m-%d')
    data = {
        'name': name,
        'exam_date': today,
        'exam_type': '闭卷',
        'daily_hours': 4,
        'risk_level': 'medium',
        'target_score': 60,
        'current_score': None,
        'credit_weight': 1,
        'notes': f'由 PPT 课件"{filename}"自动创建',
    }
    return create_exam(data)


@ppt_bp.route('/api/ppt-analysis/<session_key>/status')
def api_ppt_analysis_status(session_key):
    """获取分析会话的当前状态"""
    session_data = get_analysis_session(session_key)
    if not session_data:
        return jsonify({'error': 'Session not found'}), 404

    for field in ('chat_history', 'analysis_result', 'slide_data'):
        if session_data.get(field) and isinstance(session_data[field], str):
            try:
                session_data[field] = json.loads(session_data[field])
            except (json.JSONDecodeError, TypeError):
                session_data[field] = None

    return jsonify({k: v for k, v in session_data.items()
                    if k != 'id'})


@ppt_bp.route('/api/ppt-analysis/<session_key>/chat', methods=['POST'])
def api_ppt_analysis_chat(session_key):
    """SSE 流式对话端点 — 系统 prompt 嵌入 PPT 全文"""
    session_data = get_analysis_session(session_key)
    if not session_data:
        return jsonify({'error': 'Session not found'}), 404

    if session_data['status'] not in ('ready',):
        return jsonify({'error': '请先上传 PPT 课件'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': '消息不能为空'}), 400

    # 加载对话历史
    chat_history = []
    if session_data.get('chat_history'):
        try:
            chat_history = json.loads(session_data['chat_history'])
        except (json.JSONDecodeError, TypeError):
            chat_history = []

    # 构建课件全文上下文
    slides = json.loads(session_data['slide_data'])
    ppt_filename = session_data.get('ppt_filename', '未知课件')
    slide_count = session_data.get('slide_count', len(slides))
    ppt_text = _format_ppt_text(slides)

    chat_system_prompt = f'''你是一位大学课程辅导老师。学生上传了一份课件PPT"{ppt_filename}"（共{slide_count}页），以下是课件全部文字内容：

{ppt_text}

请根据以上课件内容，以辅导老师的身份回答学生的问题。
你可以解答疑问、解释概念、提供学习建议、帮助制定复习策略。

要求：用中文回答，语气亲切专业，简明扼要突出重点。
如果学生的问题超出课件范围，请诚实说明。'''

    chat_history.append({'role': 'user', 'content': user_message})

    # 预热加密密钥 + 获取 LLM 配置（在 Flask context 内）
    _get_encryption_key()
    from llm_client import _get_config
    llm_config = _get_config()

    def generate():
        from llm_client import call_llm_stream

        full_response = ''

        try:
            for sse_line in call_llm_stream(
                system_prompt=chat_system_prompt,
                user_message=user_message,
                temperature=0.5,
                max_tokens=4096,
                messages_history=chat_history[:-1],
                config=llm_config
            ):
                yield sse_line

                if sse_line.startswith('data: '):
                    try:
                        event = json.loads(sse_line[6:])
                        if event.get('type') == 'done':
                            full_response = event.get('full_text', '')
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            yield f'data: {json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)}\n\n'

        chat_history.append({'role': 'assistant', 'content': full_response})
        update_analysis_session(session_key, chat_history=chat_history)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


def _format_ppt_text(slides: list) -> str:
    """将幻灯片列表格式化为 LLM prompt 文本"""
    parts = []
    for s in slides:
        num = s.get('slide_num', '?')
        title = s.get('title', '') or f'第{num}页'
        text = s.get('full_text', '')[:2000]
        parts.append(f'【第{num}页】{title}\n{text}')
    return '\n\n'.join(parts)


@ppt_bp.route('/api/ppt-analysis/<session_key>/cancel', methods=['POST'])
def api_ppt_analysis_cancel(session_key):
    """取消正在进行的分析"""
    session_data = get_analysis_session(session_key)
    if not session_data:
        return jsonify({'error': 'Session not found'}), 404

    update_analysis_session(session_key, status='idle')
    return jsonify({'ok': True})


@ppt_bp.route('/api/ppt-analysis/<session_key>/generate-material', methods=['POST'])
def api_ppt_analysis_generate_material(session_key):
    """生成复习资料 — 基于 PPT 原文 + LLM"""
    session_data = get_analysis_session(session_key)
    if not session_data:
        return jsonify({'ok': False, 'error': 'Session not found'}), 404

    if session_data['status'] not in ('ready',):
        return jsonify({'ok': False, 'error': '请先上传 PPT 课件'}), 400

    data = request.get_json() or {}
    material_type = data.get('material_type', 'summary')
    if material_type not in ('summary', 'cheatsheet', 'focus_guide'):
        material_type = 'summary'

    exam_id = session_data['exam_id']
    exam = get_exam(exam_id)
    slides = json.loads(session_data['slide_data'])
    ppt_text = _format_ppt_text(slides)
    ppt_filename = session_data.get('ppt_filename', '未知课件')

    update_analysis_session(session_key, status='generating')

    try:
        from llm_client import call_llm

        type_instructions = {
            'summary': '生成一份完整的复习总结。包含：各章节核心概念讲解、重要公式、典型解题思路。用 HTML 格式输出（Bootstrap 5 样式），要有目录导航。',
            'cheatsheet': '生成一份紧凑的考前速查表。包含：高频考点清单、核心公式速查、易错点提醒。用 HTML 表格和卡片布局，紧凑排版。',
            'focus_guide': '生成一份重点突破指南。聚焦最重要的内容，每个重点给出：① 核心概念精讲 ② 典型例题思路 ③ 常见陷阱提醒。用 HTML 卡片布局。',
        }

        system_prompt = '你是资深大学课程辅导专家。根据课件内容生成复习资料。输出合法 HTML 片段（不要<!DOCTYPE>），使用 Bootstrap 5 CSS 类。中文输出。'
        user_message = f'课件"{ppt_filename}"内容：\n\n{ppt_text}\n\n{type_instructions.get(material_type, type_instructions["summary"])}\n\n请直接输出 HTML 片段。'

        html = call_llm(system_prompt, user_message, temperature=0.5, max_tokens=8192)
        html = _clean_html(html)

        from material_generator import _strip_html
        text = _strip_html(html)

        title_map = {
            'summary': f'{exam["name"]} — AI 复习总结',
            'cheatsheet': f'{exam["name"]} — AI 考前速查表',
            'focus_guide': f'{exam["name"]} — AI 重点突破指南',
        }
        title = title_map.get(material_type, f'{exam["name"]} — 复习资料')

        material_id = create_material(
            exam_id=exam_id, title=title, material_type=material_type,
            content_html=html, content_text=text, is_from_ppt=1,
        )
        update_analysis_session(session_key, status='ready')
        return jsonify({'ok': True, 'material_id': material_id, 'title': title})

    except Exception as e:
        update_analysis_session(session_key, status='ready')
        return jsonify({'ok': False, 'error': f'生成失败: {e}'}), 500


def _clean_html(text: str) -> str:
    """清理 LLM 输出的 HTML 标记"""
    text = text.strip()
    if text.startswith('```html'):
        text = text[7:]
    elif text.startswith('```'):
        nl = text.find('\n')
        if nl != -1:
            text = text[nl + 1:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()
