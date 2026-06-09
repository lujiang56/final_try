"""LLM Debug 调试控制台 — 直接与 LLM API 交互的开发者工具"""

from flask import Blueprint, render_template, request, jsonify, Response
from llm_config import _get_encryption_key
from database import get_llm_settings
import json

debug_bp = Blueprint('debug', __name__)


@debug_bp.route('/debug')
def debug_chat():
    """LLM API 调试聊天页面"""
    llm = get_llm_settings()
    llm_configured = llm.get('is_configured') and llm.get('has_key')

    config_info = {
        'provider': llm.get('provider', '未设置'),
        'model': llm.get('model_name', '未设置'),
        'configured': llm_configured,
    }
    if llm.get('api_base_url'):
        config_info['base_url'] = llm['api_base_url']

    return render_template('debug_chat.html', config=config_info)


@debug_bp.route('/api/debug/chat', methods=['POST'])
def api_debug_chat():
    """SSE 流式调试聊天端点"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求体不能为空'}), 400

    system_prompt = data.get('system_prompt', '').strip()
    user_message = data.get('user_message', '').strip()
    if not user_message:
        return jsonify({'error': '消息不能为空'}), 400

    conversation_history = data.get('conversation_history', []) or []
    temperature = float(data.get('temperature', 0.3))
    max_tokens = int(data.get('max_tokens', 4096))

    # 验证 LLM 配置
    llm_settings = get_llm_settings()
    if not (llm_settings.get('is_configured') and llm_settings.get('has_key')):
        def err_gen():
            yield f'data: {json.dumps({"type": "error", "message": "LLM 未配置，请先在设置页面配置 API Key"}, ensure_ascii=False)}\n\n'
        return Response(err_gen(), mimetype='text/event-stream')

    # 在 Flask context 内预热加密密钥缓存 + 获取解密后的 API Key
    _get_encryption_key()

    from llm_client import _get_config
    llm_config = _get_config()

    def generate():
        yield f'data: {json.dumps({"type": "meta", "provider": llm_config.get("provider"), "model": llm_config.get("model_name"), "base_url": llm_config.get("api_base_url", "")}, ensure_ascii=False)}\n\n'

        try:
            from llm_client import call_llm_stream
            for sse_line in call_llm_stream(
                system_prompt=system_prompt or 'You are a helpful assistant.',
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
                messages_history=conversation_history,
                config=llm_config
            ):
                yield sse_line
        except Exception as e:
            yield f'data: {json.dumps({"type": "error", "message": f"API 调用失败: {e}"}, ensure_ascii=False)}\n\n'

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )
