import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from moviepy import VideoFileClip


class ScanWorker(QObject):
    """扫描视频的工作线程"""
    progress = pyqtSignal(int, str, int, str)  # 当前索引, 文件名, 总数, 路径
    finished = pyqtSignal(list, float, dict)  # 视频信息列表, 总时长, 目录统计
    error = pyqtSignal(str)

    def __init__(self, directory, video_extensions):
        super().__init__()
        self.directory = directory
        self.video_extensions = video_extensions
        self.cancel = False

    def scan(self):
        """扫描视频文件（递归）"""
        try:
            video_files = []
            dir_stats = {}  # 统计每个目录的视频数量和时长

            # 递归遍历目录
            for root, dirs, files in os.walk(self.directory):
                # 可以在这里添加排除某些目录的逻辑
                # 例如：排除系统目录
                # dirs[:] = [d for d in dirs if not d.startswith('.')]

                dir_videos = []
                for file in files:
                    file_path = os.path.join(root, file)
                    ext = Path(file).suffix.lower()
                    if ext in self.video_extensions:
                        video_files.append(file_path)
                        dir_videos.append(file_path)

                # 统计每个目录的视频数量
                if dir_videos:
                    rel_path = os.path.relpath(root, self.directory)
                    if rel_path == '.':
                        rel_path = '根目录'
                    dir_stats[rel_path] = {
                        'count': len(dir_videos),
                        'files': dir_videos,
                        'duration': 0  # 稍后计算
                    }

            if not video_files:
                self.finished.emit([], 0, {})
                return

            video_info = []
            total_duration = 0

            for i, video_path in enumerate(video_files):
                filename = os.path.basename(video_path)
                rel_path = os.path.relpath(os.path.dirname(video_path), self.directory)
                if rel_path == '.':
                    rel_path = '根目录'

                self.progress.emit(i, filename, len(video_files), rel_path)

                # 获取视频时长
                try:
                    clip = VideoFileClip(video_path)
                    duration = clip.duration
                    clip.close()
                    if duration is not None:
                        total_duration += duration
                        video_info.append((video_path, filename, rel_path, duration))
                        # 更新目录统计
                        if rel_path in dir_stats:
                            dir_stats[rel_path]['duration'] += duration
                    else:
                        video_info.append((video_path, filename, rel_path, None))
                except Exception as e:
                    print(f'读取视频 {video_path} 失败: {e}')
                    video_info.append((video_path, filename, rel_path, None))

            self.finished.emit(video_info, total_duration, dir_stats)

        except Exception as e:
            self.error.emit(str(e))


class VideoDurationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # 先初始化变量
        self.current_dir = os.getcwd()
        self.video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv',
                                 '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
                                 '.3gp', '.ogv', '.ts', '.mts', '.m2ts'}
        self.worker_thread = None
        # 再初始化UI
        self.initUI()

    def initUI(self):
        self.setWindowTitle('视频时长查看器 - 递归扫描')
        self.setGeometry(100, 100, 1100, 800)

        # 设置窗口图标（如果有）
        # self.setWindowIcon(QIcon('icon.png'))

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)

        # 控制面板
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

        self.expand_btn = QPushButton('📊 展开/收起')
        self.expand_btn.clicked.connect(self.toggle_expand)
        self.expand_btn.setEnabled(False)
        control_panel.addWidget(self.expand_btn)

        layout.addLayout(control_panel)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['📁 目录', '📹 文件名', '⏱️ 时长', '📊 大小'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # 状态栏
        self.status_label = QLabel('✅ 就绪')
        self.status_label.setStyleSheet('font-size: 12px; padding: 5px;')
        layout.addWidget(self.status_label)

        # 统计信息框架
        stats_frame = QFrame()
        stats_frame.setStyleSheet('background-color: #e3f2fd; border-radius: 5px; padding: 10px;')
        stats_layout = QHBoxLayout(stats_frame)

        self.total_label = QLabel('⏱️ 总时长: 00:00:00')
        self.total_label.setStyleSheet('font-size: 14px; font-weight: bold; color: #2196F3;')
        stats_layout.addWidget(self.total_label)

        stats_layout.addStretch()

        self.file_count_label = QLabel('📄 文件数: 0')
        self.file_count_label.setStyleSheet('font-size: 14px; font-weight: bold; color: #4CAF50;')
        stats_layout.addWidget(self.file_count_label)

        stats_layout.addStretch()

        self.dir_count_label = QLabel('📁 目录数: 0')
        self.dir_count_label.setStyleSheet('font-size: 14px; font-weight: bold; color: #FF9800;')
        stats_layout.addWidget(self.dir_count_label)

        layout.addWidget(stats_frame)

        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
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
            QLabel {
                padding: 5px;
            }
            QProgressBar {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
        """)

        # 存储数据
        self.video_data = []
        self.expanded = True
        self.dir_stats = {}

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, '选择目录', self.current_dir)
        if directory:
            self.current_dir = directory
            self.dir_label.setText(f'📁 当前目录: {directory}')
            self.table.setRowCount(0)
            self.total_label.setText('⏱️ 总时长: 00:00:00')
            self.file_count_label.setText('📄 文件数: 0')
            self.dir_count_label.setText('📁 目录数: 0')
            self.status_label.setText('✅ 目录已更新，请点击扫描视频')
            self.expand_btn.setEnabled(False)

    def format_duration(self, seconds):
        if seconds is None:
            return '❌ 无法读取'
        if seconds < 0:
            return '❌ 无效时长'

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f'{hours:02d}:{minutes:02d}:{secs:02d}'
        return f'{minutes:02d}:{secs:02d}'

    def format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes is None:
            return '未知'
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f'{size_bytes:.2f} {unit}'
            size_bytes /= 1024.0
        return f'{size_bytes:.2f} PB'

    def get_file_size(self, filepath):
        """获取文件大小"""
        try:
            return os.path.getsize(filepath)
        except:
            return None

    def scan_videos(self):
        if not os.path.exists(self.current_dir):
            QMessageBox.warning(self, '错误', '目录不存在，请重新选择')
            return

        self.select_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.expand_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText('⏳ 正在扫描视频文件（递归搜索中...）')
        self.table.setRowCount(0)

        # 清空数据
        self.video_data = []
        self.dir_stats = {}

        # 创建并启动工作线程
        self.worker_thread = QThread()
        self.worker = ScanWorker(self.current_dir, self.video_extensions)
        self.worker.moveToThread(self.worker_thread)

        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.error.connect(self.on_scan_error)
        self.worker_thread.started.connect(self.worker.scan)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def update_progress(self, index, filename, total, rel_path):
        """更新进度"""
        self.status_label.setText(f'⏳ 正在处理: [{rel_path}] {filename} ({index + 1}/{total})')
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(index + 1)

    def on_scan_finished(self, video_info, total_duration, dir_stats):
        """扫描完成"""
        try:
            self.video_data = video_info
            self.dir_stats = dir_stats

            # 填充表格
            self.table.setRowCount(len(video_info))

            for i, (filepath, filename, rel_path, duration) in enumerate(video_info):
                # 目录
                dir_item = QTableWidgetItem(rel_path)
                dir_item.setFlags(dir_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 0, dir_item)

                # 文件名
                name_item = QTableWidgetItem(filename)
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 1, name_item)

                # 时长
                if duration is not None:
                    formatted_time = self.format_duration(duration)
                    time_item = QTableWidgetItem(formatted_time)
                    time_item.setForeground(QColor(46, 125, 50))  # 绿色
                else:
                    formatted_time = '❌ 无法读取'
                    time_item = QTableWidgetItem(formatted_time)
                    time_item.setForeground(QColor(198, 40, 40))  # 红色
                time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 2, time_item)

                # 文件大小
                size = self.get_file_size(filepath)
                size_str = self.format_size(size) if size else '未知'
                size_item = QTableWidgetItem(size_str)
                size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 3, size_item)

            # 显示统计信息
            total_formatted = self.format_duration(total_duration)
            self.total_label.setText(f'⏱️ 总时长: {total_formatted}')
            self.file_count_label.setText(f'📄 文件数: {len(video_info)}')
            self.dir_count_label.setText(f'📁 目录数: {len(dir_stats)}')

            # 显示目录统计
            self.show_directory_stats()

            # 自动调整列宽
            self.table.resizeColumnsToContents()
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

            self.status_label.setText(
                f'✅ 扫描完成，共找到 {len(video_info)} 个视频文件，分布在 {len(dir_stats)} 个目录中'
            )
            self.expand_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, '错误', f'显示结果时发生错误: {str(e)}')
        finally:
            self.finish_scan()

    def show_directory_stats(self):
        """在状态栏显示目录统计信息"""
        if not self.dir_stats:
            return

        # 构建目录统计信息
        stats_text = "\n📊 目录统计:\n"
        stats_text += "=" * 60 + "\n"

        # 按视频数量排序
        sorted_dirs = sorted(self.dir_stats.items(),
                             key=lambda x: x[1]['count'],
                             reverse=True)

        for dir_name, stats in sorted_dirs:
            duration_str = self.format_duration(stats['duration'])
            stats_text += f"  📁 {dir_name}: {stats['count']} 个视频, 总时长 {duration_str}\n"

        # 在状态栏显示（可选：可以放在一个弹出窗口中）
        # 这里我们只是更新状态栏，你也可以添加一个按钮来显示详细信息

    def toggle_expand(self):
        """展开/收起所有目录"""
        self.expanded = not self.expanded
        if self.expanded:
            self.expand_btn.setText('📊 收起')
            # 显示所有行
            for i in range(self.table.rowCount()):
                self.table.setRowHidden(i, False)
        else:
            self.expand_btn.setText('📊 展开')
            # 只显示根目录的文件
            for i in range(self.table.rowCount()):
                item = self.table.item(i, 0)
                if item and item.text() == '根目录':
                    self.table.setRowHidden(i, False)
                else:
                    self.table.setRowHidden(i, True)

    def on_scan_error(self, error_msg):
        """扫描出错"""
        QMessageBox.critical(self, '错误', f'扫描过程中发生错误: {error_msg}')
        self.status_label.setText(f'❌ 扫描出错: {error_msg}')
        self.finish_scan()

    def finish_scan(self):
        """完成扫描"""
        self.progress_bar.setVisible(False)
        self.select_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)
        if hasattr(self, 'worker_thread') and self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()

    def closeEvent(self, event):
        """关闭窗口时清理资源"""
        if hasattr(self, 'worker_thread') and self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = VideoDurationApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()