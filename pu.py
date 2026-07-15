import sys
import os
import re
import openpyxl
from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from moviepy import VideoFileClip
import pandas as pd
from datetime import datetime


class ScanWorker(QObject):
    """扫描视频的工作线程"""
    progress = pyqtSignal(int, str, int, str)
    finished = pyqtSignal(list, float, dict)
    error = pyqtSignal(str)

    def __init__(self, directory, video_extensions):
        super().__init__()
        self.directory = directory
        self.video_extensions = video_extensions
        self.is_cancelled = False

    def cancel(self):
        """取消扫描"""
        self.is_cancelled = True

    def scan(self):
        """扫描视频文件（递归）"""
        try:
            video_files = []
            dir_stats = {}

            for root, dirs, files in os.walk(self.directory):
                # 检查是否被取消
                if self.is_cancelled:
                    self.finished.emit([], 0, {})
                    return

                dirs[:] = [d for d in dirs if not d.startswith('.')]

                dir_videos = []
                for file in files:
                    # 检查是否被取消
                    if self.is_cancelled:
                        self.finished.emit([], 0, {})
                        return

                    file_path = os.path.join(root, file)
                    ext = Path(file).suffix.lower()
                    if ext in self.video_extensions:
                        video_files.append(file_path)
                        dir_videos.append(file_path)

                if dir_videos:
                    rel_path = os.path.relpath(root, self.directory)
                    if rel_path == '.':
                        rel_path = '根目录'
                    dir_stats[rel_path] = {
                        'count': len(dir_videos),
                        'files': dir_videos,
                        'duration': 0
                    }

            if not video_files:
                self.finished.emit([], 0, {})
                return

            video_info = []
            total_duration = 0

            for i, video_path in enumerate(video_files):
                # 检查是否被取消
                if self.is_cancelled:
                    self.finished.emit([], 0, {})
                    return

                filename = os.path.basename(video_path)
                rel_path = os.path.relpath(os.path.dirname(video_path), self.directory)
                if rel_path == '.':
                    rel_path = '根目录'

                self.progress.emit(i, filename, len(video_files), rel_path)

                try:
                    clip = VideoFileClip(video_path)
                    duration = clip.duration
                    clip.close()
                    if duration is not None:
                        total_duration += duration
                        video_info.append((video_path, filename, rel_path, duration))
                        if rel_path in dir_stats:
                            dir_stats[rel_path]['duration'] += duration
                    else:
                        video_info.append((video_path, filename, rel_path, None))
                except Exception as e:
                    print(f'读取视频 {video_path} 失败: {e}')
                    video_info.append((video_path, filename, rel_path, None))

            # 如果不是被取消的，才发送完成信号
            if not self.is_cancelled:
                self.finished.emit(video_info, total_duration, dir_stats)

        except Exception as e:
            if not self.is_cancelled:
                self.error.emit(str(e))


class RenameWorker(QObject):
    """重命名工作线程"""
    progress = pyqtSignal(int, int, str, str)
    finished = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(self, file_list):
        super().__init__()
        self.file_list = file_list
        self.is_cancelled = False

    def cancel(self):
        """取消重命名"""
        self.is_cancelled = True

    def rename_files(self):
        """执行重命名"""
        try:
            success_count = 0
            total = len(self.file_list)

            for i, (old_path, old_name, new_name) in enumerate(self.file_list):
                if self.is_cancelled:
                    self.finished.emit(success_count, total)
                    return

                if new_name == old_name:
                    self.progress.emit(i, total, old_name, '跳过（未改变）')
                    success_count += 1
                    continue

                dir_path = os.path.dirname(old_path)
                new_path = os.path.join(dir_path, new_name)

                if os.path.exists(new_path):
                    self.progress.emit(i, total, old_name, '⚠️ 目标文件已存在')
                    continue

                try:
                    os.rename(old_path, new_path)
                    success_count += 1
                    self.progress.emit(i, total, old_name, f'✅ -> {new_name}')
                except Exception as e:
                    self.progress.emit(i, total, old_name, f'❌ 错误: {str(e)}')

            if not self.is_cancelled:
                self.finished.emit(success_count, total)

        except Exception as e:
            if not self.is_cancelled:
                self.error.emit(str(e))


class VideoDurationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_dir = os.getcwd()
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv',
                                 '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
                                 '.3gp', '.ogv', '.ts', '.mts', '.m2ts'}
        self.worker_thread = None
        self.worker = None
        self.video_data = []
        self.dir_stats = {}
        self.selected_files = []
        self.is_scanning = False
        self.is_renaming = False
        self.initUI()

    def initUI(self):
        self.setWindowTitle('视频时长查看器 - 批量改名 + 导出Excel')
        self.setGeometry(100, 100, 1300, 850)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)

        # ===== 顶部控制面板 =====
        control_panel = QHBoxLayout()
        self.dir_label = QLabel(f'📁 当前目录: {self.current_dir}')
        self.dir_label.setStyleSheet('font-size: 12px; padding: 5px;')
        control_panel.addWidget(self.dir_label, 1)
        control_panel.addStretch()

        self.select_btn = QPushButton('📂 选择目录')
        self.select_btn.clicked.connect(self.select_directory)
        control_panel.addWidget(self.select_btn)

        self.scan_btn = QPushButton('🔍 扫描视频')
        self.scan_btn.clicked.connect(self.scan_videos)
        control_panel.addWidget(self.scan_btn)

        # 取消扫描按钮
        self.cancel_btn = QPushButton('⛔ 取消扫描')
        self.cancel_btn.clicked.connect(self.cancel_scan)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet('background-color: #f44336;')
        control_panel.addWidget(self.cancel_btn)

        self.export_btn = QPushButton('📊 导出Excel')
        self.export_btn.clicked.connect(self.export_to_excel)
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet('background-color: #FF5722;')
        control_panel.addWidget(self.export_btn)

        main_layout.addLayout(control_panel)

        # ===== 重命名工具面板 =====
        rename_frame = QFrame()
        rename_frame.setStyleSheet('background-color: #fff3e0; border-radius: 5px; padding: 10px;')
        rename_layout = QHBoxLayout(rename_frame)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['去除前缀', '正则表达式替换', '自定义替换'])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        rename_layout.addWidget(QLabel('模式:'))
        rename_layout.addWidget(self.mode_combo)

        rename_layout.addWidget(QLabel('查找:'))
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText('例如: xxxx.com课程- 或 ^(.*?) - ')
        self.find_input.setMinimumWidth(200)
        rename_layout.addWidget(self.find_input)

        rename_layout.addWidget(QLabel('替换为:'))
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText('替换内容或留空删除')
        self.replace_input.setMinimumWidth(200)
        rename_layout.addWidget(self.replace_input)

        self.preview_btn = QPushButton('👁️ 预览')
        self.preview_btn.clicked.connect(self.preview_rename)
        self.preview_btn.setEnabled(False)
        rename_layout.addWidget(self.preview_btn)

        self.rename_btn = QPushButton('✏️ 执行重命名')
        self.rename_btn.clicked.connect(self.execute_rename)
        self.rename_btn.setEnabled(False)
        self.rename_btn.setStyleSheet('background-color: #FF9800;')
        rename_layout.addWidget(self.rename_btn)

        # 取消重命名按钮
        self.cancel_rename_btn = QPushButton('⛔ 取消重命名')
        self.cancel_rename_btn.clicked.connect(self.cancel_rename)
        self.cancel_rename_btn.setEnabled(False)
        self.cancel_rename_btn.setStyleSheet('background-color: #f44336;')
        rename_layout.addWidget(self.cancel_rename_btn)

        help_btn = QPushButton('❓')
        help_btn.setMaximumWidth(30)
        help_btn.clicked.connect(self.show_help)
        rename_layout.addWidget(help_btn)

        main_layout.addWidget(rename_frame)

        # ===== 进度条 =====
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ===== 表格 =====
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['选择', '📁 目录', '📹 文件名', '⏱️ 时长', '📊 大小'])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.MultiSelection)

        main_layout.addWidget(self.table)

        # ===== 状态栏 =====
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)

        self.status_label = QLabel('✅ 就绪')
        self.status_label.setStyleSheet('font-size: 12px; padding: 5px;')
        status_layout.addWidget(self.status_label, 1)

        # 进度信息
        self.progress_info_label = QLabel('')
        self.progress_info_label.setStyleSheet('font-size: 12px; color: #2196F3; padding: 5px;')
        status_layout.addWidget(self.progress_info_label)

        self.total_label = QLabel('⏱️ 总时长: 00:00:00')
        self.total_label.setStyleSheet('font-size: 13px; font-weight: bold; color: #2196F3;')
        status_layout.addWidget(self.total_label)

        self.file_count_label = QLabel('📄 文件数: 0')
        self.file_count_label.setStyleSheet('font-size: 13px; font-weight: bold; color: #4CAF50;')
        status_layout.addWidget(self.file_count_label)

        self.dir_count_label = QLabel('📁 目录数: 0')
        self.dir_count_label.setStyleSheet('font-size: 13px; font-weight: bold; color: #FF9800;')
        status_layout.addWidget(self.dir_count_label)

        main_layout.addWidget(status_frame)

        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f8f9fa;
                gridline-color: #dee2e6;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 8px;
                border: 1px solid #dee2e6;
                font-weight: bold;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
            QComboBox {
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 12px;
            }
        """)

        self.video_data = []
        self.rename_preview = []

    def on_mode_changed(self, index):
        mode = self.mode_combo.currentText()
        if mode == '去除前缀':
            self.find_input.setPlaceholderText('例如: xxxx.com课程-')
            self.replace_input.setPlaceholderText('留空删除前缀')
        elif mode == '正则表达式替换':
            self.find_input.setPlaceholderText('例如: ^(.*?)-\\s*(.+)$')
            self.replace_input.setPlaceholderText('例如: \\2 (保留第二部分)')
        else:
            self.find_input.setPlaceholderText('要替换的文本')
            self.replace_input.setPlaceholderText('替换为')

    def show_help(self):
        help_text = """
        <h3>📖 批量改名使用帮助</h3>

        <b>1. 去除前缀模式</b><br>
        查找: xxxx.com课程-<br>
        替换为: (留空)<br>
        效果: "xxxx.com课程-7.常用命令" → "7.常用命令"

        <b>2. 正则表达式替换模式</b><br>
        查找: ^(.*?)-\\s*(.+)$<br>
        替换为: \\2<br>
        效果: "课程-7.常用命令" → "7.常用命令"

        <b>3. 自定义替换模式</b><br>
        查找: 旧文本<br>
        替换为: 新文本<br>
        效果: 简单文本替换

        <b>💡 导出Excel功能:</b><br>
        • 导出所有视频文件信息<br>
        • 包含文件名、路径、时长、大小等<br>
        • 支持导出重命名映射表

        <b>⛔ 取消功能:</b><br>
        • 扫描过程中可随时点击"取消扫描"<br>
        • 重命名过程中可随时点击"取消重命名"
        """
        QMessageBox.information(self, '帮助', help_text)

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, '选择目录', self.current_dir)
        if directory:
            self.current_dir = directory
            self.dir_label.setText(f'📁 当前目录: {directory}')
            self.clear_results()
            self.preview_btn.setEnabled(False)
            self.rename_btn.setEnabled(False)
            self.export_btn.setEnabled(False)

    def clear_results(self):
        self.table.setRowCount(0)
        self.total_label.setText('⏱️ 总时长: 00:00:00')
        self.file_count_label.setText('📄 文件数: 0')
        self.dir_count_label.setText('📁 目录数: 0')
        self.status_label.setText('✅ 目录已更新，请点击扫描视频')
        self.video_data = []
        self.rename_preview = []
        self.progress_info_label.setText('')

    def format_duration(self, seconds):
        if seconds is None or seconds < 0:
            return '❌ 无法读取'
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f'{hours:02d}:{minutes:02d}:{secs:02d}'
        return f'{minutes:02d}:{secs:02d}'

    def format_duration_seconds(self, seconds):
        if seconds is None or seconds < 0:
            return None
        return round(seconds, 2)

    def format_size(self, size_bytes):
        if size_bytes is None:
            return '未知'
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f'{size_bytes:.2f} {unit}'
            size_bytes /= 1024.0
        return f'{size_bytes:.2f} PB'

    def get_file_size(self, filepath):
        try:
            return os.path.getsize(filepath)
        except:
            return None

    def scan_videos(self):
        if self.is_scanning:
            return

        if not os.path.exists(self.current_dir):
            QMessageBox.warning(self, '错误', '目录不存在，请重新选择')
            return

        self.is_scanning = True
        self.select_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.preview_btn.setEnabled(False)
        self.rename_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.cancel_rename_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText('⏳ 正在扫描视频文件（递归搜索中...）')
        self.progress_info_label.setText('准备扫描...')
        self.table.setRowCount(0)
        self.video_data = []
        self.dir_stats = {}

        self.worker_thread = QThread()
        self.worker = ScanWorker(self.current_dir, self.video_extensions)
        self.worker.moveToThread(self.worker_thread)

        self.worker.progress.connect(self.update_scan_progress)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.error.connect(self.on_scan_error)
        self.worker_thread.started.connect(self.worker.scan)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def cancel_scan(self):
        """取消扫描"""
        if self.worker and self.is_scanning:
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.status_label.setText('⏳ 正在取消扫描...')
            self.progress_info_label.setText('正在取消...')

    def update_scan_progress(self, index, filename, total, rel_path):
        self.status_label.setText(f'⏳ 正在处理: [{rel_path}] {filename} ({index + 1}/{total})')
        self.progress_info_label.setText(f'进度: {index + 1}/{total}')
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(index + 1)

    def on_scan_finished(self, video_info, total_duration, dir_stats):
        self.is_scanning = False
        self.cancel_btn.setEnabled(False)

        # 检查是否被取消
        if self.worker and self.worker.is_cancelled:
            self.status_label.setText('⛔ 扫描已取消')
            self.progress_info_label.setText('已取消')
            self.progress_bar.setVisible(False)
            self.select_btn.setEnabled(True)
            self.scan_btn.setEnabled(True)
            self.export_btn.setEnabled(False)
            return

        try:
            self.video_data = video_info
            self.dir_stats = dir_stats

            if not video_info:
                self.status_label.setText('⚠️ 未找到视频文件')
                self.progress_info_label.setText('未找到文件')
                self.progress_bar.setVisible(False)
                self.select_btn.setEnabled(True)
                self.scan_btn.setEnabled(True)
                return

            self.table.setRowCount(len(video_info))

            for i, (filepath, filename, rel_path, duration) in enumerate(video_info):
                check_item = QTableWidgetItem()
                check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                check_item.setCheckState(Qt.Unchecked)
                self.table.setItem(i, 0, check_item)

                dir_item = QTableWidgetItem(rel_path)
                dir_item.setFlags(dir_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 1, dir_item)

                name_item = QTableWidgetItem(filename)
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 2, name_item)

                if duration is not None:
                    formatted_time = self.format_duration(duration)
                    time_item = QTableWidgetItem(formatted_time)
                    time_item.setForeground(QColor(46, 125, 50))
                else:
                    formatted_time = '❌ 无法读取'
                    time_item = QTableWidgetItem(formatted_time)
                    time_item.setForeground(QColor(198, 40, 40))
                time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 3, time_item)

                size = self.get_file_size(filepath)
                size_str = self.format_size(size) if size else '未知'
                size_item = QTableWidgetItem(size_str)
                size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 4, size_item)

            total_formatted = self.format_duration(total_duration)
            self.total_label.setText(f'⏱️ 总时长: {total_formatted}')
            self.file_count_label.setText(f'📄 文件数: {len(video_info)}')
            self.dir_count_label.setText(f'📁 目录数: {len(dir_stats)}')

            self.table.resizeColumnsToContents()
            self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

            self.status_label.setText(f'✅ 扫描完成，共找到 {len(video_info)} 个视频文件')
            self.progress_info_label.setText(f'完成: {len(video_info)} 个文件')
            self.preview_btn.setEnabled(True)
            self.rename_btn.setEnabled(False)
            self.export_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, '错误', f'显示结果时发生错误: {str(e)}')
        finally:
            self.progress_bar.setVisible(False)
            self.select_btn.setEnabled(True)
            self.scan_btn.setEnabled(True)

    def get_selected_files(self):
        selected = []
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.Checked:
                filepath = self.video_data[i][0]
                old_name = self.video_data[i][1]
                selected.append((i, filepath, old_name))
        return selected

    def preview_rename(self):
        selected = self.get_selected_files()
        if not selected:
            QMessageBox.warning(self, '警告', '请先选择要重命名的文件（勾选复选框）')
            return

        mode = self.mode_combo.currentText()
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()

        if not find_text and mode != '去除前缀':
            QMessageBox.warning(self, '警告', '请输入查找内容')
            return

        preview_list = []
        for row, filepath, old_name in selected:
            new_name = self.generate_new_name(old_name, mode, find_text, replace_text)
            preview_list.append((row, filepath, old_name, new_name))

        self.show_preview_dialog(preview_list)

    def generate_new_name(self, old_name, mode, find_text, replace_text):
        name, ext = os.path.splitext(old_name)

        if mode == '去除前缀':
            if find_text and name.startswith(find_text):
                new_name = name[len(find_text):] + ext
                return new_name
            return old_name

        elif mode == '正则表达式替换':
            try:
                if find_text:
                    pattern = re.compile(find_text)
                    new_name = pattern.sub(replace_text, name) + ext
                    return new_name
            except re.error as e:
                return f'❌ 正则错误: {e}'
            return old_name

        else:
            if find_text:
                new_name = name.replace(find_text, replace_text) + ext
                return new_name
            return old_name

    def show_preview_dialog(self, preview_list):
        dialog = QDialog(self)
        dialog.setWindowTitle('重命名预览')
        dialog.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout(dialog)

        info_label = QLabel(f'将重命名 {len(preview_list)} 个文件，请确认修改:')
        layout.addWidget(info_label)

        preview_table = QTableWidget()
        preview_table.setColumnCount(3)
        preview_table.setHorizontalHeaderLabels(['原文件名', '新文件名', '状态'])
        preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        preview_table.setRowCount(len(preview_list))

        for i, (row, filepath, old_name, new_name) in enumerate(preview_list):
            preview_table.setItem(i, 0, QTableWidgetItem(old_name))
            preview_table.setItem(i, 1, QTableWidgetItem(new_name))

            if new_name == old_name:
                status_item = QTableWidgetItem('⏭️ 未改变')
                status_item.setForeground(QColor(255, 152, 0))
            else:
                status_item = QTableWidgetItem('✏️ 将修改')
                status_item.setForeground(QColor(46, 125, 50))
            preview_table.setItem(i, 2, status_item)

        layout.addWidget(preview_table)

        button_box = QDialogButtonBox()
        confirm_btn = button_box.addButton('确认执行', QDialogButtonBox.AcceptRole)
        cancel_btn = button_box.addButton('取消', QDialogButtonBox.RejectRole)
        confirm_btn.setStyleSheet('background-color: #FF9800;')

        button_box.accepted.connect(lambda: self.execute_rename_from_preview(preview_list, dialog))
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.exec_()

    def execute_rename_from_preview(self, preview_list, dialog):
        self.rename_list = preview_list
        dialog.accept()
        self.execute_rename()

    def execute_rename(self):
        if self.is_renaming:
            return

        if not hasattr(self, 'rename_list') or not self.rename_list:
            selected = self.get_selected_files()
            if not selected:
                QMessageBox.warning(self, '警告', '请先选择要重命名的文件')
                return

            mode = self.mode_combo.currentText()
            find_text = self.find_input.text()
            replace_text = self.replace_input.text()

            self.rename_list = []
            for row, filepath, old_name in selected:
                new_name = self.generate_new_name(old_name, mode, find_text, replace_text)
                self.rename_list.append((row, filepath, old_name, new_name))

        reply = QMessageBox.question(
            self, '确认重命名',
            f'确定要重命名 {len(self.rename_list)} 个文件吗？\n此操作不可撤销！',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            self.rename_list = []
            return

        self.is_renaming = True
        self.set_controls_enabled(False)
        self.cancel_rename_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.rename_list))
        self.status_label.setText('⏳ 正在重命名文件...')
        self.progress_info_label.setText('准备重命名...')

        self.rename_thread = QThread()
        self.rename_worker = RenameWorker(
            [(filepath, old_name, new_name) for _, filepath, old_name, new_name in self.rename_list]
        )
        self.rename_worker.moveToThread(self.rename_thread)

        self.rename_worker.progress.connect(self.update_rename_progress)
        self.rename_worker.finished.connect(self.on_rename_finished)
        self.rename_worker.error.connect(self.on_rename_error)
        self.rename_thread.started.connect(self.rename_worker.rename_files)
        self.rename_thread.finished.connect(self.rename_thread.deleteLater)

        self.rename_thread.start()

    def cancel_rename(self):
        """取消重命名"""
        if self.rename_worker and self.is_renaming:
            self.rename_worker.cancel()
            self.cancel_rename_btn.setEnabled(False)
            self.status_label.setText('⏳ 正在取消重命名...')
            self.progress_info_label.setText('正在取消...')

    def update_rename_progress(self, index, total, old_name, status):
        self.progress_bar.setValue(index + 1)
        self.progress_info_label.setText(f'进度: {index + 1}/{total}')
        self.status_label.setText(f'⏳ 重命名: {status} ({index + 1}/{total})')

    def on_rename_finished(self, success_count, total):
        self.is_renaming = False
        self.cancel_rename_btn.setEnabled(False)

        # 检查是否被取消
        if self.rename_worker and self.rename_worker.is_cancelled:
            self.status_label.setText('⛔ 重命名已取消')
            self.progress_info_label.setText('已取消')
            self.progress_bar.setVisible(False)
            self.set_controls_enabled(True)
            return

        self.status_label.setText(f'✅ 重命名完成，成功 {success_count}/{total} 个文件')
        self.progress_info_label.setText(f'完成: {success_count}/{total}')
        self.progress_bar.setVisible(False)
        self.set_controls_enabled(True)
        self.rename_list = []
        # 重新扫描以更新显示
        self.scan_videos()

    def on_rename_error(self, error_msg):
        self.is_renaming = False
        self.cancel_rename_btn.setEnabled(False)
        QMessageBox.critical(self, '错误', f'重命名过程中发生错误: {error_msg}')
        self.progress_bar.setVisible(False)
        self.set_controls_enabled(True)

    def on_scan_error(self, error_msg):
        self.is_scanning = False
        self.cancel_btn.setEnabled(False)
        QMessageBox.critical(self, '错误', f'扫描过程中发生错误: {error_msg}')
        self.status_label.setText(f'❌ 扫描出错: {error_msg}')
        self.progress_info_label.setText('出错')
        self.progress_bar.setVisible(False)
        self.select_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)

    def set_controls_enabled(self, enabled):
        self.select_btn.setEnabled(enabled)
        self.scan_btn.setEnabled(enabled)
        self.preview_btn.setEnabled(enabled)
        self.rename_btn.setEnabled(enabled)
        self.export_btn.setEnabled(enabled)

    # ==================== 导出Excel功能 ====================

    def export_to_excel(self):
        """导出到Excel"""
        if not self.video_data:
            QMessageBox.warning(self, '警告', '没有数据可导出，请先扫描视频')
            return

        export_type, ok = QInputDialog.getItem(
            self, '选择导出类型',
            '请选择要导出的内容:',
            ['视频详细信息', '目录统计信息', '重命名映射表', '完整报告'],
            0, False
        )

        if not ok:
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name = f'视频信息_{timestamp}.xlsx'

        file_path, _ = QFileDialog.getSaveFileName(
            self, '保存Excel文件',
            default_name,
            'Excel文件 (*.xlsx)'
        )

        if not file_path:
            return

        try:
            self.status_label.setText('⏳ 正在生成Excel文件...')
            self.progress_info_label.setText('生成中...')
            QApplication.processEvents()

            if export_type == '视频详细信息':
                self.export_video_details(file_path)
            elif export_type == '目录统计信息':
                self.export_directory_stats(file_path)
            elif export_type == '重命名映射表':
                self.export_rename_mapping(file_path)
            else:
                self.export_full_report(file_path)

            self.status_label.setText(f'✅ Excel导出成功: {os.path.basename(file_path)}')
            self.progress_info_label.setText('导出完成')
            QMessageBox.information(self, '导出成功', f'文件已保存到:\n{file_path}')

        except Exception as e:
            QMessageBox.critical(self, '导出失败', f'导出Excel时发生错误:\n{str(e)}')
            self.status_label.setText('❌ 导出失败')
            self.progress_info_label.setText('导出失败')

    def export_video_details(self, file_path):
        """导出视频详细信息"""
        data = []
        for filepath, filename, rel_path, duration in self.video_data:
            size = self.get_file_size(filepath)
            data.append({
                '序号': len(data) + 1,
                '目录': rel_path,
                '文件名': filename,
                '完整路径': filepath,
                '时长(秒)': self.format_duration_seconds(duration),
                '时长(格式化)': self.format_duration(duration),
                '文件大小(字节)': size,
                '文件大小(格式化)': self.format_size(size) if size else '未知',
                '扩展名': Path(filename).suffix.lower(),
                '状态': '正常' if duration is not None else '无法读取'
            })

        df = pd.DataFrame(data)
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='视频信息', index=False)

            stats_df = pd.DataFrame({
                '统计项': ['总文件数', '成功读取', '无法读取', '总时长(秒)', '总时长(格式化)'],
                '数值': [
                    len(data),
                    sum(1 for d in data if d['状态'] == '正常'),
                    sum(1 for d in data if d['状态'] == '无法读取'),
                    sum(d['时长(秒)'] for d in data if d['时长(秒)'] is not None),
                    self.format_duration(sum(d['时长(秒)'] for d in data if d['时长(秒)'] is not None))
                ]
            })
            stats_df.to_excel(writer, sheet_name='统计信息', index=False)

    def export_directory_stats(self, file_path):
        """导出目录统计信息"""
        data = []
        for dir_name, stats in sorted(self.dir_stats.items()):
            data.append({
                '目录': dir_name,
                '视频数量': stats['count'],
                '总时长(秒)': round(stats['duration'], 2),
                '总时长(格式化)': self.format_duration(stats['duration']),
                '文件列表': '\n'.join([os.path.basename(f) for f in stats['files'][:5]]) +
                            ('\n...' if len(stats['files']) > 5 else '')
            })

        df = pd.DataFrame(data)
        df.to_excel(file_path, sheet_name='目录统计', index=False)

    def export_rename_mapping(self, file_path):
        """导出重命名映射表"""
        selected = self.get_selected_files()
        if not selected:
            QMessageBox.warning(self, '警告', '请先选择要导出的文件（勾选复选框）')
            return

        mode = self.mode_combo.currentText()
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()

        data = []
        for row, filepath, old_name in selected:
            new_name = self.generate_new_name(old_name, mode, find_text, replace_text)
            data.append({
                '序号': len(data) + 1,
                '原文件名': old_name,
                '新文件名': new_name,
                '完整路径': filepath,
                '是否改变': '是' if new_name != old_name else '否',
                '目录': os.path.basename(os.path.dirname(filepath))
            })

        df = pd.DataFrame(data)

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='重命名映射', index=False)

            rule_df = pd.DataFrame({
                '项目': ['重命名模式', '查找内容', '替换内容', '选定文件数'],
                '值': [mode, find_text, replace_text, len(data)]
            })
            rule_df.to_excel(writer, sheet_name='重命名规则', index=False)

    def export_full_report(self, file_path):
        """导出完整报告"""
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # 1. 视频详细信息
            video_data = []
            for filepath, filename, rel_path, duration in self.video_data:
                size = self.get_file_size(filepath)
                video_data.append({
                    '序号': len(video_data) + 1,
                    '目录': rel_path,
                    '文件名': filename,
                    '完整路径': filepath,
                    '时长(秒)': self.format_duration_seconds(duration),
                    '时长(格式化)': self.format_duration(duration),
                    '文件大小(字节)': size,
                    '文件大小(格式化)': self.format_size(size) if size else '未知',
                    '扩展名': Path(filename).suffix.lower(),
                    '状态': '正常' if duration is not None else '无法读取'
                })

            df_video = pd.DataFrame(video_data)
            df_video.to_excel(writer, sheet_name='视频信息', index=False)

            # 2. 目录统计
            dir_data = []
            for dir_name, stats in sorted(self.dir_stats.items()):
                dir_data.append({
                    '目录': dir_name,
                    '视频数量': stats['count'],
                    '总时长(秒)': round(stats['duration'], 2),
                    '总时长(格式化)': self.format_duration(stats['duration'])
                })

            df_dir = pd.DataFrame(dir_data)
            df_dir.to_excel(writer, sheet_name='目录统计', index=False)

            # 3. 全局统计
            total_files = len(video_data)
            success_files = sum(1 for d in video_data if d['状态'] == '正常')
            total_seconds = sum(d['时长(秒)'] for d in video_data if d['时长(秒)'] is not None)

            stats_data = {
                '统计项': [
                    '扫描目录', '扫描时间', '总文件数', '成功读取', '无法读取',
                    '总时长(秒)', '总时长(格式化)', '目录数量'
                ],
                '数值': [
                    self.current_dir,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    total_files,
                    success_files,
                    total_files - success_files,
                    round(total_seconds, 2) if total_seconds else 0,
                    self.format_duration(total_seconds) if total_seconds else '00:00:00',
                    len(self.dir_stats)
                ]
            }

            df_stats = pd.DataFrame(stats_data)
            df_stats.to_excel(writer, sheet_name='全局统计', index=False)

    def closeEvent(self, event):
        """关闭窗口时清理资源"""
        # 取消正在进行的操作
        if hasattr(self, 'worker') and self.worker:
            self.worker.cancel()
        if hasattr(self, 'rename_worker') and self.rename_worker:
            self.rename_worker.cancel()

        if hasattr(self, 'worker_thread') and self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()
        if hasattr(self, 'rename_thread') and self.rename_thread and self.rename_thread.isRunning():
            self.rename_thread.quit()
            self.rename_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = VideoDurationApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()