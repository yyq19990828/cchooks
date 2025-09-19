"""
跨平台文件权限处理模块

提供统一的文件和目录权限管理接口，支持Windows、macOS、Linux三大平台。
专门为Claude Code CLI工具设计，确保所有文件操作在不同平台上都能可靠工作。

主要功能：
- 跨平台权限检查和设置
- 脚本执行权限管理
- 目录创建权限处理
- 权限错误详细诊断
- 安全防护和路径验证
- 权限修复建议和替代方案
"""

import os
import platform
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .file_operations import FileOperationError, SecurityError, validate_path_security


class PermissionLevel(Enum):
    """权限级别枚举"""
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    READ_WRITE = auto()
    FULL = auto()


class PlatformType(Enum):
    """平台类型枚举"""
    WINDOWS = "windows"
    MACOS = "darwin"
    LINUX = "linux"
    UNKNOWN = "unknown"


@dataclass
class PermissionInfo:
    """权限信息数据类"""
    path: Path
    exists: bool
    is_readable: bool
    is_writable: bool
    is_executable: bool
    owner_readable: bool
    owner_writable: bool
    owner_executable: bool
    group_readable: bool = False
    group_writable: bool = False
    group_executable: bool = False
    other_readable: bool = False
    other_writable: bool = False
    other_executable: bool = False
    platform_specific: Dict[str, Any] = None

    def __post_init__(self):
        if self.platform_specific is None:
            self.platform_specific = {}


@dataclass
class PermissionError:
    """权限错误信息"""
    error_code: str
    message: str
    suggested_fix: str
    alternative_solutions: List[str]
    is_recoverable: bool
    requires_admin: bool = False


class PermissionDiagnostic:
    """权限诊断和修复建议类"""

    @staticmethod
    def diagnose_permission_error(path: Path, required_level: PermissionLevel,
                                error: Exception) -> PermissionError:
        """诊断权限错误并提供修复建议"""
        platform_name = get_current_platform()

        if isinstance(error, PermissionError):
            return PermissionDiagnostic._diagnose_permission_denied(path, required_level, platform_name)
        elif isinstance(error, FileNotFoundError):
            return PermissionDiagnostic._diagnose_file_not_found(path, platform_name)
        elif isinstance(error, OSError):
            return PermissionDiagnostic._diagnose_os_error(path, required_level, error, platform_name)
        else:
            return PermissionDiagnostic._diagnose_unknown_error(path, required_level, error, platform_name)

    @staticmethod
    def _diagnose_permission_denied(path: Path, required_level: PermissionLevel,
                                  platform: PlatformType) -> PermissionError:
        """诊断权限拒绝错误"""
        if platform == PlatformType.WINDOWS:
            return PermissionError(
                error_code="WINDOWS_ACCESS_DENIED",
                message=f"Windows拒绝访问 {path}。可能需要管理员权限或文件被其他程序锁定。",
                suggested_fix="右键以管理员身份运行程序，或检查文件是否被其他程序占用。",
                alternative_solutions=[
                    "检查文件是否被防病毒软件保护",
                    "确认文件不在受保护的系统目录中",
                    "尝试关闭可能占用文件的其他程序"
                ],
                is_recoverable=True,
                requires_admin=True
            )
        else:
            return PermissionError(
                error_code="UNIX_PERMISSION_DENIED",
                message=f"权限不足无法访问 {path}。",
                suggested_fix="运行 chmod 修改权限或使用 sudo 提升权限。",
                alternative_solutions=[
                    f"sudo chmod u+{'rwx' if required_level == PermissionLevel.FULL else 'rw'} {path}",
                    f"sudo chown $USER {path}",
                    "检查父目录权限是否正确"
                ],
                is_recoverable=True,
                requires_admin=False
            )

    @staticmethod
    def _diagnose_file_not_found(path: Path, platform: PlatformType) -> PermissionError:
        """诊断文件不存在错误"""
        parent = path.parent
        return PermissionError(
            error_code="FILE_NOT_FOUND",
            message=f"文件或目录 {path} 不存在。",
            suggested_fix=f"确保路径正确，或创建缺失的父目录 {parent}。",
            alternative_solutions=[
                f"mkdir -p {parent}" if platform != PlatformType.WINDOWS else f"md {parent}",
                "检查路径拼写是否正确",
                "确认文件是否已被移动或删除"
            ],
            is_recoverable=True,
            requires_admin=False
        )

    @staticmethod
    def _diagnose_os_error(path: Path, required_level: PermissionLevel,
                          error: OSError, platform: PlatformType) -> PermissionError:
        """诊断操作系统错误"""
        error_code = getattr(error, 'errno', 0)

        if error_code == 13:  # Permission denied
            return PermissionDiagnostic._diagnose_permission_denied(path, required_level, platform)
        elif error_code == 2:  # No such file or directory
            return PermissionDiagnostic._diagnose_file_not_found(path, platform)
        elif error_code == 28:  # No space left on device
            return PermissionError(
                error_code="NO_SPACE_LEFT",
                message="磁盘空间不足。",
                suggested_fix="清理磁盘空间或选择其他存储位置。",
                alternative_solutions=[
                    "删除不需要的文件释放空间",
                    "使用其他驱动器或分区",
                    "检查是否有大文件可以移动"
                ],
                is_recoverable=True,
                requires_admin=False
            )
        else:
            return PermissionError(
                error_code=f"OS_ERROR_{error_code}",
                message=f"操作系统错误: {error}",
                suggested_fix="检查系统状态和文件系统完整性。",
                alternative_solutions=[
                    "重新启动程序",
                    "检查磁盘错误",
                    "联系系统管理员"
                ],
                is_recoverable=False,
                requires_admin=False
            )

    @staticmethod
    def _diagnose_unknown_error(path: Path, required_level: PermissionLevel,
                               error: Exception, platform: PlatformType) -> PermissionError:
        """诊断未知错误"""
        return PermissionError(
            error_code="UNKNOWN_ERROR",
            message=f"未知错误: {error}",
            suggested_fix="重试操作或检查系统状态。",
            alternative_solutions=[
                "重新启动程序",
                "检查文件路径是否正确",
                "查看系统日志获取更多信息"
            ],
            is_recoverable=False,
            requires_admin=False
        )


