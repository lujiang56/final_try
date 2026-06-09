"""期末突击 Web 应用 — Flask 主入口

路由已拆分到 blueprints/ 目录：
  blueprints/exam_bp.py      — 首页 / 仪表盘 / 科目 / 考点 / 计划 / 错题
  blueprints/ppt_bp.py       — PPT 课件对话 / SSE 聊天 / 复习资料 API
  blueprints/debug_bp.py     — LLM Debug 调试控制台
  blueprints/settings_bp.py  — LLM API 设置 / 连接测试
  blueprints/library_bp.py   — 资料库 / 资料查看 / 下载 / 删除
"""

from flask import Flask
from database import init_db, close_db
from blueprints import exam_bp, ppt_bp, debug_bp, settings_bp, library_bp
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FINAL_TRY_SECRET', 'final-try-secret-2024')

app.teardown_appcontext(close_db)


@app.after_request
def add_no_cache_headers(response):
    """禁止浏览器缓存 HTML 页面，确保前端代码总是最新"""
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# 上传文件存储目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 启动时清理 uploads/ 中的残留文件（进程崩溃/被kill等异常情况遗留）
if os.path.exists(UPLOAD_FOLDER):
    for _f in os.listdir(UPLOAD_FOLDER):
        _fp = os.path.join(UPLOAD_FOLDER, _f)
        try:
            os.remove(_fp)
        except OSError:
            pass

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# 启动时初始化数据库
init_db()


# ─── 注册 Blueprint ──────────────────────────────────────

app.register_blueprint(exam_bp)       # /, /dashboard, /exam/..., /api/exam/...
app.register_blueprint(ppt_bp)        # /ppt-analysis, /api/ppt-analysis/...
app.register_blueprint(debug_bp)      # /debug, /api/debug/...
app.register_blueprint(settings_bp)   # /settings, /api/llm/...
app.register_blueprint(library_bp)    # /library, /materials/...


# ─── 启动 ─────────────────────────────────────────────────

if __name__ == '__main__':
    print('期末突击助手已启动 -> http://localhost:5000')
    app.run(debug=True, host='127.0.0.1', port=5000)
