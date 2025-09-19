"""
备份管理CLI命令

提供完整的备份管理功能：
- 备份状态显示
- 手动备份创建
- 备份恢复
- 备份清理和验证
"""

import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ...settings.discovery import discover_settings_files
from ...utils.backup import BackupConfig, BackupManager, BackupStatus, BackupType


# 简单的表格格式化函数
def format_table(headers, rows):
    """简单的表格格式化"""
    if not rows:
        return "未找到数据"

    # 计算每列的最大宽度
    col_widths = [len(str(header)) for header in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # 生成表格
    result = []

    # 标题行
    header_row = " | ".join(str(headers[i]).ljust(col_widths[i]) for i in range(len(headers)))
    result.append(header_row)
    result.append("-" * len(header_row))

    # 数据行
    for row in rows:
        data_row = " | ".join(str(row[i]).ljust(col_widths[i]) for i in range(len(row)))
        result.append(data_row)

    return "\n".join(result)

def format_json_output(data):
    """JSON格式化输出"""
    import json
    return json.dumps(data, indent=2, ensure_ascii=False)
from ..exceptions import CLIError


def create_backup_subparser(subparsers: argparse._SubParsersAction) -> None:
    """创建备份管理子命令解析器"""
    backup_parser = subparsers.add_parser(
        'backup',
        help='备份管理工具',
        description='管理设置文件的备份和恢复'
    )

    backup_subparsers = backup_parser.add_subparsers(
        dest='backup_action',
        help='备份操作'
    )

    # 状态命令
    status_parser = backup_subparsers.add_parser(
        'status',
        help='显示备份状态',
        description='显示当前备份系统状态和统计信息'
    )
    status_parser.add_argument(
        '--format',
        choices=['table', 'json'],
        default='table',
        help='输出格式'
    )

    # 列出备份命令
    list_parser = backup_subparsers.add_parser(
        'list',
        help='列出备份',
        description='列出指定文件或所有文件的备份'
    )
    list_parser.add_argument(
        'file_path',
        nargs='?',
        help='要列出备份的文件路径（可选）'
    )
    list_parser.add_argument(
        '--type',
        choices=[t.value for t in BackupType],
        help='按备份类型过滤'
    )
    list_parser.add_argument(
        '--status',
        choices=[s.value for s in BackupStatus],
        help='按备份状态过滤'
    )
    list_parser.add_argument(
        '--format',
        choices=['table', 'json'],
        default='table',
        help='输出格式'
    )

    # 创建备份命令
    create_parser = backup_subparsers.add_parser(
        'create',
        help='创建备份',
        description='手动创建文件备份'
    )
    create_parser.add_argument(
        'file_path',
        help='要备份的文件路径'
    )
    create_parser.add_argument(
        '--reason',
        default='手动备份',
        help='备份原因'
    )
    create_parser.add_argument(
        '--notes',
        default='',
        help='用户备注'
    )
    create_parser.add_argument(
        '--compress',
        action='store_true',
        help='启用压缩'
    )

    # 恢复备份命令
    restore_parser = backup_subparsers.add_parser(
        'restore',
        help='恢复备份',
        description='从备份恢复文件'
    )
    restore_parser.add_argument(
        'backup_id',
        nargs='?',
        help='备份ID（可选，如果不指定则恢复最新备份）'
    )
    restore_parser.add_argument(
        '--file',
        help='要恢复的原始文件路径（当不指定backup_id时必需）'
    )
    restore_parser.add_argument(
        '--target',
        help='恢复目标路径（可选，默认为原始位置）'
    )
    restore_parser.add_argument(
        '--verify',
        action='store_true',
        default=True,
        help='恢复前验证备份（默认启用）'
    )
    restore_parser.add_argument(
        '--no-verify',
        dest='verify',
        action='store_false',
        help='跳过备份验证'
    )

    # 验证备份命令
    verify_parser = backup_subparsers.add_parser(
        'verify',
        help='验证备份',
        description='验证备份文件的完整性'
    )
    verify_parser.add_argument(
        'backup_id',
        nargs='?',
        help='备份ID（可选，如果不指定则验证所有备份）'
    )
    verify_parser.add_argument(
        '--format',
        choices=['table', 'json'],
        default='table',
        help='输出格式'
    )

    # 清理备份命令
    cleanup_parser = backup_subparsers.add_parser(
        'cleanup',
        help='清理备份',
        description='清理过期或损坏的备份'
    )
    cleanup_parser.add_argument(
        '--days',
        type=int,
        help='清理多少天前的备份'
    )
    cleanup_parser.add_argument(
        '--corrupted',
        action='store_true',
        help='清理损坏的备份'
    )
    cleanup_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示将要清理的备份，不实际删除'
    )