def get_current_platform() -> PlatformType:
    """获取当前运行平台"""
    system = platform.system().lower()
    if system == "windows":
        return PlatformType.WINDOWS
    elif system == "darwin":
        return PlatformType.MACOS
    elif system == "linux":
        return PlatformType.LINUX
    else:
        return PlatformType.UNKNOWN


def get_permission_info(file_path: Union[str, Path]) -> PermissionInfo:
    """获取文件或目录的详细权限信息"""
    path = validate_path_security(file_path)
    platform_type = get_current_platform()

    # 基础信息
    exists = path.exists()
    info = PermissionInfo(
        path=path,
        exists=exists,
        is_readable=False,
        is_writable=False,
        is_executable=False,
        owner_readable=False,
        owner_writable=False,
        owner_executable=False
    )

    if not exists:
        return info

    try:
        # 使用os.access检查基本权限
        info.is_readable = os.access(path, os.R_OK)
        info.is_writable = os.access(path, os.W_OK)
        info.is_executable = os.access(path, os.X_OK)

        # 获取详细权限信息
        stat_info = path.stat()
        mode = stat_info.st_mode

        # 所有者权限
        info.owner_readable = bool(mode & stat.S_IRUSR)
        info.owner_writable = bool(mode & stat.S_IWUSR)
        info.owner_executable = bool(mode & stat.S_IXUSR)

        # Unix/Linux/macOS的组和其他用户权限
        if platform_type != PlatformType.WINDOWS:
            info.group_readable = bool(mode & stat.S_IRGRP)
            info.group_writable = bool(mode & stat.S_IWGRP)
            info.group_executable = bool(mode & stat.S_IXGRP)
            info.other_readable = bool(mode & stat.S_IROTH)
            info.other_writable = bool(mode & stat.S_IWOTH)
            info.other_executable = bool(mode & stat.S_IXOTH)

        # 平台特定信息
        if platform_type == PlatformType.WINDOWS:
            info.platform_specific = _get_windows_permission_info(path)
        elif platform_type == PlatformType.MACOS:
            info.platform_specific = _get_macos_permission_info(path)
        elif platform_type == PlatformType.LINUX:
            info.platform_specific = _get_linux_permission_info(path)

    except (OSError, ValueError) as e:
        # 如果获取权限信息失败，记录错误但不抛出异常
        info.platform_specific = {"error": str(e)}

    return info


def _get_windows_permission_info(path: Path) -> Dict[str, Any]:
    """获取Windows特定的权限信息（增强版）"""
    info = {
        "platform": "windows",
        "is_system_file": False,
        "is_hidden": False,
        "is_readonly": False,
        "is_archive": False,
        "is_compressed": False,
        "is_encrypted": False,
        "effective_permissions": {
            "can_read": False,
            "can_write": False,
            "can_execute": False,
            "can_delete": False
        }
    }

    try:
        # 检查文件属性
        import stat
        stat_info = path.stat()

        # Windows文件属性（增强检查）
        if hasattr(stat_info, 'st_file_attributes'):
            attrs = stat_info.st_file_attributes
            info["is_hidden"] = bool(attrs & 2)  # FILE_ATTRIBUTE_HIDDEN
            info["is_readonly"] = bool(attrs & 1)  # FILE_ATTRIBUTE_READONLY
            info["is_system_file"] = bool(attrs & 4)  # FILE_ATTRIBUTE_SYSTEM
            info["is_archive"] = bool(attrs & 32)  # FILE_ATTRIBUTE_ARCHIVE
            info["is_compressed"] = bool(attrs & 2048)  # FILE_ATTRIBUTE_COMPRESSED
            info["is_encrypted"] = bool(attrs & 16384)  # FILE_ATTRIBUTE_ENCRYPTED

        # 基础权限检查（使用os.access）
        info["effective_permissions"]["can_read"] = os.access(path, os.R_OK)
        info["effective_permissions"]["can_write"] = os.access(path, os.W_OK)
        info["effective_permissions"]["can_execute"] = os.access(path, os.X_OK)

        # 尝试检查删除权限（尝试重命名到自身来测试）
        if path.exists():
            try:
                temp_name = path.with_suffix('.temp_check_delete')
                if not temp_name.exists():
                    path.rename(temp_name)
                    temp_name.rename(path)
                    info["effective_permissions"]["can_delete"] = True
            except (OSError, PermissionError):
                info["effective_permissions"]["can_delete"] = False

        # 检查是否在受保护的位置
        protected_paths = [
            "C:\\Windows",
            "C:\\Program Files",
            "C:\\Program Files (x86)",
            "C:\\ProgramData"
        ]
        path_str = str(path).upper()
        info["is_in_protected_location"] = any(path_str.startswith(p.upper()) for p in protected_paths)

        # 尝试获取详细ACL信息（增强版）
        try:
            # 这需要pywin32，如果不可用就跳过
            import win32con
            import win32file
            import win32security

            # 获取安全描述符
            sd = win32security.GetFileSecurity(str(path),
                                             win32security.DACL_SECURITY_INFORMATION |
                                             win32security.OWNER_SECURITY_INFORMATION)
            dacl = sd.GetSecurityDescriptorDacl()
            owner_sid = sd.GetSecurityDescriptorOwner()

            if dacl:
                info["has_acl"] = True
                info["ace_count"] = dacl.GetAceCount()

                # 分析ACE条目
                aces = []
                for i in range(dacl.GetAceCount()):
                    ace = dacl.GetAce(i)
                    ace_type, ace_flags = ace[0], ace[1]
                    permissions = ace[2]
                    sid = ace[3]

                    try:
                        account, domain, type = win32security.LookupAccountSid(None, sid)
                        ace_info = {
                            "type": ace_type,
                            "account": f"{domain}\\{account}" if domain else account,
                            "permissions": permissions,
                            "allow": ace_type == win32security.ACCESS_ALLOWED_ACE_TYPE
                        }
                        aces.append(ace_info)
                    except Exception:
                        # 如果无法解析SID，跳过
                        pass

                info["aces"] = aces[:10]  # 限制输出数量
            else:
                info["has_acl"] = False

            # 获取所有者信息
            if owner_sid:
                try:
                    owner_account, owner_domain, owner_type = win32security.LookupAccountSid(None, owner_sid)
                    info["owner"] = f"{owner_domain}\\{owner_account}" if owner_domain else owner_account
                except Exception:
                    info["owner"] = "Unknown"

        except ImportError:
            info["acl_info"] = "pywin32 not available - limited permission analysis"
        except Exception as e:
            info["acl_error"] = str(e)

        # 检查文件是否被锁定
        if path.is_file():
            try:
                with open(path, 'r+b'):
                    info["is_locked"] = False
            except (OSError, PermissionError):
                info["is_locked"] = True
        else:
            info["is_locked"] = False

        # 检查文件关联和执行能力
        if path.is_file():
            suffix = path.suffix.lower()
            info["file_association"] = {
                "extension": suffix,
                "is_executable": suffix in ['.exe', '.com', '.bat', '.cmd', '.msi', '.scr'],
                "is_script": suffix in ['.py', '.pyw', '.ps1', '.vbs', '.js'],
                "requires_interpreter": suffix in ['.py', '.pyw', '.ps1', '.vbs', '.js']
            }

    except Exception as e:
        info["error"] = str(e)

    return info


