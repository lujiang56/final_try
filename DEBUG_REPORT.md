# PPT 分析页面调试追溯报告

> 日期：2026-06-05 | 项目：期末突击备考 Web 应用

---

## 一、问题现象

用户上传 PPTX 文件后，前端"毫无反应"——文件选择后点击上传按钮无任何视觉反馈，不显示进度条，不进入分析/对话流程。页面 URL 从 `/ppt-analysis` 变为 `/ppt-analysis?ppt_file=chapter1.pptx&exam_id=` 后无后续。

## 二、排查过程

### 第 1 层：后端验证

直接通过 Python 脚本调用 API：

```
POST /api/ppt-analysis/create  →  ok=True, slides=67, session 创建成功
GET  /api/ppt-analysis/{key}/analyze  →  流式 token 正常返回
POST /api/ppt-analysis/{key}/chat     →  对话正常
```

**结论：后端 API 完全正常。**

### 第 2 层：浏览器 JS 错误

用户报告 `Uncaught TypeError: Cannot read properties of undefined (reading 'addEventListener')` at line 325。

追踪到 `dom.uploadForm.addEventListener('submit', ...)` —— `dom.uploadForm` 为 `undefined`。

**根因定位：`$('#upload-form')` 即 `document.querySelector('#upload-form')` 返回 `null`。**

### 第 3 层：排除缓存

- 添加 `@app.after_request` 设置 `Cache-Control: no-cache, no-store, must-revalidate`
- 用户使用无痕窗口测试
- 问题依旧

**排除浏览器缓存。**

### 第 4 层：排除 app.js 干扰

- `app.js`（通过 `base.html` 加载）中有旧的上传区域事件处理器和全局表单处理器
- 将 `ppt_analysis.html` 改为独立页面，不继承 `base.html`，不加载 `app.js`
- 问题依旧

**排除 app.js 干扰。**

### 第 5 层：HTML 结构验证

在 form 标签**之后**插入同步内联 `<script>`，检查 form 是否在 DOM 中：

```javascript
document.getElementById('upload-form')   → true  ✓
document.querySelector('#upload-form')  → true  ✓
document.forms.length                   → 1     ✓
```

**form 在解析时存在。但 DOMContentLoaded 回调中 `querySelector('#upload-form')` 返回 `null`。**

### 第 6 层：发现 HTML 结构缺陷

统计 `<div>` 和 `</div>` 数量：

```
<div> 46  </div> 45  →  少一个 </div>
```

**根因**：将模板从 `{% extends "base.html" %}` 改为独立 HTML 时，`<div class="container mt-4 mb-5">` 缺少对应的 `</div>` 关闭标签。

浏览器解析器遇到未关闭的 `<div>` 时，会尝试自动修复 DOM 树。这种修复行为在不同时机、不同查询方式下表现不一致：
- 内联脚本（同步解析时）：form 可被 `getElementById` 和 `querySelector` 找到
- DOMContentLoaded 回调中：`querySelector` 找不到该 form

### 第 7 层：防御性修复

在内联脚本中保存 form 引用到 `window.__UPLOAD_FORM_REF`，DOMContentLoaded 中若 `querySelector` 失败则回退使用该引用。

## 三、最终修复清单

| 问题 | 修复 |
|---|---|
| Flask SSE context 丢失导致 API Key 解密失败 | `llm_config.py` 缓存加密密钥；所有 SSE 端点预热 context |
| XHR `uploadXHR = null` 检查顺序错误导致上传被跳过 | 先检查 `uploadXHR === null`，再置 null |
| `app.js` 全局表单处理器与 PPT 页面冲突 | `app.js` 跳过 `id="upload-form"` 的表单 |
| `app.js` 上传区域处理器重复绑定 | `app.js` 仅对 `materials.html` 生效 |
| 缺少 `cryptography` 包 | 安装到 `.venv` |
| 缺少 `openai` 包 | 安装到 `.venv` |
| HTML `<div>` 未闭合导致 DOM 解析异常 | 补上 `</div>`；改为独立页面不继承 base.html |
| `querySelector` 在 DOMContentLoaded 中查不到 form | 内联保存引用防御 |

## 四、架构简化

在此期间按用户要求完成了以下架构变更：

1. **删除词义分析模块**：`ppt_analyzer.py`（规则引擎）、`ppt_llm_analyzer.py`（结构化 LLM 分析）
2. **删除分析步骤**：上传 PPT → 直接进入聊天（不再经过"分析→结构化→存考点"）
3. **聊天 prompt 嵌入 PPT 全文**：系统 prompt 直接包含幻灯片文字内容
4. **流程简化为 2 步**：上传课件 → AI 对话
5. **清理冗余文件**：删除 8 个过期测试文件和模块

## 五、经验教训

1. **HTML 结构完整性是第一道防线**：一个未闭合的 `<div>` 可以导致整个 DOM 查询失效，且错误信息完全不指向根因。建议在 CI 中加入 HTML validator。
2. **`querySelector` 不是 100% 可靠**：在浏览器 DOM 修复算法介入后，不同时机同一查询可能返回不同结果。`getElementById` 比 `querySelector` 更稳定。
3. **缓存问题容易被误判**：添加了 no-cache 头后问题依旧，容易被误认为是"缓存没清干净"，实际上问题在 HTML 结构。
4. **最小化测试页面是最强调试工具**：`test_upload.html` 独立页面秒定位到问题不在后端、不在浏览器、不在 app.js，而在模板自身。

---

*报告生成于 2026-06-05，调试耗时约 2 小时，最终根因为 1 个未闭合的 HTML 标签。*
