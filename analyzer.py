"""真题材料分析引擎 — 从用户输入的题目文本中提取考点"""

import re
from database import clear_knowledge_points, upsert_kp, get_sections


# 章节关键词库（中英文通用，按学科分类）
CHAPTER_KEYWORDS = {
    # ─── 数学 ───
    '极限与连续': ['极限', '连续', '间断', '无穷小', '无穷大', '夹逼', 'lim', 'limit', 'continuity'],
    '导数': ['导数', '求导', '微分', '可导', '切线', '法线', 'derivative', 'differentiate'],
    '中值定理': ['罗尔', '拉格朗日', '柯西', '泰勒', '中值', 'Rolle', 'Lagrange', 'Taylor', 'MVT'],
    '积分': ['积分', '不定积分', '定积分', '换元', '分部积分', 'integral', 'integration', '原函数', '反常积分'],
    '微分方程': ['微分方程', '通解', '特解', 'ODE', 'differential equation', '分离变量', '特征方程'],
    '向量与空间': ['向量', '空间解析', '点积', '叉积', '平面', '直线', 'vector'],
    '多元函数': ['偏导', '全微分', '梯度', '方向导数', '极值', '拉格朗日乘数', 'partial derivative'],
    '重积分': ['二重积分', '三重积分', '极坐标', '柱坐标', '球坐标', 'double integral'],
    '级数': ['级数', '收敛', '发散', '幂级数', '傅里叶', 'series', 'convergence'],
    '线性代数': ['矩阵', '行列式', '特征值', '特征向量', '秩', '线性相关', 'matrix', 'eigenvalue'],
    '概率': ['概率', '随机变量', '分布', '期望', '方差', '贝叶斯', 'probability', 'distribution'],

    # ─── 计算机组成原理 ───
    '数据表示与运算': [
        '原码', '反码', '补码', '移码', '浮点数', 'IEEE754', '溢出', '定点数',
        '算术逻辑', 'ALU', '加法器', '乘法器', 'Booth', '进位', '标志位',
        '字长', '符号位', '阶码', '尾数', '规格化', '对阶'
    ],
    '指令系统': [
        '指令格式', '操作码', '地址码', '寻址方式', '立即寻址', '直接寻址',
        '间接寻址', '变址寻址', '基址寻址', '相对寻址', '寄存器寻址',
        'RISC', 'CISC', '指令集', '指令周期', '取指', '译码', '执行'
    ],
    '存储系统': [
        '存储器', '主存', '内存', 'SRAM', 'DRAM', 'ROM', 'RAM', '闪存',
        '存储层次', '局部性', '存储容量', '地址线', '数据线', '按字节编址',
        '按字编址', '存储芯片', '扩展', '刷新', '存取周期'
    ],
    'Cache与虚拟存储': [
        'Cache', '缓存', '命中率', '直接映射', '全相联', '组相联', '块大小',
        'Tag', 'Index', '偏移', '写回', '写直达', '替换算法', 'LRU',
        '虚拟存储器', '页表', 'TLB', '快表', '虚地址', '实地址', '页号',
        '页内偏移', '缺页', '段表', '段页式'
    ],
    'CPU与控制器': [
        'CPU', '控制器', '运算器', '微程序', '微指令', '微操作', '硬连线',
        '控制存储器', '微地址', '微程序计数器', '程序计数器', 'PC',
        '指令寄存器', 'IR', '数据通路', '寄存器堆', '暂存器'
    ],
    '指令流水线': [
        '流水线', '流水段', '结构相关', '数据相关', '控制相关', 'RAW',
        'WAR', 'WAW', 'RAR', '旁路', '转发', '阻塞', '流水线冲突',
        '吞吐率', '加速比', '流水线效率', '超标量'
    ],
    '总线': [
        '总线', '数据总线', '地址总线', '控制总线', '总线仲裁', '集中式',
        '分布式', 'PCI', '带宽', '总线周期', '同步', '异步'
    ],
    'I/O与中断': [
        'I/O', '输入输出', '中断', 'DMA', '中断向量', '中断屏蔽', '中断嵌套',
        '中断优先级', '关中断', '开中断', '保存断点', '中断响应',
        '程序查询', '程序中断', '通道', '外设', '接口'
    ],

    # ─── CS 其他 ───
    '数据结构': ['链表', '栈', '队列', '树', '图', '排序', '查找', '哈希', '复杂度', 'algorithm',
                '邻接矩阵', '邻接表', '入度', '出度', '拓扑排序', '最短路径'],
    '算法': ['递归', '动态规划', '贪心', '回溯', '分治', 'DP', 'BFS', 'DFS', 'binary search'],
    '计算机网络': ['TCP', 'IP', 'HTTP', 'DNS', '路由', '协议', 'OSI', 'network'],
    '操作系统': ['进程', '线程', '死锁', '调度', '文件系统', 'OS', 'process', 'thread', '同步', '互斥'],
    '数据库': ['SQL', '索引', '事务', '范式', 'JOIN', 'database', 'query'],

    # ─── 物理 ───
    '力学': ['牛顿', '受力', '动量', '能量', '功', '摩擦力', 'Newton'],
    '电磁学': ['电场', '磁场', '电势', '电流', '麦克斯韦', '电磁感应', 'electric', 'magnetic'],
    '热学': ['热力学', '熵', '温度', '热传导', '理想气体', 'thermodynamics'],
    '光学': ['折射', '反射', '干涉', '衍射', '偏振', 'optics', 'refraction'],

    # ─── 经济 ───
    '经济学': ['供需', '弹性', '边际', 'GDP', '通胀', '垄断', '博弈', 'economics'],
}


