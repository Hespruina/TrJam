#!/usr/bin/env python3
# project_achievement.py

import argparse
import sys
from pathlib import Path

# 默认忽略的目录（常见非代码目录）
DEFAULT_IGNORED_DIRS = {
    '__pycache__',
    '.git',
    '.venv',
    'venv',
    '.idea',
    '.vscode',
    'node_modules',
    'dist',
    'build',
    '.mypy_cache',
    '.pytest_cache',
    '.tox',
    '.eggs',
    '__MACOSX',
    'htmlcov',
    '.coverage',
    '.ruff_cache',
    '.mypy_cache',
    '.DS_Store',  # 虽是文件，但有时作为目录名出现（安全起见保留）
    'runtime',
}

SUPPORTED_EXTENSIONS = {'.py', '.txt', '.yml', '.yaml', '.xml', '.json', '.xaml'}

def count_lines(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def print_tree(current_path, prefix="", ignored_dirs=None, output_file=None):
    if ignored_dirs is None:
        ignored_dirs = set()
    path = Path(current_path)
    try:
        items = [
            item for item in path.iterdir()
            if item.name not in ignored_dirs
        ]
        items.sort(key=lambda x: (x.is_file(), x.name.lower()))
    except (PermissionError, OSError):
        line = f"{prefix}📁 {path.name} [无法访问]"
        print_to_target(line, output_file)
        return

    total = len(items)
    for i, item in enumerate(items):
        is_last = (i == total - 1)
        connector = "└── " if is_last else "├── "
        next_prefix = "    " if is_last else "│   "

        if item.is_dir():
            line = f"{prefix}{connector}📁 {item.name}"
            print_to_target(line, output_file)
            print_tree(item, prefix + next_prefix, ignored_dirs, output_file)
        else:
            if item.suffix.lower() in SUPPORTED_EXTENSIONS:
                lines = count_lines(item)
                line = f"{prefix}{connector}📄 {item.name} ({lines} 行)"
                print_to_target(line, output_file)

def print_to_target(line, output_file=None):
    if output_file is None:
        print(line)
    else:
        output_file.write(line + '\n')

def main():
    parser = argparse.ArgumentParser(
        description="扫描项目目录，生成带行数的树状结构报告。"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="输出文件路径（若未指定，则输出到控制台）"
    )
    parser.add_argument(
        "-e", "--exclude",
        action="append",
        default=[],
        help="要排除的目录名（可多次使用，例如：-e temp -e logs）"
    )

    args = parser.parse_args()

    # 合并默认忽略目录与用户指定目录
    ignored_dirs = set(DEFAULT_IGNORED_DIRS)
    ignored_dirs.update(args.exclude)

    # 准备输出目标
    output_file = None
    output_handle = None
    if args.output:
        output_handle = open(args.output, 'w', encoding='utf-8')
        output_file = output_handle

    try:
        header = "项目结构与文件行数统计"
        separator = "=" * 50
        print_to_target(header, output_file)
        print_to_target(separator, output_file)
        print_tree(".", ignored_dirs=ignored_dirs, output_file=output_file)
        print_to_target(separator, output_file)
    finally:
        if output_handle:
            output_handle.close()

if __name__ == "__main__":
    main()