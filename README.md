# 🎬 Video Duration Viewer

![Python Version](https://badgen.net/badge/python/3.8+/blue)
![PyQt5 Version](https://badgen.net/badge/PyQt5/5.15+/green)
![License](https://badgen.net/badge/license/MIT/blue)
![Platform](https://badgen.net/badge/platform/Windows/lightgrey)
![Status](https://badgen.net/badge/status/stable/brightgreen)

**一个功能强大的 Windows 桌面应用，用于批量查看视频时长、递归扫描目录、批量重命名视频文件，并支持导出详细报告到 Excel。**

功能特性 • 快速开始 • 使用指南 • 截图 • 贡献

## 📖 目录

- 功能特性
- 快速开始
- 使用指南
- 功能详解
- 截图
- 技术栈
- 常见问题
- 贡献
- 许可证



## ✨ 功能特性

### 📹 视频扫描与信息查看

- **递归扫描**：自动扫描当前目录及所有子目录下的视频文件
- **多格式支持**：支持 MP4、AVI、MKV、MOV、WMV、FLV、WEBM、M4V、MPG、MPEG、3GP、OGV、TS、MTS、M2TS 等主流视频格式
- **详细信息展示**：以表格形式清晰展示文件所在目录、文件名、时长和文件大小
- **实时进度**：扫描过程中实时显示进度，支持随时取消

### ⏱️ 时长统计

- **总时长计算**：自动统计所有视频文件的总时长
- **目录统计**：分别统计每个子目录的视频数量和总时长
- **多格式显示**：支持显示为 `HH:MM:SS` 或 `MM:SS` 格式
- **秒数精确统计**：同时显示总秒数，便于精确计算

### ✏️ 批量重命名

支持三种重命名模式，灵活应对各种场景：

#### 1. 去除前缀模式

- 批量删除文件名开头的广告文本或固定前缀
- 示例：`xxxx.com课程-7.常用命令` → `7.常用命令`

#### 2. 正则表达式替换模式

- 强大的正则表达式支持，灵活匹配和替换
- 支持捕获组（`\1`、`\2` 等）
- 示例：`^(.*?)-\\s*(.+)$` → `\\2`（提取第二部分）

#### 3. 自定义替换模式

- 简单的文本替换，适合固定字符的替换
- 示例：将 `old` 替换为 `new`

#### 重命名特性

- ✅ **预览功能**：执行前预览所有修改，确认无误再执行
- ✅ **选择性重命名**：通过复选框选择要重命名的文件
- ✅ **安全确认**：执行前二次确认，防止误操作
- ✅ **冲突检测**：自动检测目标文件名是否已存在
- ✅ **实时进度**：显示重命名进度，支持随时取消

### 📊 导出 Excel 报告

支持四种导出类型，满足不同需求：

#### 1. 视频详细信息

- 文件名、目录、完整路径
- 时长（秒和格式化两种显示）
- 文件大小（字节和格式化）
- 文件扩展名和读取状态

#### 2. 目录统计信息

- 每个目录的视频数量
- 每个目录的总时长
- 目录下的文件列表

#### 3. 重命名映射表

- 原文件名 → 新文件名对照表
- 包含重命名规则信息
- 显示哪些文件会被修改

#### 4. 完整报告

- 包含以上所有信息
- 全局统计信息（扫描时间、总文件数、成功率等）

### 🎯 其他特色

- **美观的界面**：基于 PyQt5 构建，界面简洁现代
- **多线程处理**：扫描和重命名操作不卡顿界面
- **取消功能**：支持随时取消扫描或重命名操作
- **状态提示**：实时显示当前操作状态和进度
- **文件大小显示**：自动格式化为 B、KB、MB、GB 等单位



## 🚀 快速开始

### 系统要求

- Windows 7/10/11（64位）
- Python 3.8 或更高版本

### 源码运行

```bash
# 克隆仓库
git clone https://github.com/ryanxin7/video-duration-viewer.git
cd video-duration-viewer

# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行程序
python pu.py
```



### 打包为 EXE（无需安装 Python）

```bash
# 安装打包工具
pip install pyinstaller

# 执行打包脚本
build.bat

# 或手动打包
pyinstaller VideoDurationViewer.spec
```



生成的 `VideoDurationViewer.exe` 位于 `dist` 目录，可直接在 Windows 上运行。

### 依赖库

```txt
PyQt5>=5.15.0      # GUI 框架
moviepy>=2.0.0     # 视频处理
pandas>=1.5.0      # 数据处理
openpyxl>=3.1.0    # Excel 导出
```



## 📖 使用指南

### 基本操作流程

1. **选择目录**
   - 点击「📂 选择目录」按钮
   - 选择包含视频文件的文件夹
2. **扫描视频**
   - 点击「🔍 扫描视频」按钮
   - 程序会自动递归扫描所有子目录
   - 实时显示扫描进度
3. **查看信息**
   - 表格显示所有视频文件
   - 包含目录、文件名、时长、大小等信息
   - 底部显示总时长和统计信息
4. **批量重命名**
   - 勾选需要重命名的文件
   - 选择重命名模式（去除前缀/正则替换/自定义替换）
   - 输入查找内容和替换内容
   - 点击「👁️ 预览」查看效果
   - 确认后点击「✏️ 执行重命名」
5. **导出报告**
   - 点击「📊 导出Excel」按钮
   - 选择导出类型（四种可选）
   - 选择保存位置
   - 自动生成 Excel 文件

------

## 🔧 功能详解

### 重命名模式示例

#### 去除前缀模式

```
查找: [广告前缀]
替换为: (留空)

示例:
原文件名: xxxx.com课程-7.常用命令
新文件名: 7.常用命令
```



#### 正则表达式替换模式

```
查找: ^(.*?)-\\s*(.+)$
替换为: \\2

示例:
原文件名: 教程-第7章-常用命令
新文件名: 第7章-常用命令
```



#### 自定义替换模式

```
查找: 旧文本
替换为: 新文本

示例:
原文件名: 2023_01_视频.mp4
新文件名: 2024_01_视频.mp4
```



### 导出报告说明

| 导出类型     | 内容                  | 适用场景           |
| :----------- | :-------------------- | :----------------- |
| 视频详细信息 | 所有视频的完整信息    | 数据分析、归档     |
| 目录统计信息 | 每个目录的视频统计    | 目录管理、空间分析 |
| 重命名映射表 | 原文件名→新文件名对照 | 重命名记录、审计   |
| 完整报告     | 包含以上所有内容      | 全面数据导出       |

------

## 📸 截图

### 主界面

https://screenshots/main.png

### 扫描视频

https://screenshots/scan.png

### 批量重命名

https://screenshots/rename.png

### 导出 Excel

https://screenshots/export.png

> **注意**：截图需要实际运行程序后补充。

------

## 🛠️ 技术栈

| 技术            | 用途           |
| :-------------- | :------------- |
| **PyQt5**       | GUI 界面框架   |
| **moviepy**     | 读取视频时长   |
| **pandas**      | 数据处理和分析 |
| **openpyxl**    | Excel 文件读写 |
| **PyInstaller** | 打包为 EXE     |
| **Python 3.8+** | 开发语言       |

### 架构设计

text

```
┌─────────────────────────────────────────────┐
│           Video Duration Viewer             │
├─────────────────────────────────────────────┤
│  ┌──────────────┐  ┌─────────────────────┐ │
│  │  Main Window  │  │  Scan Worker        │ │
│  │  (PyQt5 GUI)  │  │  (QThread)          │ │
│  └──────────────┘  └─────────────────────┘ │
│  ┌──────────────┐  ┌─────────────────────┐ │
│  │  Data Table  │  │  Rename Worker      │ │
│  │  (QTable)    │  │  (QThread)          │ │
│  └──────────────┘  └─────────────────────┘ │
│  ┌──────────────┐  ┌─────────────────────┐ │
│  │  Excel Export│  │  Video Duration     │ │
│  │  (pandas)    │  │  (moviepy)          │ │
│  └──────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────┘
```



------

## ❓ 常见问题

### Q1: 程序运行时提示缺少 FFmpeg？

**A**: 安装 moviepy 时需要 FFmpeg 支持：

bash

```
pip install ffmpeg-python
```



或从 [FFmpeg 官网](https://ffmpeg.org/download.html) 下载并添加到系统 PATH。

### Q2: 打包后的 EXE 文件很大怎么办？

**A**: 这是正常现象，因为包含了完整的 Python 环境和所有依赖库。可使用 UPX 压缩优化：

bash

```
# 下载 UPX 并放到指定目录
pyinstaller --onefile --upx-dir="upx_path" pu.py
```



### Q3: 扫描时程序卡住了？

**A**: 程序使用多线程处理，不会卡顿。如果大文件读取较慢，可点击「取消扫描」按钮停止。

### Q4: 导出的 Excel 文件无法打开？

**A**: 请确保已安装 openpyxl：

bash

```
pip install openpyxl
```



### Q5: 重命名后文件不见了？

**A**: 重命名不会删除文件，只是修改文件名。检查是否重命名为隐藏文件格式（如以 `.` 开头）。

### Q6: 支持哪些视频格式？

**A**: 支持 MP4、AVI、MKV、MOV、WMV、FLV、WEBM、M4V、MPG、MPEG、3GP、OGV、TS、MTS、M2TS 等格式。

------

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

### 开发建议

- 遵循 PEP 8 代码规范
- 添加适当的注释和文档
- 测试新功能是否影响现有功能
- 更新 README 和文档

------

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](https://license/) 文件

text

```
MIT License

Copyright (c) 2024 Video Duration Viewer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
...
```



------

## 📞 联系方式

- **项目地址**: [GitHub Repository](https://github.com/ryanxin7/video-duration-viewer)
- **问题反馈**: [Issues](https://github.com/ryanxin7/video-duration-viewer/issues)
- **作者**: [Your Name](https://github.com/ryanxin7)

------

## ⭐ 支持项目

如果这个项目对你有帮助，请给个 Star ⭐ 支持一下！

https://img.shields.io/github/stars/ryanxin7/video-duration-viewer?style=social

------

## 📋 更新日志

### v0.1.0 (2026-07-16)

- 🎉 首次发布
- ✨ 支持递归扫描视频文件