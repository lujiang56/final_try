# final_try — 开发文档

> 期末突击备考 Web 应用 | Flask + SQLite + Bootstrap 5

---

## 1. 项目概述

### 1.1 背景

传统的期末复习指导依赖 CLI 交互，缺乏可视化、不能持久化数据、不便于多科管理。本项目将「期末突击攻略」skill 转化为完整的 Web GUI 应用。

### 1.2 核心功能

| 模块 | 功能 |
|------|------|
| 快速诊断 | 表单录入考试科目、时间、风险等级、题型分布 |
| 战况仪表盘 | 所有科目的优先级排序卡片 + 进度条 |
| 真题分析 | 粘贴真题文本 → 关键词匹配 → 自动拆解考点 |
| 考点管理 | 手动增删考点、标记掌握状态、调整突击价值 |
| 突击计划 | 三阶段自动生成（套路解析 → 强化练习 → 考前冲刺） |
| 错题本 | 记录错题，按错误原因分类，标记复习状态 |
| 进度追踪 | 所有页面的进度条和完成百分比 |

### 1.3 设计理念

- **80/20 原则**：只抓高频高分考点，果断放弃低价值内容
- **真题驱动**：从真题倒推复习内容，不从第一章开始
- **短期突击**：面向 1-7 天的冲刺场景，非全学期规划

---

## 2. 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | Python 3 + Flask 3.x | 轻量级，15 条路由 |
| 数据库 | SQLite 3 | 零配置，5 张表 |
| 前端框架 | Bootstrap 5.3 (CDN) | 响应式，白色简洁主题 |
| 图表 | Chart.js 4.4 (CDN) | 仪表盘可视化（预留） |
| 前端交互 | Vanilla JavaScript | AJAX 任务切换、倒计时 |

---

## 3. 项目结构

```
final_try/
├── app.py                 # Flask 主入口 (267 行)
│   ├── /                  # 首页：诊断表单 (GET/POST)
│   ├── /dashboard         # 仪表盘：科目总览 (GET)
│   ├── /exam/<id>         # 单科详情：考点+错题 (GET/POST)
│   ├── /exam/<id>/materials   # 真题分析 (GET/POST)
│   ├── /exam/<id>/plan        # 突击计划 (GET)
│   ├── /exam/<id>/plan/regenerate  # 重新生成计划 (POST)
│   ├── /exam/<id>/plan/toggle/<tid>  # 切换任务状态 (POST/AJAX)
│   ├── /exam/<id>/add_kp       # 手动添加考点 (POST)
│   ├── /exam/<id>/kp/<kid>/toggle  # 切换考点掌握 (POST)
│   ├── /exam/<id>/kp/<kid>/delete  # 删除考点 (POST)
│   ├── /exam/<id>/mistake      # 添加错题 (POST)
│   ├── /exam/<id>/mistake/<mid>/toggle  # 标记已复习 (POST)
│   ├── /exam/<id>/mistake/<mid>/delete  # 删除错题 (POST)
│   ├── /exam/<id>/delete       # 删除科目 (POST)
│   └── /api/exam/<id>/progress # 进度JSON (GET)
│
├── database.py            # SQLite 数据层 (280 行)
│   ├── init_db()          # 建表
│   ├── Exam CRUD ×5       # create/get_all/get/update/delete
│   ├── Section CRUD ×2    # get/update
│   ├── KnowledgePoint CRUD ×5  # get/upsert/clear/toggle/delete
│   ├── PlanTask CRUD ×4   # get/clear/add/toggle
│   ├── Mistake CRUD ×4    # get/add/toggle/delete
│   └── Stats ×1           # get_exam_stats
│
├── analyzer.py            # 真题分析引擎 (100+ 行)
│   ├── CHAPTER_KEYWORDS   # 30+ 学科 × 章节关键词库
│   ├── detect_chapter()   # 关键词匹配 → 章节判定
│   ├── determine_raid_value()  # 频次+分值 → 突击价值
│   ├── analyze_materials()     # 主分析流程
│   └── manual_add_kp()         # 手动添加考点
│
├── planner.py             # 突击计划生成器 (100+ 行)
│   ├── generate_plan()    # 三阶段计划生成
│   └── _calc_days_left()  # 距考天数计算
│
├── templates/             # Jinja2 模板
│   ├── base.html          # 母版（导航栏 + CDN 引用）
│   ├── index.html         # 首页诊断表单
│   ├── dashboard.html     # 战况仪表盘
│   ├── subject.html       # 考点管理 + 错题本
│   ├── materials.html     # 真题分析页面
│   └── plan.html          # 三阶段突击计划
│
├── static/
│   ├── style.css          # 白色简洁主题
│   └── app.js             # AJAX 交互 + UI 增强
│
└── requirements.txt       # Flask
```

---

## 4. 数据库设计

### 4.1 ER 图（简化）

```
exam (科目)
 ├── 1:N → exam_section (题型分布)
 ├── 1:N → knowledge_point (考点)
 ├── 1:N → plan_task (计划任务)
 └── 1:N → mistake (错题)
```

### 4.2 表结构