def handle_backup_command(args: argparse.Namespace) -> int:
    """处理备份管理命令"""
    try:
        # 创建备份管理器
        config = BackupConfig()

        # 根据命令行参数调整配置
        if hasattr(args, 'compress') and args.compress:
            config.enable_compression = True

        manager = BackupManager(config)

        # 根据子命令执行相应操作
        if args.backup_action == 'status':
            return _handle_status_command(manager, args)
        elif args.backup_action == 'list':
            return _handle_list_command(manager, args)
        elif args.backup_action == 'create':
            return _handle_create_command(manager, args)
        elif args.backup_action == 'restore':
            return _handle_restore_command(manager, args)
        elif args.backup_action == 'verify':
            return _handle_verify_command(manager, args)
        elif args.backup_action == 'cleanup':
            return _handle_cleanup_command(manager, args)
        else:
            print("错误：未指定备份操作")
            return 1

    except Exception as e:
        raise CLIError(f"备份管理失败: {e}")


def _handle_status_command(manager: BackupManager, args: argparse.Namespace) -> int:
    """处理状态命令"""
    stats = manager.get_backup_statistics()

    if args.format == 'json':
        # 转换datetime为字符串以便JSON序列化
        if stats['oldest_backup']:
            stats['oldest_backup'] = stats['oldest_backup'].isoformat()
        if stats['newest_backup']:
            stats['newest_backup'] = stats['newest_backup'].isoformat()

        print(format_json_output(stats))
    else:
        print("=== 备份系统状态 ===")
        print(f"总备份数量: {stats['total_backups']}")
        print(f"唯一文件数: {stats['unique_files_count']}")
        print(f"总大小: {_format_size(stats['total_size'])}")

        if stats['oldest_backup']:
            print(f"最早备份: {stats['oldest_backup'].strftime('%Y-%m-%d %H:%M:%S')}")
        if stats['newest_backup']:
            print(f"最新备份: {stats['newest_backup'].strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n按类型统计:")
        for backup_type, count in stats['by_type'].items():
            print(f"  {backup_type}: {count}")

        print("\n按状态统计:")
        for status, count in stats['by_status'].items():
            print(f"  {status}: {count}")

    return 0


def _handle_list_command(manager: BackupManager, args: argparse.Namespace) -> int:
    """处理列表命令"""
    # 构建过滤条件
    source_path = Path(args.file_path) if args.file_path else None
    backup_type = BackupType(args.type) if args.type else None
    status = BackupStatus(args.status) if args.status else None

    # 获取备份列表
    backups = manager.list_backups(source_path, backup_type, status)

    if not backups:
        print("未找到匹配的备份")
        return 0

    if args.format == 'json':
        backup_data = []
        for backup in backups:
            data = backup.to_dict()
            backup_data.append(data)
        print(format_json_output(backup_data))
    else:
        # 表格格式输出
        headers = ['备份ID', '类型', '状态', '创建时间', '源文件', '大小']
        rows = []

        for backup in sorted(backups, key=lambda x: x.created_at, reverse=True):
            rows.append([
                backup.backup_id[:12] + '...',  # 截断ID显示
                backup.backup_type.value,
                backup.status.value,
                backup.created_at.strftime('%Y-%m-%d %H:%M'),
                Path(backup.source_file_path).name,  # 仅显示文件名
                _format_size(backup.backup_size)
            ])

        print(format_table(headers, rows))

    return 0


def _handle_create_command(manager: BackupManager, args: argparse.Namespace) -> int:
    """处理创建备份命令"""
    file_path = Path(args.file_path)

    if not file_path.exists():
        print(f"错误：文件不存在: {file_path}")
        return 1

    try:
        metadata = manager.create_backup(
            file_path,
            BackupType.MANUAL,
            args.reason,
            args.notes
        )

        print("备份创建成功:")
        print(f"  备份ID: {metadata.backup_id}")
        print(f"  备份文件: {metadata.backup_file_path}")
        print(f"  原始大小: {_format_size(metadata.original_size)}")
        print(f"  备份大小: {_format_size(metadata.backup_size)}")
        if metadata.compression.value != 'none':
            compression_ratio = (1 - metadata.backup_size / metadata.original_size) * 100
            print(f"  压缩率: {compression_ratio:.1f}%")

        return 0

    except Exception as e:
        print(f"错误：创建备份失败: {e}")
        return 1


