"""
cchooks工具模块

提供文件操作、JSON处理、格式化等核心工具功能。
"""

from .file_operations import (
    # 异常类
    FileOperationError,
    PermissionError,
    SecurityError,
    SettingsFileNotFoundError,
    # 安全和路径处理
    validate_path_security,
    get_home_directory,
    find_project_root,
    # 设置文件发现
    discover_settings_files,
    get_settings_file_path,
    # 权限和目录操作
    check_file_permissions,
    ensure_directory_exists,
    # 备份和恢复
    create_backup,
    restore_from_backup,
    # 文件读写操作
    read_json_file,
    write_json_file,
    read_text_file,
    write_text_file,
    safe_delete_file,
    # 文件信息
    get_file_info,
)

from .json_handler import (
    # JSON处理类
    SettingsJSONHandler,
    # 便捷函数
    create_empty_settings,
    load_settings_file,
    save_settings_file,
    validate_hook_configuration,
)

from .json_utils import (
    # JSON utility functions
    read_json_from_stdin,
    validate_required_fields,
    safe_get_str,
    safe_get_bool,
    safe_get_dict,
)

from .formatters import (
    # 格式化器类
    BaseFormatter,
    JSONFormatter,
    TableFormatter,
    YAMLFormatter,
    QuietFormatter,
    # 格式化器工厂函数
    create_formatter,
    # 便利格式化函数
    format_command_result,
    format_hook_list,
    format_validation_result,
    format_template_list,
)

__all__ = [
    # 异常类
    'FileOperationError',
    'PermissionError',
    'SecurityError',
    'SettingsFileNotFoundError',
    # 安全和路径处理
    'validate_path_security',
    'get_home_directory',
    'find_project_root',
    # 设置文件发现
    'discover_settings_files',
    'get_settings_file_path',
    # 权限和目录操作
    'check_file_permissions',
    'ensure_directory_exists',
    # 备份和恢复
    'create_backup',
    'restore_from_backup',
    # 文件读写操作
    'read_json_file',
    'write_json_file',
    'read_text_file',
    'write_text_file',
    'safe_delete_file',
    # 文件信息
    'get_file_info',
    # JSON处理类
    'SettingsJSONHandler',
    # JSON便捷函数
    'create_empty_settings',
    'load_settings_file',
    'save_settings_file',
    'validate_hook_configuration',
    # JSON utility functions
    'read_json_from_stdin',
    'validate_required_fields',
    'safe_get_str',
    'safe_get_bool',
    'safe_get_dict',
    # 格式化器类
    'BaseFormatter',
    'JSONFormatter',
    'TableFormatter',
    'YAMLFormatter',
    'QuietFormatter',
    # 格式化器工厂函数
    'create_formatter',
    # 便利格式化函数
    'format_command_result',
    'format_hook_list',
    'format_validation_result',
    'format_template_list',
]