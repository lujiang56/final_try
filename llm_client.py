"""
LLM 客户端 — 统一的 LLM API 调用封装

支持的 Provider:
  - anthropic: Anthropic Claude API (messages.create)
  - openai: OpenAI Chat Completions API
  - custom: 兼容 OpenAI 格式的自部署模型 (Ollama, vLLM 等)

用法:
    from llm_client import call_llm, test_llm_connection

    result = call_llm(system_prompt="你是...", user_message="分析以下内容...")
"""

import json
import time


def _get_config():
    """获取当前 LLM 配置"""
    from database import get_llm_settings, get_llm_api_key
    settings = get_llm_settings()
    api_key = get_llm_api_key()
    settings['api_key'] = api_key
    return settings


def call_llm(system_prompt: str, user_message: str,
             temperature: float = 0.3, max_tokens: int = 4096) -> str:
    """
    统一的 LLM 调用入口，自动根据配置选择 Provider。

    Args:
        system_prompt: 系统提示词
        user_message: 用户消息
        temperature: 温度参数 (0.0-1.0)，分析类任务建议 0.2-0.4
        max_tokens: 最大输出 token 数

    Returns:
        LLM 返回的文本内容

    Raises:
        RuntimeError: 未配置 API Key
        Exception: API 调用失败
    """
    config = _get_config()

    if not config.get('api_key'):
        raise RuntimeError('未配置 LLM API Key，请在设置页面配置')

    provider = config.get('provider', 'anthropic')

    if provider == 'anthropic':
        return _call_anthropic(config, system_prompt, user_message, temperature, max_tokens)
    elif provider in ('openai', 'custom'):
        return _call_openai_compatible(config, system_prompt, user_message, temperature, max_tokens)
    else:
        raise ValueError(f'不支持的 Provider: {provider}')


def test_llm_connection(provider: str, api_key: str,
                        api_base_url: str = '', model_name: str = '') -> dict:
    """
    测试 LLM API 连接是否有效。

    Args:
        provider: 'anthropic' | 'openai' | 'custom'
        api_key: 明文 API Key
        api_base_url: 自定义 endpoint (仅 custom)
        model_name: 模型名

    Returns:
        {'ok': True, 'model': '...', 'latency_ms': 123}
        或
        {'ok': False, 'error': '错误信息'}
    """
    test_config = {
        'provider': provider,
        'api_key': api_key,
        'api_base_url': api_base_url,
        'model_name': model_name or _get_default_model(provider),
    }

    test_prompt = '请回复"OK"（仅这两个字母，不要其他内容）。'

    start = time.time()
    try:
        if provider == 'anthropic':
            result = _call_anthropic(test_config, 'You are a connection tester.',
                                     test_prompt, temperature=0, max_tokens=10)
        else:
            result = _call_openai_compatible(test_config, 'You are a connection tester.',
                                             test_prompt, temperature=0, max_tokens=10)

        latency_ms = int((time.time() - start) * 1000)
        return {
            'ok': True,
            'model': test_config['model_name'],
            'latency_ms': latency_ms,
            'response': result.strip(),
        }
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        return {
            'ok': False,
            'error': str(e),
            'latency_ms': latency_ms,
        }


def _get_default_model(provider: str) -> str:
    """获取默认模型名"""
    from llm_config import get_default_model
    return get_default_model(provider)


# ─── Anthropic ──────────────────────────────────────────────

def _call_anthropic(config: dict, system_prompt: str, user_message: str,
                    temperature: float, max_tokens: int) -> str:
    """调用 Anthropic Claude API"""
    import anthropic

    model = config.get('model_name') or 'claude-sonnet-4-6'

    client = anthropic.Anthropic(api_key=config['api_key'])

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {'role': 'user', 'content': user_message}
                ]
            )
            # 提取文本内容
            text_parts = []
            for block in response.content:
                if block.type == 'text':
                    text_parts.append(block.text)
            return '\n'.join(text_parts)

        except anthropic.APIError as e:
            if attempt == 2:
                raise
            # 指数退避
            time.sleep(2 ** attempt)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