def _handle_restore_command(manager: BackupManager, args: argparse.Namespace) -> int:
    """处理恢复备份命令"""
    try:
        if args.backup_id:
            # 恢复指定备份
            restored_path = manager.restore_backup(
                args.backup_id,
                args.target,
                args.verify
            )
        else:
            # 恢复最新备份
            if not args.file:
                print("错误：未指定备份ID时必须指定源文件路径")
                return 1

            file_path = Path(args.file)
            restored_path = manager.restore_latest_backup(file_path, args.target)

            if restored_path is None:
                print(f"错误：未找到文件的备份: {file_path}")
                return 1

        print(f"备份恢复成功: {restored_path}")
        return 0

    except Exception as e:
        print(f"错误：恢复备份失败: {e}")
        return 1


def _handle_verify_command(manager: BackupManager, args: argparse.Namespace) -> int:
    """处理验证备份命令"""
    try:
        if args.backup_id:
            # 验证指定备份
            backup = manager.get_backup_by_id(args.backup_id)
            if not backup:
                print(f"错误：备份不存在: {args.backup_id}")
                return 1

            is_valid = manager._verify_backup(backup)
            if args.format == 'json':
                result = {
                    'backup_id': args.backup_id,
                    'valid': is_valid,
                    'status': 'verified' if is_valid else 'corrupted'
                }
                print(format_json_output(result))
            else:
                status = "有效" if is_valid else "损坏"
                print(f"备份 {args.backup_id}: {status}")

            return 0 if is_valid else 1
        else:
            # 验证所有备份
            results = manager.verify_all_backups()

            if args.format == 'json':
                print(format_json_output(results))
            else:
                print("验证完成:")
                print(f"  总计检查: {results['total_checked']}")
                print(f"  验证成功: {results['verified']}")
                print(f"  发现损坏: {results['corrupted']}")

                if results['corrupted_backups']:
                    print("\n损坏的备份:")
                    for backup_id in results['corrupted_backups']:
                        print(f"  - {backup_id}")

            return 0 if results['corrupted'] == 0 else 1

    except Exception as e:
        print(f"错误：验证备份失败: {e}")
        return 1


def _handle_cleanup_command(manager: BackupManager, args: argparse.Namespace) -> int:
    """处理清理备份命令"""
    try:
        cleaned_count = 0

        if args.days:
            # 清理指定天数前的备份
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=args.days)

            all_backups = manager.list_backups()
            old_backups = [b for b in all_backups if b.created_at < cutoff_date]

            if args.dry_run:
                print(f"将清理 {len(old_backups)} 个过期备份:")
                for backup in old_backups:
                    print(f"  - {backup.backup_id} ({backup.created_at.strftime('%Y-%m-%d %H:%M')})")
            else:
                for backup in old_backups:
                    if manager._delete_backup(backup.backup_id):
                        cleaned_count += 1
                print(f"清理了 {cleaned_count} 个过期备份")

        if args.corrupted:
            # 清理损坏的备份
            results = manager.verify_all_backups()
            corrupted_backups = results['corrupted_backups']

            if args.dry_run:
                print(f"将清理 {len(corrupted_backups)} 个损坏备份:")
                for backup_id in corrupted_backups:
                    print(f"  - {backup_id}")
            else:
                for backup_id in corrupted_backups:
                    if manager._delete_backup(backup_id):
                        cleaned_count += 1
                print(f"清理了 {len(corrupted_backups)} 个损坏备份")

        if not args.days and not args.corrupted:
            # 使用默认清理策略
            cleaned_count = manager.cleanup_all_backups()
            if args.dry_run:
                print("使用默认清理策略（根据配置的保留期限）")
            else:
                print(f"清理了 {cleaned_count} 个过期备份")

        return 0

    except Exception as e:
        print(f"错误：清理备份失败: {e}")
        return 1


def _format_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"
