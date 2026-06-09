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
                    // 局部更新进度条和统计数字
                    fetch(`/api/exam/${examId}/progress`).then(r => r.json()).then(stats => {
                        const total = stats.tasks_total || 1;
                        const done = stats.tasks_done || 0;
                        const pct = Math.round(done / total * 100);
                        const progressBar = document.querySelector('.progress-bar');
                        if (progressBar) progressBar.style.width = pct + '%';
                        const pctHeading = document.querySelector('h3');
                        if (pctHeading) {
                            pctHeading.innerHTML = `${pct}% <small class="text-muted fs-6">完成</small>`;
                        }
                        const statsSmall = document.querySelector('.card-body .small.text-muted');
                        if (statsSmall && statsSmall.textContent.includes('分钟')) {
                            // skip — only update done/total count
                        }
                        // Update done/total text
                        const doneTotalText = document.querySelector('.card-body small.text-muted:not([class*="text-danger"]):not([class*="text-success"]):not([class*="text-warning"])');
                        if (doneTotalText && doneTotalText.textContent.includes('/')) {
                            doneTotalText.textContent = `${done}/${total} 个任务已完成`;
                        }
                    });
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
    // 跳过 PPT 分析页面的上传表单（它有自己的 XHR 逻辑）
    document.querySelectorAll('form').forEach(function (form) {
        if (form.id === 'upload-form') return;  // ppt_analysis.html 专用表单，跳过
        form.addEventListener('submit', function () {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                setTimeout(() => { submitBtn.disabled = false; }, 2000);
            }
        });
    });

    // ─── PPT Upload Zone（仅 materials.html 使用，ppt_analysis.html 有自己的实现）───
    if (document.getElementById('ppt-upload-form')) {
        const uploadZone = document.getElementById('upload-zone');
        const fileInput = document.getElementById('ppt-file-input');
        const fileInfo = document.getElementById('file-info');
        const fileName = document.getElementById('file-name');
        const fileSize = document.getElementById('file-size');
        const uploadBtn = document.getElementById('upload-btn');

        if (uploadZone && fileInput) {
            uploadZone.addEventListener('click', function () {
                fileInput.click();
            });

            uploadZone.addEventListener('dragover', function (e) {
                e.preventDefault();
                uploadZone.classList.add('dragover');
            });
            uploadZone.addEventListener('dragleave', function () {
                uploadZone.classList.remove('dragover');
            });
            uploadZone.addEventListener('drop', function (e) {
                e.preventDefault();
                uploadZone.classList.remove('dragover');
                if (e.dataTransfer.files.length) {
                    fileInput.files = e.dataTransfer.files;
                    updateFileDisplay(e.dataTransfer.files[0]);
                }
            });

            fileInput.addEventListener('change', function () {
                if (fileInput.files.length) {
                    updateFileDisplay(fileInput.files[0]);
                }
            });

            function updateFileDisplay(file) {
                fileName.textContent = file.name;
                fileSize.textContent = formatFileSize(file.size);
                fileInfo.style.display = '';
                uploadBtn.style.display = '';
            }

            function formatFileSize(bytes) {
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / 1048576).toFixed(1) + ' MB';
            }
        }
    }

});