def _get_macos_permission_info(path: Path) -> Dict[str, Any]:
    """获取macOS特定的权限信息（增强版）"""
    info = {
        "platform": "macos",
        "has_extended_attributes": False,
        "is_quarantined": False,
        "has_resource_fork": False,
        "has_code_signature": False,
        "is_notarized": False,
        "requires_full_disk_access": False,
        "sip_protected": False,
        "gatekeeper_status": "unknown"
    }

    try:
        # 检查扩展属性（增强版）
        try:
            import xattr
            attrs = xattr.listxattr(str(path))
            info["has_extended_attributes"] = len(attrs) > 0
            info["extended_attributes"] = [attr.decode('utf-8', errors='ignore') for attr in attrs]

            # 检查隔离属性（Gatekeeper）
            if b'com.apple.quarantine' in attrs:
                info["is_quarantined"] = True
                try:
                    quarantine_data = xattr.getxattr(str(path), 'com.apple.quarantine')
                    info["quarantine_data"] = quarantine_data.decode('utf-8', errors='ignore')
                except Exception:
                    pass

            # 检查其他重要的扩展属性
            important_attrs = {
                'com.apple.metadata:_kMDItemUserTags': 'user_tags',
                'com.apple.FinderInfo': 'finder_info',
                'com.apple.TextEncoding': 'text_encoding'
            }

            for attr_name, info_key in important_attrs.items():
                if attr_name.encode() in attrs:
                    info[f"has_{info_key}"] = True

        except ImportError:
            info["xattr_info"] = "xattr module not available - limited extended attribute support"
        except Exception as e:
            info["xattr_error"] = str(e)

        # 检查资源分支
        resource_path = path.parent / f"{path.name}/..namedfork/rsrc"
        info["has_resource_fork"] = resource_path.exists()

        # 检查是否在受保护的系统目录中（SIP - System Integrity Protection）
        sip_protected_paths = [
            "/System", "/usr", "/bin", "/sbin", "/Library",
            "/Applications/Utilities", "/private/etc", "/private/var"
        ]
        path_str = str(path)
        info["sip_protected"] = any(path_str.startswith(p) for p in sip_protected_paths)

        # 检查是否在需要Full Disk Access的位置
        protected_locations = [
            "/private/var/db", "/private/var/folders", "/Library/Application Support",
            "/System/Library", "/usr/libexec", "/private/etc"
        ]
        info["requires_full_disk_access"] = any(path_str.startswith(p) for p in protected_locations)

        # 如果是可执行文件，检查代码签名和公证状态
        if path.is_file() and os.access(path, os.X_OK):
            # 检查代码签名
            try:
                result = subprocess.run(['codesign', '-v', str(path)],
                                      capture_output=True, text=True, timeout=10)
                info["has_code_signature"] = result.returncode == 0
                if result.returncode != 0:
                    info["code_signature_error"] = result.stderr.strip()
            except (subprocess.SubprocessError, FileNotFoundError):
                info["codesign_info"] = "codesign command not available"

            # 检查公证状态
            try:
                result = subprocess.run(['spctl', '-a', '-v', str(path)],
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    info["gatekeeper_status"] = "accepted"
                    info["is_notarized"] = "notarized" in result.stderr.lower()
                else:
                    info["gatekeeper_status"] = "rejected"
                    info["gatekeeper_reason"] = result.stderr.strip()
            except (subprocess.SubprocessError, FileNotFoundError):
                info["spctl_info"] = "spctl command not available"

        # 检查ACL信息
        try:
            result = subprocess.run(['ls', '-le', str(path)],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    if 'group:' in line or 'user:' in line:
                        info["has_acl"] = True
                        break
                else:
                    info["has_acl"] = False
        except (subprocess.SubprocessError, FileNotFoundError):
            info["acl_check_info"] = "ls command not available"

        # 检查是否在iCloud同步目录中
        try:
            import getpass
            icloud_paths = [
                "/Users/*/Library/Mobile Documents",
                "/Users/*/Documents",
                "/Users/*/Desktop"
            ]
            for icloud_pattern in icloud_paths:
                if any(path_str.startswith(icloud_pattern.replace('*', part))
                       for part in [os.environ.get('USER', ''), getpass.getuser()]):
                    info["in_icloud_sync"] = True
                    break
            else:
                info["in_icloud_sync"] = False
        except ImportError:
            info["in_icloud_sync"] = False

        # 检查Spotlight索引状态
        try:
            result = subprocess.run(['mdls', '-name', 'kMDItemFSName', str(path)],
                                  capture_output=True, text=True, timeout=5)
            info["spotlight_indexed"] = result.returncode == 0 and "null" not in result.stdout
        except (subprocess.SubprocessError, FileNotFoundError):
            info["spotlight_info"] = "mdls command not available"

    except Exception as e:
        info["error"] = str(e)

    return info


def _get_linux_permission_info(path: Path) -> Dict[str, Any]:
    """获取Linux特定的权限信息（增强版）"""
    info = {
        "platform": "linux",
        "has_acl": False,
        "has_selinux_context": False,
        "has_capabilities": False,
        "has_apparmor_profile": False,
        "has_immutable_flag": False,
        "filesystem_type": "unknown",
        "mount_options": [],
        "security_context": {}
    }

    try:
        # 检查文件系统类型和挂载选项
        try:
            result = subprocess.run(['stat', '-f', '-c', '%T', str(path)],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info["filesystem_type"] = result.stdout.strip()

            # 获取挂载选项
            result = subprocess.run(['findmnt', '-n', '-o', 'OPTIONS', str(path)],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info["mount_options"] = result.stdout.strip().split(',')
        except (subprocess.SubprocessError, FileNotFoundError):
            info["filesystem_info"] = "stat/findmnt commands not available"

        # 检查扩展ACL
        try:
            result = subprocess.run(['getfacl', str(path)],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                acl_output = result.stdout.strip()
                info["has_acl"] = True
                info["acl_info"] = acl_output

                # 解析ACL信息
                acl_entries = []
                for line in acl_output.split('\n'):
                    if line.startswith('user:') or line.startswith('group:') or line.startswith('other:'):
                        acl_entries.append(line.strip())
                info["acl_entries"] = acl_entries
        except (subprocess.SubprocessError, FileNotFoundError):
            info["acl_info"] = "getfacl not available"

        # 检查SELinux上下文（增强版）
        try:
            result = subprocess.run(['ls', '-Z', str(path)],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout.strip()
                if '?' not in output and output:
                    info["has_selinux_context"] = True
                    parts = output.split()
                    if len(parts) >= 1:
                        selinux_context = parts[0]
                        info["selinux_context"] = selinux_context

                        # 解析SELinux上下文
                        context_parts = selinux_context.split(':')
                        if len(context_parts) >= 3:
                            info["security_context"] = {
                                "user": context_parts[0],
                                "role": context_parts[1],
                                "type": context_parts[2],
                                "level": context_parts[3] if len(context_parts) > 3 else ""
                            }

            # 检查SELinux策略状态
            result = subprocess.run(['getenforce'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info["selinux_mode"] = result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            info["selinux_info"] = "SELinux commands not available"

        # 检查AppArmor配置
        try:
            if path.is_file():
                result = subprocess.run(['aa-status'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and str(path) in result.stdout:
                    info["has_apparmor_profile"] = True
                    info["apparmor_status"] = "profile exists"
        except (subprocess.SubprocessError, FileNotFoundError):
            info["apparmor_info"] = "AppArmor not available"

        # 检查文件能力（增强版）
        if path.is_file():
            try:
                result = subprocess.run(['getcap', str(path)],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    info["has_capabilities"] = True
                    cap_output = result.stdout.strip()
                    info["capabilities"] = cap_output

                    # 解析能力
                    if '=' in cap_output:
                        cap_part = cap_output.split('=')[1].strip()
                        capabilities_list = [cap.strip() for cap in cap_part.split(',') if cap.strip()]
                        info["capabilities_list"] = capabilities_list
            except (subprocess.SubprocessError, FileNotFoundError):
                info["capabilities_info"] = "getcap not available"

        # 检查文件属性（immutable等）
        try:
            result = subprocess.run(['lsattr', str(path)],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                attrs_output = result.stdout.strip()
                if attrs_output:
                    attrs = attrs_output.split()[0]
                    info["extended_attributes"] = attrs
                    info["has_immutable_flag"] = 'i' in attrs
                    info["has_append_only"] = 'a' in attrs
                    info["has_compress"] = 'c' in attrs
                    info["has_secure_delete"] = 's' in attrs
        except (subprocess.SubprocessError, FileNotFoundError):
            info["lsattr_info"] = "lsattr not available"

        # 检查命名空间信息
        try:
            if path.is_file():
                result = subprocess.run(['readlink', '/proc/self/ns/mnt'],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    info["mount_namespace"] = result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            info["namespace_info"] = "namespace commands not available"

        # 检查是否在容器中
        try:
            if os.path.exists('/.dockerenv'):
                info["in_container"] = "docker"
            elif os.path.exists('/run/.containerenv'):
                info["in_container"] = "podman"
            elif os.environ.get('container'):
                info["in_container"] = os.environ['container']
            else:
                info["in_container"] = False
        except Exception:
            info["in_container"] = "unknown"

        # 检查cgroup信息
        try:
            with open('/proc/self/cgroup') as f:
                cgroup_info = f.read().strip()
                info["has_cgroup_limits"] = 'memory' in cgroup_info or 'cpu' in cgroup_info
        except OSError:
            info["cgroup_info"] = "cgroup information not available"

    except Exception as e:
        info["error"] = str(e)

    return info


def check_permission(file_path: Union[str, Path],
                    permission_level: PermissionLevel) -> Tuple[bool, Optional[PermissionError]]:
    """
    检查文件或目录的权限

    Args:
        file_path: 文件或目录路径
        permission_level: 所需的权限级别

    Returns:
        (是否有权限, 权限错误信息)
    """
    try:
        path = validate_path_security(file_path)
        info = get_permission_info(path)

        if not info.exists:
            # 文件不存在，检查父目录的写权限
            parent_info = get_permission_info(path.parent)
            if not parent_info.exists:
                error = PermissionDiagnostic.diagnose_permission_error(
                    path.parent, PermissionLevel.WRITE, FileNotFoundError()
                )
                return False, error

            if not parent_info.is_writable:
                error = PermissionDiagnostic.diagnose_permission_error(
                    path.parent, PermissionLevel.WRITE, PermissionError()
                )
                return False, error

            return True, None

        # 检查所需权限
        has_permission = True

        if permission_level in [PermissionLevel.READ, PermissionLevel.READ_WRITE, PermissionLevel.FULL]:
            has_permission &= info.is_readable

        if permission_level in [PermissionLevel.WRITE, PermissionLevel.READ_WRITE, PermissionLevel.FULL]:
            has_permission &= info.is_writable

        if permission_level in [PermissionLevel.EXECUTE, PermissionLevel.FULL]:
            has_permission &= info.is_executable

        if not has_permission:
            error = PermissionDiagnostic.diagnose_permission_error(
                path, permission_level, PermissionError()
            )
            return False, error

        return True, None

    except Exception as e:
        error = PermissionDiagnostic.diagnose_permission_error(
            Path(file_path), permission_level, e
        )
        return False, error


def set_permission(file_path: Union[str, Path],
                  permission_level: PermissionLevel,
                  apply_to_owner: bool = True,
                  apply_to_group: bool = False,
                  apply_to_others: bool = False) -> Tuple[bool, Optional[PermissionError]]:
    """
    设置文件或目录权限

    Args:
        file_path: 文件或目录路径
        permission_level: 要设置的权限级别
        apply_to_owner: 是否应用到所有者
        apply_to_group: 是否应用到组
        apply_to_others: 是否应用到其他用户

    Returns:
        (是否成功, 错误信息)
    """
    try:
        path = validate_path_security(file_path)

        if not path.exists():
            error = PermissionDiagnostic.diagnose_permission_error(
                path, permission_level, FileNotFoundError()
            )
            return False, error

        platform_type = get_current_platform()

        if platform_type == PlatformType.WINDOWS:
            return _set_windows_permission(path, permission_level)
        else:
            return _set_unix_permission(path, permission_level,
                                      apply_to_owner, apply_to_group, apply_to_others)

    except Exception as e:
        error = PermissionDiagnostic.diagnose_permission_error(
            Path(file_path), permission_level, e
        )
        return False, error


def _set_windows_permission(path: Path, permission_level: PermissionLevel) -> Tuple[bool, Optional[PermissionError]]:
    """设置Windows文件权限（增强版）"""
    try:
        # Windows上主要通过修改只读属性和使用icacls命令
        if permission_level in [PermissionLevel.WRITE, PermissionLevel.READ_WRITE, PermissionLevel.FULL]:
            # 移除只读属性
            try:
                current_attrs = path.stat().st_file_attributes if hasattr(path.stat(), 'st_file_attributes') else 0
                if current_attrs & 1:  # FILE_ATTRIBUTE_READONLY
                    try:
                        # 使用Python的内置方法移除只读属性
                        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        # 如果失败，尝试使用attrib命令
                        try:
                            subprocess.run(['attrib', '-R', str(path)], check=True,
                                         capture_output=True, timeout=10)
                        except subprocess.SubprocessError:
                            # attrib失败，尝试icacls
                            pass
            except (OSError, AttributeError):
                # 忽略属性检查失败
                pass

            # 尝试使用icacls设置更详细的权限
            try:
                # 获取当前用户
                import getpass
                username = getpass.getuser()

                # 根据权限级别设置不同的权限
                if permission_level == PermissionLevel.FULL:
                    # 完全控制
                    icacls_cmd = ['icacls', str(path), '/grant', f'{username}:(F)']
                elif permission_level == PermissionLevel.READ_WRITE:
                    # 读写权限
                    icacls_cmd = ['icacls', str(path), '/grant', f'{username}:(M)']
                elif permission_level == PermissionLevel.WRITE:
                    # 写权限
                    icacls_cmd = ['icacls', str(path), '/grant', f'{username}:(W)']
                else:
                    # 读权限
                    icacls_cmd = ['icacls', str(path), '/grant', f'{username}:(R)']

                # 执行icacls命令
                result = subprocess.run(icacls_cmd, check=False, capture_output=True,
                                      text=True, timeout=15)

                if result.returncode != 0:
                    # icacls失败，但不一定是致命错误
                    # 记录错误但继续验证权限
                    pass

            except (subprocess.SubprocessError, FileNotFoundError, ImportError):
                # icacls不可用或失败，使用基本方法
                pass

        # 验证权限设置是否成功
        final_check, check_error = check_permission(path, permission_level)
        if not final_check:
            # 权限设置失败，提供详细的诊断信息
            platform_info = _get_windows_permission_info(path)

            suggested_fixes = [
                "右键文件选择'属性' -> '安全'选项卡手动设置权限",
                "确保当前用户是文件的所有者",
                "检查父目录的权限设置"
            ]

            if platform_info.get("is_in_protected_location", False):
                suggested_fixes.insert(0, "以管理员身份运行程序")

            if platform_info.get("is_locked", False):
                suggested_fixes.insert(0, "关闭所有正在使用此文件的程序")

            error = PermissionError(
                error_code="WINDOWS_PERMISSION_SET_FAILED",
                message=f"无法设置Windows文件权限: {path}",
                suggested_fix=suggested_fixes[0],
                alternative_solutions=suggested_fixes[1:],
                is_recoverable=True,
                requires_admin=platform_info.get("is_in_protected_location", False)
            )
            return False, error

        return True, None

    except Exception as e:
        error = PermissionDiagnostic.diagnose_permission_error(
            path, permission_level, e
        )
        return False, error


def _set_unix_permission(path: Path, permission_level: PermissionLevel,
                        apply_to_owner: bool, apply_to_group: bool,
                        apply_to_others: bool) -> Tuple[bool, Optional[PermissionError]]:
    """设置Unix/Linux/macOS文件权限"""
    try:
        current_mode = path.stat().st_mode

        # 计算新的权限模式
        new_mode = current_mode

        # 定义权限位
        owner_perms = 0
        group_perms = 0
        other_perms = 0

        if permission_level in [PermissionLevel.READ, PermissionLevel.READ_WRITE, PermissionLevel.FULL]:
            owner_perms |= stat.S_IRUSR
            group_perms |= stat.S_IRGRP
            other_perms |= stat.S_IROTH

        if permission_level in [PermissionLevel.WRITE, PermissionLevel.READ_WRITE, PermissionLevel.FULL]:
            owner_perms |= stat.S_IWUSR
            group_perms |= stat.S_IWGRP
            other_perms |= stat.S_IWOTH

        if permission_level in [PermissionLevel.EXECUTE, PermissionLevel.FULL]:
            owner_perms |= stat.S_IXUSR
            group_perms |= stat.S_IXGRP
            other_perms |= stat.S_IXOTH

        # 应用权限
        if apply_to_owner:
            # 清除现有所有者权限，设置新权限
            new_mode &= ~(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            new_mode |= owner_perms

        if apply_to_group:
            new_mode &= ~(stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP)
            new_mode |= group_perms

        if apply_to_others:
            new_mode &= ~(stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)
            new_mode |= other_perms

        # 设置权限
        os.chmod(path, new_mode)
        return True, None

    except OSError as e:
        error = PermissionDiagnostic.diagnose_permission_error(
            path, permission_level, e
        )
        return False, error


def make_script_executable(script_path: Union[str, Path]) -> Tuple[bool, Optional[PermissionError]]:
    """
    使脚本文件可执行（增强版）

    Args:
        script_path: 脚本文件路径

    Returns:
        (是否成功, 错误信息)
    """
    try:
        path = validate_path_security(script_path)
        platform_type = get_current_platform()

        if not path.exists():
            error = PermissionDiagnostic.diagnose_permission_error(
                path, PermissionLevel.EXECUTE, FileNotFoundError()
            )
            return False, error

        if platform_type == PlatformType.WINDOWS:
            return _make_windows_script_executable(path)
        elif platform_type == PlatformType.MACOS:
            return _make_macos_script_executable(path)
        else:  # Linux and other Unix-like systems
            return _make_linux_script_executable(path)

    except Exception as e:
        error = PermissionDiagnostic.diagnose_permission_error(
            Path(script_path), PermissionLevel.EXECUTE, e
        )
        return False, error


def _make_windows_script_executable(path: Path) -> Tuple[bool, Optional[PermissionError]]:
    """使Windows脚本可执行"""
    suffix = path.suffix.lower()

    # Python脚本
    if suffix in ['.py', '.pyw']:
        # 检查Python解释器是否可用
        try:
            result = subprocess.run(['python', '--version'], capture_output=True, timeout=5)
            if result.returncode != 0:
                try:
                    result = subprocess.run(['py', '--version'], capture_output=True, timeout=5)
                    if result.returncode != 0:
                        error = PermissionError(
                            error_code="PYTHON_NOT_FOUND",
                            message="Python解释器未找到或不可用",
                            suggested_fix="安装Python或确保Python在PATH环境变量中",
                            alternative_solutions=[
                                "从Microsoft Store安装Python",
                                "从python.org下载并安装Python",
                                "检查PATH环境变量设置"
                            ],
                            is_recoverable=True
                        )
                        return False, error
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass  # Python检查失败不影响文件权限设置
        except (subprocess.SubprocessError, FileNotFoundError):
            pass  # Python检查失败不影响文件权限设置

        # 确保文件可读写
        return set_permission(path, PermissionLevel.READ_WRITE)

    # PowerShell脚本
    elif suffix in ['.ps1', '.psm1']:
        # 检查PowerShell执行策略
        try:
            result = subprocess.run(['powershell', '-Command', 'Get-ExecutionPolicy'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                policy = result.stdout.strip()
                if policy in ['Restricted', 'AllSigned']:
                    error = PermissionError(
                        error_code="POWERSHELL_EXECUTION_POLICY",
                        message=f"PowerShell执行策略限制: {policy}",
                        suggested_fix="以管理员身份运行PowerShell并执行: Set-ExecutionPolicy RemoteSigned",
                        alternative_solutions=[
                            "Set-ExecutionPolicy Bypass -Scope Process",
                            "Set-ExecutionPolicy Unrestricted -Scope CurrentUser",
                            "使用 -ExecutionPolicy Bypass 参数运行脚本"
                        ],
                        is_recoverable=True,
                        requires_admin=True
                    )
                    return False, error
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        return set_permission(path, PermissionLevel.READ_WRITE)

    # 批处理文件
    elif suffix in ['.bat', '.cmd']:
        return set_permission(path, PermissionLevel.READ_WRITE)

    # 可执行文件
    elif suffix in ['.exe', '.com', '.msi']:
        # 检查数字签名
        try:
            result = subprocess.run(['powershell', '-Command', f'Get-AuthenticodeSignature "{path}"'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and 'NotSigned' in result.stdout:
                error = PermissionError(
                    error_code="UNSIGNED_EXECUTABLE",
                    message="可执行文件未签名，可能被Windows Defender阻止",
                    suggested_fix="从可信来源获取已签名的文件",
                    alternative_solutions=[
                        "将文件添加到Windows Defender排除列表",
                        "暂时禁用实时保护",
                        "联系软件供应商获取签名版本"
                    ],
                    is_recoverable=True
                )
                return False, error
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        return set_permission(path, PermissionLevel.FULL)

    # 其他类型
    else:
        return set_permission(path, PermissionLevel.READ_WRITE)


def _make_macos_script_executable(path: Path) -> Tuple[bool, Optional[PermissionError]]:
    """使macOS脚本可执行"""
    # 首先设置执行权限
    success, error = set_permission(path, PermissionLevel.EXECUTE,
                                  apply_to_owner=True, apply_to_group=True, apply_to_others=False)
    if not success:
        return False, error

    # 检查Gatekeeper状态
    try:
        result = subprocess.run(['spctl', '-a', '-v', str(path)],
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            # 文件被Gatekeeper阻止
            if 'quarantine' in result.stderr.lower():
                # 尝试移除隔离属性
                try:
                    subprocess.run(['xattr', '-d', 'com.apple.quarantine', str(path)],
                                 check=True, capture_output=True, timeout=10)
                except subprocess.SubprocessError:
                    error = PermissionError(
                        error_code="MACOS_QUARANTINE",
                        message="文件被macOS隔离，无法执行",
                        suggested_fix="在终端中运行: xattr -d com.apple.quarantine " + str(path),
                        alternative_solutions=[
                            "在系统偏好设置中允许来自任何来源的应用",
                            "右键点击文件选择'打开'来信任该应用",
                            "使用sudo权限移除隔离属性"
                        ],
                        is_recoverable=True
                    )
                    return False, error
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 检查SIP保护
    path_str = str(path)
    if any(path_str.startswith(p) for p in ["/System", "/usr", "/bin", "/sbin"]):
        error = PermissionError(
            error_code="MACOS_SIP_PROTECTED",
            message="文件位于SIP保护的系统目录中",
            suggested_fix="将脚本移动到用户目录或/usr/local目录",
            alternative_solutions=[
                "使用/usr/local/bin目录",
                "将脚本放在用户主目录",
                "禁用SIP（不推荐）"
            ],
            is_recoverable=True
        )
        return False, error

    return True, None


def _make_linux_script_executable(path: Path) -> Tuple[bool, Optional[PermissionError]]:
    """使Linux脚本可执行"""
    # 设置执行权限
    success, error = set_permission(path, PermissionLevel.EXECUTE,
                                  apply_to_owner=True, apply_to_group=True, apply_to_others=False)
    if not success:
        return False, error

    # 检查SELinux上下文
    try:
        result = subprocess.run(['getenforce'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip() == 'Enforcing':
            # SELinux在强制模式，检查文件上下文
            result = subprocess.run(['ls', '-Z', str(path)],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                context = result.stdout.split()[0]
                if 'exec_t' not in context and 'bin_t' not in context:
                    # 尝试设置正确的SELinux上下文
                    try:
                        subprocess.run(['chcon', '-t', 'bin_t', str(path)],
                                     check=True, capture_output=True, timeout=10)
                    except subprocess.SubprocessError:
                        error = PermissionError(
                            error_code="SELINUX_CONTEXT",
                            message="SELinux阻止文件执行",
                            suggested_fix=f"运行: sudo chcon -t bin_t {path}",
                            alternative_solutions=[
                                "sudo setsebool -P allow_execmod 1",
                                f"sudo semanage fcontext -a -t bin_t {path}",
                                "暂时禁用SELinux (setenforce 0)"
                            ],
                            is_recoverable=True,
                            requires_admin=True
                        )
                        return False, error
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 检查文件系统挂载选项
    try:
        result = subprocess.run(['findmnt', '-n', '-o', 'OPTIONS', str(path)],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            options = result.stdout.strip()
            if 'noexec' in options:
                error = PermissionError(
                    error_code="FILESYSTEM_NOEXEC",
                    message="文件系统以noexec选项挂载",
                    suggested_fix="重新挂载文件系统移除noexec选项",
                    alternative_solutions=[
                        "将脚本移动到允许执行的文件系统",
                        "修改/etc/fstab移除noexec选项",
                        "使用解释器直接运行脚本"
                    ],
                    is_recoverable=True,
                    requires_admin=True
                )
                return False, error
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return True, None


def ensure_directory_writable(dir_path: Union[str, Path],
                             create_if_missing: bool = True) -> Tuple[bool, Optional[PermissionError]]:
    """
    确保目录可写

    Args:
        dir_path: 目录路径
        create_if_missing: 如果目录不存在是否创建

    Returns:
        (是否成功, 错误信息)
    """
    try:
        path = validate_path_security(dir_path)

        if not path.exists():
            if create_if_missing:
                # 检查父目录权限
                parent = path.parent
                if not parent.exists():
                    # 递归创建父目录
                    success, error = ensure_directory_writable(parent, create_if_missing=True)
                    if not success:
                        return False, error

                # 创建目录
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    error = PermissionDiagnostic.diagnose_permission_error(
                        path, PermissionLevel.WRITE, e
                    )
                    return False, error
            else:
                error = PermissionDiagnostic.diagnose_permission_error(
                    path, PermissionLevel.WRITE, FileNotFoundError()
                )
                return False, error

        # 检查是否为目录
        if not path.is_dir():
            error = PermissionError(
                error_code="NOT_A_DIRECTORY",
                message=f"{path} 不是一个目录。",
                suggested_fix="确保路径指向一个目录而不是文件。",
                alternative_solutions=["使用不同的目录路径", "删除同名文件后重新创建目录"],
                is_recoverable=False
            )
            return False, error

        # 检查写权限
        return check_permission(path, PermissionLevel.WRITE)

    except Exception as e:
        error = PermissionDiagnostic.diagnose_permission_error(
            Path(dir_path), PermissionLevel.WRITE, e
        )
        return False, error


def get_safe_temp_directory() -> Tuple[Path, Optional[PermissionError]]:
    """
    获取安全的临时目录

    Returns:
        (临时目录路径, 错误信息)
    """
    import tempfile

    try:
        # 尝试系统默认临时目录
        system_temp = Path(tempfile.gettempdir())
        success, error = ensure_directory_writable(system_temp, create_if_missing=False)
        if success:
            return system_temp, None

        # 尝试用户主目录下的temp
        home_temp = Path.home() / "tmp"
        success, error = ensure_directory_writable(home_temp, create_if_missing=True)
        if success:
            return home_temp, None

        # 尝试当前目录下的temp
        current_temp = Path.cwd() / "tmp"
        success, error = ensure_directory_writable(current_temp, create_if_missing=True)
        if success:
            return current_temp, None

        # 所有选项都失败
        error = PermissionError(
            error_code="NO_TEMP_DIRECTORY",
            message="无法找到或创建可写的临时目录。",
            suggested_fix="手动创建一个临时目录并设置适当的权限。",
            alternative_solutions=[
                "检查磁盘空间是否充足",
                "确认用户有创建目录的权限",
                "使用不同的工作目录"
            ],
            is_recoverable=True
        )
        return Path(tempfile.gettempdir()), error

    except Exception as e:
        error = PermissionDiagnostic.diagnose_permission_error(
            Path(tempfile.gettempdir()), PermissionLevel.WRITE, e
        )
        return Path(tempfile.gettempdir()), error


def validate_claude_directory_permissions() -> List[PermissionError]:
    """
    验证Claude相关目录的权限

    Returns:
        权限错误列表（如果为空表示所有权限正常）
    """
    errors = []

    # 检查用户主目录
    home_dir = Path.home()
    success, error = check_permission(home_dir, PermissionLevel.READ_WRITE)
    if not success and error:
        errors.append(error)

    # 检查.claude目录
    claude_dir = home_dir / ".claude"
    success, error = ensure_directory_writable(claude_dir, create_if_missing=True)
    if not success and error:
        errors.append(error)

    # 检查设置文件
    settings_file = claude_dir / "settings.json"
    if settings_file.exists():
        success, error = check_permission(settings_file, PermissionLevel.READ_WRITE)
        if not success and error:
            errors.append(error)

    # 检查日志目录
    logs_dir = claude_dir / "logs"
    success, error = ensure_directory_writable(logs_dir, create_if_missing=True)
    if not success and error:
        errors.append(error)

    # 检查临时目录
    _, temp_error = get_safe_temp_directory()
    if temp_error:
        errors.append(temp_error)

    return errors


def create_directory_with_permissions(dir_path: Union[str, Path],
                                    permission_level: PermissionLevel = PermissionLevel.READ_WRITE,
                                    recursive: bool = True) -> Tuple[bool, Optional[PermissionError]]:
    """
    创建目录并设置权限

    Args:
        dir_path: 目录路径
        permission_level: 权限级别
        recursive: 是否递归创建父目录

    Returns:
        (是否成功, 错误信息)
    """
    try:
        path = validate_path_security(dir_path)

        # 创建目录
        if recursive:
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(exist_ok=True)

        # 设置权限
        return set_permission(path, permission_level, apply_to_owner=True)

    except Exception as e:
        error = PermissionDiagnostic.diagnose_permission_error(
            Path(dir_path), permission_level, e
        )
        return False, error


def fix_directory_permissions(dir_path: Union[str, Path],
                            recursive: bool = False) -> Tuple[bool, List[PermissionError]]:
    """
    修复目录权限问题

    Args:
        dir_path: 目录路径
        recursive: 是否递归修复子目录

    Returns:
        (是否成功, 错误列表)
    """
    errors = []
    path = validate_path_security(dir_path)

    if not path.exists():
        error = PermissionDiagnostic.diagnose_permission_error(
            path, PermissionLevel.READ_WRITE, FileNotFoundError()
        )
        return False, [error]

    if not path.is_dir():
        error = PermissionError(
            error_code="NOT_A_DIRECTORY",
            message=f"{path} 不是一个目录",
            suggested_fix="确保路径指向一个目录",
            alternative_solutions=["检查路径是否正确"],
            is_recoverable=False
        )
        return False, [error]

    # 修复当前目录权限
    success, error = ensure_directory_writable(path)
    if not success and error:
        errors.append(error)

    # 递归修复子目录
    if recursive:
        try:
            for item in path.rglob('*'):
                if item.is_dir():
                    success, error = ensure_directory_writable(item)
                    if not success and error:
                        errors.append(error)
        except (OSError, PermissionError) as e:
            error = PermissionDiagnostic.diagnose_permission_error(
                path, PermissionLevel.READ_WRITE, e
            )
            errors.append(error)

    return len(errors) == 0, errors


def validate_project_directory_structure(project_root: Union[str, Path]) -> List[PermissionError]:
    """
    验证项目目录结构的权限

    Args:
        project_root: 项目根目录

    Returns:
        权限错误列表
    """
    errors = []
    root = validate_path_security(project_root)

    # 检查的目录列表
    directories_to_check = [
        '.claude',
        '.claude/logs',
        '.claude/backups',
        '.claude/temp',
        '.git',  # 如果存在
        'src',   # 如果存在
        'tests', # 如果存在
    ]

    for dir_name in directories_to_check:
        dir_path = root / dir_name
        if dir_path.exists():
            success, error = check_permission(dir_path, PermissionLevel.READ_WRITE)
            if not success and error:
                errors.append(error)

    return errors


def diagnose_system_permissions() -> Dict[str, Any]:
    """
    诊断系统级权限问题

    Returns:
        诊断结果字典
    """
    diagnosis = {
        "platform": get_current_platform().value,
        "timestamp": datetime.now().isoformat(),
        "issues": [],
        "recommendations": [],
        "system_info": {}
    }

    platform = get_current_platform()

    # 检查用户权限
    try:
        import getpass
        current_user = getpass.getuser()
        diagnosis["system_info"]["current_user"] = current_user

        # 检查是否为管理员/root
        if platform == PlatformType.WINDOWS:
            try:
                import ctypes
                is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                diagnosis["system_info"]["is_admin"] = bool(is_admin)
                if not is_admin:
                    diagnosis["recommendations"].append("考虑以管理员身份运行以获得完整权限")
            except Exception:
                diagnosis["system_info"]["is_admin"] = "unknown"
        else:
            is_root = os.getuid() == 0 if hasattr(os, 'getuid') else False
            diagnosis["system_info"]["is_root"] = is_root
            if is_root:
                diagnosis["recommendations"].append("以root身份运行，请注意安全风险")

    except Exception as e:
        diagnosis["issues"].append(f"无法获取用户信息: {e}")

    # 检查关键目录
    key_directories = [
        Path.home(),
        Path.home() / ".claude",
        Path.cwd(),
    ]

    for directory in key_directories:
        try:
            success, error = check_permission(directory, PermissionLevel.READ_WRITE)
            if not success and error:
                diagnosis["issues"].append({
                    "type": "directory_permission",
                    "path": str(directory),
                    "error": error.message,
                    "fix": error.suggested_fix
                })
        except Exception as e:
            diagnosis["issues"].append(f"检查目录权限失败 {directory}: {e}")

    # 平台特定检查
    if platform == PlatformType.WINDOWS:
        diagnosis["system_info"].update(_diagnose_windows_system())
    elif platform == PlatformType.MACOS:
        diagnosis["system_info"].update(_diagnose_macos_system())
    else:
        diagnosis["system_info"].update(_diagnose_linux_system())

    return diagnosis


def _diagnose_windows_system() -> Dict[str, Any]:
    """诊断Windows系统权限"""
    info = {}
    try:
        # 检查UAC状态
        result = subprocess.run(['reg', 'query', 'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System',
                               '/v', 'EnableLUA'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            info["uac_enabled"] = "1" in result.stdout
    except Exception:
        info["uac_enabled"] = "unknown"

    return info


def _diagnose_macos_system() -> Dict[str, Any]:
    """诊断macOS系统权限"""
    info = {}
    try:
        # 检查SIP状态
        result = subprocess.run(['csrutil', 'status'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            info["sip_enabled"] = "enabled" in result.stdout.lower()
    except Exception:
        info["sip_enabled"] = "unknown"

    return info


def _diagnose_linux_system() -> Dict[str, Any]:
    """诊断Linux系统权限"""
    info = {}
    try:
        # 检查SELinux状态
        result = subprocess.run(['getenforce'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["selinux_mode"] = result.stdout.strip()
    except Exception:
        info["selinux_mode"] = "unknown"

    return info


# 导出所有公共接口
__all__ = [
    # 枚举和数据类
    'PermissionLevel',
    'PlatformType',
    'PermissionInfo',
    'PermissionError',
    'PermissionDiagnostic',

    # 核心函数
    'get_current_platform',
    'get_permission_info',
    'check_permission',
    'set_permission',
    'make_script_executable',
    'ensure_directory_writable',
    'get_safe_temp_directory',
    'validate_claude_directory_permissions',

    # 增强的目录管理功能
    'create_directory_with_permissions',
    'fix_directory_permissions',
    'validate_project_directory_structure',
    'diagnose_system_permissions',
]