# ─── OpenAI Compatible ──────────────────────────────────────

def _call_openai_compatible(config: dict, system_prompt: str, user_message: str,
                            temperature: float, max_tokens: int) -> str:
    """调用 OpenAI 或兼容 OpenAI 格式的 API"""
    from openai import OpenAI

    model = config.get('model_name') or 'gpt-4o'

    if config.get('provider') == 'custom' and config.get('api_base_url'):
        base_url = config['api_base_url']
    else:
        base_url = None

    client_kwargs = {'api_key': config['api_key']}
    if base_url:
        client_kwargs['base_url'] = base_url

    client = OpenAI(**client_kwargs)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message}
                ]
            )
            return response.choices[0].message.content or ''

        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


# ─── JSON 解析辅助 ──────────────────────────────────────────

def call_llm_json(system_prompt: str, user_message: str,
                  temperature: float = 0.2, max_tokens: int = 4096) -> dict:
    """
    调用 LLM 并解析 JSON 返回。

    会自动处理 LLM 输出中的 markdown 代码块包裹 (```json ... ```)。

    Returns:
        解析后的 dict。如果解析失败，返回 {'raw_response': str, 'parse_error': str}
    """
    raw = call_llm(system_prompt, user_message, temperature, max_tokens)

    # 尝试提取 JSON：去掉可能的 markdown 代码块标记
    text = raw.strip()

    # 移除 ```json ... ``` 包裹
    if text.startswith('```'):
        # 找到第一行末尾
        first_newline = text.find('\n')
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试找到 {...} 边界
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        return {
            'raw_response': raw,
            'parse_error': '无法将 LLM 输出解析为 JSON',
        }


# ─── 流式输出（SSE）──────────────────────────────────────────

def call_llm_stream(system_prompt: str, user_message: str,
                    temperature: float = 0.3, max_tokens: int = 4096,
                    messages_history: list = None, config: dict = None):
    """
    流式 LLM 调用生成器，yield SSE 格式字符串。

    Args:
        system_prompt: 系统提示词
        user_message: 当前用户消息
        temperature: 温度参数
        max_tokens: 最大输出 token 数
        messages_history: 可选的多轮对话历史
            [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}]
        config: 可选的预获取 LLM 配置。在 SSE 生成器中使用时，应先在 Flask
                context 内调用 _get_config() 获取后传入，避免 context 丢失导致
                解密失败。

    Yields:
        "data: {"type": "token", "text": "..."}\n\n"
        "data: {"type": "done", "full_text": "..."}\n\n"
        "data: {"type": "error", "message": "..."}\n\n"
    """
    for event in call_llm_stream_raw(system_prompt, user_message, temperature,
                                      max_tokens, messages_history, config=config):
        yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'


def call_llm_stream_raw(system_prompt: str, user_message: str,
                         temperature: float = 0.3, max_tokens: int = 4096,
                         messages_history: list = None, config: dict = None):
    """
    call_llm_stream() 的原始 dict 版本，yield Python dict 而非 SSE 字符串。

    供 analyze_ppt_streaming() 等需要嵌套处理流式事件的场景使用。

    Yields:
        {"type": "token", "text": "..."}
        {"type": "done", "full_text": "..."}
        {"type": "error", "message": "..."}
    """
    if config is None:
        config = _get_config()

    if not config.get('api_key'):
        yield {"type": "error", "message": "未配置 LLM API Key，请在设置页面配置"}
        return

    provider = config.get('provider', 'anthropic')

    try:
        if provider == 'anthropic':
            yield from _call_anthropic_stream_raw(config, system_prompt, user_message,
                                                   temperature, max_tokens, messages_history)
        elif provider in ('openai', 'custom'):
            yield from _call_openai_compatible_stream_raw(config, system_prompt, user_message,
                                                            temperature, max_tokens, messages_history)
        else:
            yield {"type": "error", "message": f"不支持的 Provider: {provider}"}
    except Exception as e:
        yield {"type": "error", "message": str(e)}