```sql
-- 考试科目
exam (
    id, name, exam_date, exam_type, daily_hours,
    risk_level, target_score, current_score,
    credit_weight, priority, notes, created_at
)

-- 题型分布（每科默认5种题型）
exam_section (
    id, exam_id(FK), section_type, section_label, score, count
)

-- 考点（从真题分析拆解或手动添加）
knowledge_point (
    id, exam_id(FK), chapter, topic,
    frequency, difficulty, score_impact,
    raid_value, is_mastered
)

-- 突击计划任务
plan_task (
    id, exam_id(FK), phase, task,
    estimated_minutes, priority, is_done, sort_order
)

-- 错题
mistake (
    id, exam_id(FK), question, wrong_answer,
    correct_answer, reason, knowledge_tag, reviewed
)
```

---

## 5. 核心算法

### 5.1 真题分析算法 (analyzer.py)

```
输入: 原始真题文本 + 试卷总分
流程:
  1. 正则切分题目 (按题号/中文序号)
  2. 每道题 → detect_chapter() → 关键词打分 → 得分最高的章节
  3. 正则提取每道题的分值标记 (如"10分")
  4. 按章节聚合: 频次 + 总分值
  5. determine_raid_value():
     - 频次≥2 且 分值占比>15% → "必拿"
     - 频次≥1 且 分值占比>5%  → "争取"
     - 其他                      → "可弃"
  6. 写入 knowledge_point 表
输出: 考点分布 dict
```

### 5.2 突击计划生成算法 (planner.py)

```
输入: exam_id
流程:
  1. 读取 exam (距考天数、每日小时)
  2. 读取 knowledge_point (按 raid_value 排序)
  3. 总时间 = 天数 × 每日小时
  4. 三阶段分配:
     - Phase 1 (40%): 必拿考点 → 真题套路解析任务
     - Phase 2 (35%): 争取考点 → 中等练习任务
     - Phase 3 (25%): 错题回顾 + 模拟考 + 速记
  5. 题型专项训练 (高分题型优先)
  6. 写入 plan_task 表
输出: 更新的考点列表
```

### 5.3 关键词匹配库

支持 30+ 学科/专题的关键词匹配，覆盖：
- 数学 (11个专题)：微积分、线代、概率等
- 计算机组成原理 (8个专题)：数据表示、指令系统、存储、Cache、CPU、流水线、总线、I/O
- 其他 CS (5个专题)：数据结构、算法、网络、OS、数据库
- 物理 (4个专题)：力学、电磁学、热学、光学
- 经济 (1个专题)

---

## 6. 部署与运行

### 6.1 环境要求

- Python 3.8+
- pip

### 6.2 安装与启动

```bash
cd final_try
pip install -r requirements.txt
python app.py
# 访问 http://localhost:5000
```

### 6.3 配置项

| 配置 | 位置 | 默认值 |
|------|------|--------|
| 数据库路径 | database.py:DB_PATH | `./final_try.db` |
| 服务端口 | app.py:app.run() | 5000 |
| Debug 模式 | app.py:app.run() | True |
| 监听地址 | app.py:app.run() | 0.0.0.0 |

---

## 7. 前端设计说明

### 7.1 设计原则

- 白色背景 + 细灰边框，避免视觉疲劳
- 移动端响应式（手机查看复习进度）
- 无过分动画，信息密度优先
- 按钮使用 `btn-dark` / `btn-outline-secondary` 朴素风格

### 7.2 关键交互

- **任务勾选**：AJAX 异步提交，即时反馈
- **进度条**：`(已完成任务 / 总任务) × 100%`
- **倒计时**：距考试天数自动计算
- **表单防重复提交**：提交后按钮禁用 2 秒

---

## 8. Token 估算

由于无法从客户端直接获取 API 侧的精确 token 统计，以下基于项目规模估算：

| 类别 | 内容 | 估算 token |
|------|------|:---------:|
| **输出 (代码)** | |
| | database.py (280行) | ~3,500 |
| | app.py (267行) | ~3,300 |
| | analyzer.py (130行) | ~1,800 |
| | planner.py (120行) | ~1,500 |
| | 6个 HTML 模板 (~320行) | ~8,000 |
| | style.css (130行) | ~800 |
| | app.js (80行) | ~600 |
| | skill 文件 (2个版本) | ~4,000 |
| | 开发文档 (本文件) | ~3,000 |
| | 小计 | ~26,500 |
| **输出 (对话说明)** | 分析、总结、交互文本 | ~12,000 |
| **输入** | 用户消息 + 系统提示 + skill加载 | ~15,000 |
| **上下文** | 代码读取、搜索结果等 | ~10,000 |
| **总计 (估算)** | | **~60,000 - 80,000 tokens** |

> 注：实际消耗以 Anthropic API console 为准。以上为基于代码行数和对话长度的粗略估算。

---

## 9. 待优化项

- [ ] 真题分析：接入 LLM 做更精准的考点提取（当前基于关键词匹配）
- [ ] 计划任务：增加截止日期提醒
- [ ] 仪表盘：接入 Chart.js 画分值饼图
- [ ] 多用户支持：用户登录 + 数据隔离
- [ ] 导出功能：计划导出为 PDF / 打印
- [ ] 移动端 PWA：离线可用
- [ ] 暗色主题切换开关
