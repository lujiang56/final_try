"""LLM API 设置页面 — Provider / API Key / 模型配置"""

from flask import Blueprint, render_template, request, jsonify
from llm_config import mask_api_key, get_default_model, decrypt_api_key
from database import get_llm_settings, save_llm_settings, clear_llm_settings

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """LLM API 配置页面"""
    message = None
    error = None

    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if action == 'save':
            provider = request.form.get('provider', 'anthropic')
            api_key = request.form.get('api_key', '')
            api_base_url = request.form.get('api_base_url', '')
            model_name = request.form.get('model_name', '')
            auto_model = request.form.get('auto_model', '0')

            if auto_model == '1' or not model_name.strip():
                model_name = get_default_model(provider)

            try:
                save_llm_settings(
                    provider=provider,
                    api_key=api_key,
                    api_base_url=api_base_url,
                    model_name=model_name
                )
                message = '设置已保存'
            except Exception as e:
                error = f'保存失败: {e}'

        elif action == 'clear':
            try:
                clear_llm_settings()
                message = 'API Key 已清除'
            except Exception as e:
                error = f'清除失败: {e}'

    # 读取当前设置
    llm = get_llm_settings()

    # 生成掩码 Key 用于前端显示
    masked_key = ''
    if llm.get('has_key'):
        raw_key = get_llm_api_key() or ''
        if raw_key:
            masked_key = mask_api_key(raw_key)

    return render_template('settings.html',
                           llm=llm,
                           masked_key=masked_key,
                           message=message,
                           error=error)


@settings_bp.route('/api/llm/test', methods=['POST'])
def api_llm_test():
    """测试 LLM API 连接"""
    try:
        data = request.get_json() or {}
        provider = data.get('provider', 'anthropic')
        api_key = data.get('api_key', '')
        api_base_url = data.get('api_base_url', '')
        model_name = data.get('model_name', '')

        if not api_key:
            from database import get_llm_api_key
            api_key = get_llm_api_key() or ''

        if not api_key:
            return jsonify({'ok': False, 'error': '请先输入 API Key'})

        from llm_client import test_llm_connection
        result = test_llm_connection(provider, api_key, api_base_url, model_name)
        return jsonify(result)

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
