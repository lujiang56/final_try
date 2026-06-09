"""个人资料库 — 复习资料的查看 / 下载 / 删除"""

from flask import Blueprint, render_template, request, redirect, url_for, Response
from database import get_materials, get_material, delete_material
import re

library_bp = Blueprint('library', __name__)


@library_bp.route('/library')
def library():
    """个人复习资料库 — 展示所有生成的资料"""
    materials = get_materials()
    # 按科目分组
    exams_materials = {}
    for m in materials:
        ename = m.get('exam_name', '未知科目')
        if ename not in exams_materials:
            exams_materials[ename] = []
        exams_materials[ename].append(m)

    type_counts = {}
    for m in materials:
        t = m.get('material_type', 'summary')
        type_counts[t] = type_counts.get(t, 0) + 1

    return render_template('library.html',
                           materials=materials,
                           exams_materials=exams_materials,
                           type_counts=type_counts)


@library_bp.route('/materials/<int:material_id>')
def material_view(material_id):
    """查看单份复习资料"""
    material = get_material(material_id)
    if not material:
        return redirect(url_for('library.library'))

    return render_template('material_view.html', material=material)


@library_bp.route('/materials/<int:material_id>/download')
def material_download(material_id):
    """下载复习资料为 .txt 文件"""
    material = get_material(material_id)
    if not material or not material.get('content_text'):
        return redirect(url_for('library.library'))

    safe_title = material['title'].replace(' ', '_').replace('/', '_').replace('\\', '_')
    safe_title = re.sub(r'[<>:"|?*]', '', safe_title)
    filename = f"{safe_title}.txt"

    return Response(
        material['content_text'],
        mimetype='text/plain; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@library_bp.route('/materials/<int:material_id>/delete', methods=['POST'])
def material_delete(material_id):
    """删除复习资料"""
    delete_material(material_id)
    return redirect(url_for('library.library'))
