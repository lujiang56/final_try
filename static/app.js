/**
 * 期末突击 — 前端交互逻辑
 */

document.addEventListener('DOMContentLoaded', function () {

    // ─── 计划任务：AJAX 切换完成状态 ───
    document.querySelectorAll('.task-toggle').forEach(function (checkbox) {
        checkbox.addEventListener('change', function () {
            const taskId = this.dataset.taskId;
            const examId = this.dataset.examId;
            const label = this.nextElementSibling;

            fetch(`/exam/${examId}/plan/toggle/${taskId}`, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.ok) {
                    // 切换视觉效果
                    const parentDiv = this.closest('.form-check');
                    if (this.checked) {
                        parentDiv.classList.add('bg-success', 'bg-opacity-10');
                        label.classList.add('text-decoration-line-through', 'text-secondary');
                    } else {
                        parentDiv.classList.remove('bg-success', 'bg-opacity-10');
                        label.classList.remove('text-decoration-line-through', 'text-secondary');
                    }
                    // 简单刷新进度（可优化为局部更新）
                    setTimeout(() => location.reload(), 300);
                }
            })
            .catch(err => console.error('Toggle error:', err));
        });
    });

    // ─── 倒计时实时更新 ───
    document.querySelectorAll('[data-exam-date]').forEach(function (el) {
        const examDate = new Date(el.dataset.examDate);
        const now = new Date();
        const daysLeft = Math.ceil((examDate - now) / (1000 * 60 * 60 * 24));
        if (daysLeft >= 0) {
            el.textContent = `倒计时 ${daysLeft} 天`;
            if (daysLeft <= 2) {
                el.classList.add('text-danger', 'fw-bold');
            } else if (daysLeft <= 5) {
                el.classList.add('text-warning');
            } else {
                el.classList.add('text-success');
            }
        } else {
            el.textContent = '已考完 ✅';
            el.classList.add('text-success');
        }
    });

    // ─── 删除确认 ───
    document.querySelectorAll('[data-confirm]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm(this.dataset.confirm || '确定要执行此操作吗？')) {
                e.preventDefault();
            }
        });
    });

    // ─── 焦点自动定位 ───
    const autofocus = document.querySelector('[autofocus]');
    if (autofocus) {
        autofocus.focus();
    }

    // ─── 表单提交禁用重复提交 ───
    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function () {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                setTimeout(() => { submitBtn.disabled = false; }, 2000);
            }
        });
    });

});