def _build_messages(provider: str, system_prompt: str,
                    messages_history: list, user_message: str) -> tuple:
    """
    构建多轮对话的消息格式。

    Anthropic: 返回 (system_prompt, messages_list)
    OpenAI:    返回 (system_prompt_or_none, messages_list_with_system)

    messages_history 格式: [{'role': 'user'|'assistant', 'content': '...'}, ...]
    """
    if provider == 'anthropic':
        # Anthropic: system 单独传，messages 只含对话
        history = []
        for m in (messages_history or []):
            role = m.get('role', 'user')
            if role in ('user', 'assistant'):
                history.append({'role': role, 'content': m.get('content', '')})
        history.append({'role': 'user', 'content': user_message})
        return system_prompt, history
    else:
        # OpenAI: system 放在 messages 数组第一个
        messages = [{'role': 'system', 'content': system_prompt}]
        for m in (messages_history or []):
            role = m.get('role', 'user')
            if role in ('user', 'assistant'):
                messages.append({'role': role, 'content': m.get('content', '')})
        messages.append({'role': 'user', 'content': user_message})
        return None, messages


def _call_anthropic_stream(config: dict, system_prompt: str, user_message: str,
                           temperature: float, max_tokens: int,
                           messages_history: list = None):
    """Anthropic 流式调用生成器（SSE 字符串版本，兼容旧代码）"""
    for event in _call_anthropic_stream_raw(config, system_prompt, user_message,
                                             temperature, max_tokens, messages_history):
        yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'


def _call_anthropic_stream_raw(config: dict, system_prompt: str, user_message: str,
                                temperature: float, max_tokens: int,
                                messages_history: list = None):
    """Anthropic 流式调用生成器 — yield dict 事件"""
    import anthropic

    model = config.get('model_name') or 'claude-sonnet-4-6'
    client = anthropic.Anthropic(api_key=config['api_key'])

    system, messages = _build_messages('anthropic', system_prompt,
                                        messages_history, user_message)

    full_text = []

    try:
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_text.append(text)
                yield {"type": "token", "text": text}

        full = ''.join(full_text)
        yield {"type": "done", "full_text": full}

    except Exception as e:
        yield {"type": "error", "message": f"Anthropic API 错误: {e}"}


def _call_openai_compatible_stream(config: dict, system_prompt: str, user_message: str,
                                    temperature: float, max_tokens: int,
                                    messages_history: list = None):
    """OpenAI 兼容流式调用生成器（SSE 字符串版本，兼容旧代码）"""
    for event in _call_openai_compatible_stream_raw(config, system_prompt, user_message,
                                                     temperature, max_tokens, messages_history):
        yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'


def _call_openai_compatible_stream_raw(config: dict, system_prompt: str, user_message: str,
                                        temperature: float, max_tokens: int,
                                        messages_history: list = None):
    """OpenAI 兼容流式调用生成器 — yield dict 事件"""
    from openai import OpenAI

    model = config.get('model_name') or 'gpt-4o'

    if config.get('provider') == 'custom' and config.get('api_base_url'):
        base_url = config['api_base_url']
    else:
        base_url = None

    client_kwargs = {'api_key': config['api_key']}
    if base_url:
        client_kwargs['base_url'] = base_url

    client = OpenAI(**client_kwargs)

    _, messages = _build_messages('openai', system_prompt,
                                   messages_history, user_message)

    full_text = []

    try:
        stream = client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                full_text.append(delta.content)
                yield {"type": "token", "text": delta.content}

        full = ''.join(full_text)
        yield {"type": "done", "full_text": full}

    except Exception as e:
        yield {"type": "error", "message": f"OpenAI API 错误: {e}"}
