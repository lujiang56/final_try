# final_try — 期末突击备考助手

> 短期高强度备考 Web 应用 | 真题驱动 · 考点拆解 · 突击计划

![](https://img.shields.io/badge/Python-3.8+-blue) ![](https://img.shields.io/badge/Flask-3.x-green) ![](https://img.shields.io/badge/Bootstrap-5.3-purple)

## 这是什么

面向大学期末考试的**短期突击工具**。粘贴往年真题，自动拆解高频考点，生成三阶段突击计划，跟踪复习进度。

核心理念：80/20 法则——只抓 20% 的高频考点拿下 80% 的分数。

## 快速开始

```bash
pip install -r requirements.txt
python app.py
# 打开 http://localhost:5000
```

## 功能

| 模块 | 说明 |
|------|------|
| 快速诊断 | 录入科目、时间、风险等级 |
| 真题分析 | 粘贴真题文本 → 自动拆解考点 |
| 考点管理 | 标记必拿/争取/可弃，跟踪掌握状态 |
| 突击计划 | 自动生成三阶段时间表 |
| 错题本 | 记录错题，分类回顾 |

## 技术栈

- **后端**: Python Flask + SQLite
- **前端**: Bootstrap 5（白色简洁主题）
- **分析引擎**: 关键词匹配 + 分值聚合

## 项目结构

```
final_try/
├── app.py              # Flask 主程序
├── database.py         # SQLite 数据层
├── analyzer.py         # 真题分析引擎
├── planner.py          # 突击计划生成器
├── templates/          # Jinja2 模板 (6个页面)
├── static/             # CSS + JS
└── DEVELOPMENT.md      # 开发文档
```