def detect_chapter(text: str) -> str:
    """根据文本中的关键词判断所属章节"""
    text_lower = text.lower()
    scores = {}
    for chapter, keywords in CHAPTER_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > 0:
            scores[chapter] = score
    if scores:
        return max(scores, key=scores.get)
    return '未分类'


def determine_raid_value(frequency: int, score_impact: float, total_score: float = 100) -> str:
    """根据频次和分值占比判定突击价值"""
    if total_score <= 0:
        total_score = 100
    pct = (score_impact / total_score) * 100
    if frequency >= 2 and pct > 15:
        return '必拿'
    elif frequency >= 1 and pct > 5:
        return '争取'
    else:
        return '可弃'


def analyze_materials(exam_id: int, raw_text: str, total_score: float = 100):
    """
    分析用户输入的真题/资料文本，拆解考点并写入数据库。

    Args:
        exam_id: 科目ID
        raw_text: 用户粘贴的题目文本
        total_score: 试卷总分（默认100）
    """
    # 清除旧考点
    clear_knowledge_points(exam_id)

    # 按题目切分（以数字序号、题号等为分隔）
    questions = re.split(r'\n\s*(?:\d+[\.\)、]|[一二三四五六七八九十]+[、．.])', raw_text)
    questions = [q.strip() for q in questions if len(q.strip()) > 10]

    if not questions:
        # 如果切不出来，把整段当作一个考点处理
        questions = [raw_text]

    # 统计每章出现频率和分值
    chapter_stats = {}  # chapter -> {freq, score, topics}

    for q in questions:
        chapter = detect_chapter(q)
        if chapter not in chapter_stats:
            chapter_stats[chapter] = {'freq': 0, 'score': 0, 'topics': []}
        chapter_stats[chapter]['freq'] += 1
        # 尝试提取分值（如 "10分"、"（15分）"）
        score_match = re.findall(r'[（(]?\s*(\d+)\s*分\s*[）)]?', q)
        if score_match:
            chapter_stats[chapter]['score'] += sum(int(s) for s in score_match)

    # 如果没提取到分值，按平均分配
    if all(s['score'] == 0 for s in chapter_stats.values()):
        avg_score = total_score / len(chapter_stats) if chapter_stats else total_score
        for ch in chapter_stats:
            chapter_stats[ch]['score'] = avg_score

    # 写入数据库
    for chapter, stats in chapter_stats.items():
        raid = determine_raid_value(stats['freq'], stats['score'], total_score)
        upsert_kp(
            exam_id=exam_id,
            chapter=chapter,
            topic=chapter,  # topic 和 chapter 合并，用户可以手动拆分
            frequency=stats['freq'],
            difficulty=2 if raid == '必拿' else 1,
            score_impact=stats['score'],
            raid_value=raid
        )

    return chapter_stats


def manual_add_kp(exam_id: int, chapter: str, topic: str,
                  difficulty: int = 1, score_impact: float = 0,
                  frequency: int = 0, raid_value: str = '争取'):
    """手动添加考点"""
    if raid_value == 'auto':
        raid_value = determine_raid_value(frequency, score_impact)
    upsert_kp(exam_id, chapter, topic, frequency, difficulty, score_impact, raid_value)
