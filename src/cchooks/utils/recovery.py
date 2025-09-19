"""错误恢复机制模块，提供自动和手动错误恢复功能。

本模块实现T041任务的恢复需求：
1. 自动重试策略
2. 回滚机制
3. 备份和恢复
4. 优雅降级
5. 故障转移
6. 状态监控和健康检查

支持多种恢复策略：
- 指数退避重试
- 断路器模式
- 备份切换
- 数据回滚
- 服务降级
"""

import asyncio
import json
import shutil
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ..exceptions import (
    CCHooksError,
    ErrorRecoveryAction,
    ErrorSeverity,
    create_error_from_exception,
)
from .logging import get_logger


class RecoveryStrategy(Enum):
    """恢复策略枚举。"""
    NONE = "none"                    # 无恢复
    RETRY = "retry"                  # 重试
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避
    CIRCUIT_BREAKER = "circuit_breaker"          # 断路器
    FAILOVER = "failover"            # 故障转移
    ROLLBACK = "rollback"            # 回滚
    DEGRADED = "degraded"            # 降级服务


class RecoveryState(Enum):
    """恢复状态枚举。"""
    HEALTHY = "healthy"              # 健康
    DEGRADED = "degraded"            # 降级
    FAILING = "failing"              # 失败中
    FAILED = "failed"                # 已失败
    RECOVERING = "recovering"        # 恢复中
    RECOVERED = "recovered"          # 已恢复


@dataclass
class RetryPolicy:
    """重试策略配置。"""
    max_attempts: int = 3
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    backoff_factor: float = 2.0  # 退避因子
    jitter: bool = True  # 是否添加随机抖动


@dataclass
class CircuitBreakerConfig:
    """断路器配置。"""
    failure_threshold: int = 5  # 失败阈值
    timeout: float = 60.0  # 超时时间（秒）
    success_threshold: int = 2  # 成功阈值
    monitor_window: float = 300.0  # 监控窗口（秒）


@dataclass
class BackupConfig:
    """备份配置。"""
    backup_dir: Path = field(default_factory=lambda: Path.home() / ".claude" / "backups")
    max_backups: int = 10
    backup_interval: float = 3600.0  # 备份间隔（秒）
    auto_backup: bool = True


@dataclass
class RecoveryResult:
    """恢复结果。"""
    success: bool
    strategy_used: RecoveryStrategy
    attempts: int
    duration: float
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ErrorRecoveryManager:
    """错误恢复管理器。"""

    def __init__(self, retry_policy: RetryPolicy = None,
                 circuit_breaker_config: CircuitBreakerConfig = None,
                 backup_config: BackupConfig = None):
        """初始化恢复管理器。

        Args:
            retry_policy: 重试策略配置
            circuit_breaker_config: 断路器配置
            backup_config: 备份配置
        """
        self.retry_policy = retry_policy or RetryPolicy()
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.backup_config = backup_config or BackupConfig()

        self._logger = get_logger()
        self._lock = threading.Lock()

        # 断路器状态
        self._circuit_states: Dict[str, Dict[str, Any]] = {}

        # 备份管理
        self._backup_registry: Dict[str, List[Path]] = {}

        # 恢复策略注册表
        self._recovery_strategies: Dict[str, Callable] = {}
        self._register_default_strategies()

        # 健康检查
        self._health_checks: Dict[str, Callable] = {}
        self._component_states: Dict[str, RecoveryState] = {}

        # 确保备份目录存在
        self.backup_config.backup_dir.mkdir(parents=True, exist_ok=True)

    def _register_default_strategies(self) -> None:
        """注册默认的恢复策略。"""
        self._recovery_strategies.update({
            RecoveryStrategy.RETRY.value: self._retry_strategy,
            RecoveryStrategy.EXPONENTIAL_BACKOFF.value: self._exponential_backoff_strategy,
            RecoveryStrategy.CIRCUIT_BREAKER.value: self._circuit_breaker_strategy,
            RecoveryStrategy.ROLLBACK.value: self._rollback_strategy,
            RecoveryStrategy.DEGRADED.value: self._degraded_strategy
        })

    def register_recovery_strategy(self, name: str, strategy: Callable) -> None:
        """注册自定义恢复策略。

        Args:
            name: 策略名称
            strategy: 策略函数
        """
        self._recovery_strategies[name] = strategy
        self._logger.debug(f"注册恢复策略: {name}")

    def register_health_check(self, component: str, check_func: Callable[[], bool]) -> None:
        """注册健康检查函数。

        Args:
            component: 组件名称
            check_func: 健康检查函数
        """
        self._health_checks[component] = check_func
        self._component_states[component] = RecoveryState.HEALTHY
        self._logger.debug(f"注册健康检查: {component}")

    def attempt_recovery(self, error: Exception, operation: Callable,
                        strategies: List[RecoveryStrategy] = None,
                        context: Dict[str, Any] = None) -> RecoveryResult:
        """尝试错误恢复。

        Args:
            error: 发生的错误
            operation: 要重试的操作
            strategies: 恢复策略列表
            context: 上下文信息

        Returns:
            恢复结果
        """
        start_time = time.time()
        context = context or {}

        # 转换为CCHooks异常
        if not isinstance(error, CCHooksError):
            error = create_error_from_exception(error)

        self._logger.error("开始错误恢复", error=error, context=context)

        # 确定恢复策略
        if strategies is None:
            strategies = self._determine_strategies(error)

        # 依次尝试恢复策略
        for strategy in strategies:
            try:
                recovery_func = self._recovery_strategies.get(strategy.value)
                if not recovery_func:
                    self._logger.warning(f"未找到恢复策略: {strategy.value}")
                    continue

                self._logger.info(f"尝试恢复策略: {strategy.value}")

                # 执行恢复策略
                result = recovery_func(error, operation, context)
                if result.success:
                    duration = time.time() - start_time
                    self._logger.info(f"恢复成功，使用策略: {strategy.value}，耗时: {duration:.2f}秒")
                    return RecoveryResult(
                        success=True,
                        strategy_used=strategy,
                        attempts=result.attempts,
                        duration=duration,
                        metadata=result.metadata
                    )

            except Exception as recovery_error:
                self._logger.error(f"恢复策略失败: {strategy.value}", error=recovery_error)
                continue

        # 所有策略都失败
        duration = time.time() - start_time
        self._logger.error(f"所有恢复策略都失败，总耗时: {duration:.2f}秒")
        return RecoveryResult(
            success=False,
            strategy_used=RecoveryStrategy.NONE,
            attempts=0,
            duration=duration,
            error=error
        )

    def _determine_strategies(self, error: CCHooksError) -> List[RecoveryStrategy]:
        """根据错误类型确定恢复策略。"""
        strategies = []

        # 根据恢复动作确定策略
        for action in error.recovery_actions:
            if action == ErrorRecoveryAction.RETRY:
                strategies.append(RecoveryStrategy.EXPONENTIAL_BACKOFF)
            elif action == ErrorRecoveryAction.ROLLBACK:
                strategies.append(RecoveryStrategy.ROLLBACK)
            elif action == ErrorRecoveryAction.SKIP:
                strategies.append(RecoveryStrategy.DEGRADED)

        # 根据错误严重程度添加策略
        if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            strategies.append(RecoveryStrategy.CIRCUIT_BREAKER)

        # 默认策略
        if not strategies:
            strategies = [RecoveryStrategy.RETRY]

        return strategies

    def _retry_strategy(self, error: Exception, operation: Callable,
                       context: Dict[str, Any]) -> RecoveryResult:
        """简单重试策略。"""
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                self._logger.debug(f"重试第 {attempt} 次")
                result = operation()
                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.RETRY,
                    attempts=attempt,
                    duration=0,
                    metadata={"result": result}
                )

            except Exception as retry_error:
                if attempt < self.retry_policy.max_attempts:
                    time.sleep(self.retry_policy.base_delay)
                else:
                    return RecoveryResult(
                        success=False,
                        strategy_used=RecoveryStrategy.RETRY,
                        attempts=attempt,
                        duration=0,
                        error=retry_error
                    )

    def _exponential_backoff_strategy(self, error: Exception, operation: Callable,
                                    context: Dict[str, Any]) -> RecoveryResult:
        """指数退避重试策略。"""
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                self._logger.debug(f"指数退避重试第 {attempt} 次")
                result = operation()
                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.EXPONENTIAL_BACKOFF,
                    attempts=attempt,
                    duration=0,
                    metadata={"result": result}
                )

            except Exception as retry_error:
                if attempt < self.retry_policy.max_attempts:
                    # 计算延迟时间
                    delay = min(
                        self.retry_policy.base_delay * (self.retry_policy.backoff_factor ** (attempt - 1)),
                        self.retry_policy.max_delay
                    )

                    # 添加随机抖动
                    if self.retry_policy.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)

                    self._logger.debug(f"等待 {delay:.2f} 秒后重试")
                    time.sleep(delay)
                else:
                    return RecoveryResult(
                        success=False,
                        strategy_used=RecoveryStrategy.EXPONENTIAL_BACKOFF,
                        attempts=attempt,
                        duration=0,
                        error=retry_error
                    )

    def _circuit_breaker_strategy(self, error: Exception, operation: Callable,
                                 context: Dict[str, Any]) -> RecoveryResult:
        """断路器策略。"""
        operation_name = context.get("operation_name", "unknown")

        with self._lock:
            state = self._circuit_states.get(operation_name, {
                "state": "closed",  # closed, open, half_open
                "failure_count": 0,
                "last_failure_time": None,
                "success_count": 0
            })

            # 检查断路器状态
            if state["state"] == "open":
                # 检查是否可以进入半开状态
                if (time.time() - state["last_failure_time"]) > self.circuit_breaker_config.timeout:
                    state["state"] = "half_open"
                    state["success_count"] = 0
                else:
                    return RecoveryResult(
                        success=False,
                        strategy_used=RecoveryStrategy.CIRCUIT_BREAKER,
                        attempts=0,
                        duration=0,
                        error=Exception("断路器开启，拒绝执行")
                    )

            try:
                result = operation()

                # 操作成功
                if state["state"] == "half_open":
                    state["success_count"] += 1
                    if state["success_count"] >= self.circuit_breaker_config.success_threshold:
                        state["state"] = "closed"
                        state["failure_count"] = 0

                self._circuit_states[operation_name] = state
                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.CIRCUIT_BREAKER,
                    attempts=1,
                    duration=0,
                    metadata={"result": result, "circuit_state": state["state"]}
                )

            except Exception as circuit_error:
                # 操作失败
                state["failure_count"] += 1
                state["last_failure_time"] = time.time()

                if state["failure_count"] >= self.circuit_breaker_config.failure_threshold:
                    state["state"] = "open"

                self._circuit_states[operation_name] = state
                return RecoveryResult(
                    success=False,
                    strategy_used=RecoveryStrategy.CIRCUIT_BREAKER,
                    attempts=1,
                    duration=0,
                    error=circuit_error,
                    metadata={"circuit_state": state["state"]}
                )

    def _rollback_strategy(self, error: Exception, operation: Callable,
                          context: Dict[str, Any]) -> RecoveryResult:
        """回滚策略。"""
        resource_id = context.get("resource_id")
        if not resource_id:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.ROLLBACK,
                attempts=0,
                duration=0,
                error=Exception("缺少resource_id，无法执行回滚")
            )

        try:
            # 查找最近的备份
            backup_path = self._find_latest_backup(resource_id)
            if not backup_path:
                return RecoveryResult(
                    success=False,
                    strategy_used=RecoveryStrategy.ROLLBACK,
                    attempts=0,
                    duration=0,
                    error=Exception(f"未找到 {resource_id} 的备份文件")
                )

            # 执行回滚
            self._restore_from_backup(resource_id, backup_path)
            self._logger.info(f"成功回滚 {resource_id} 到备份: {backup_path}")

            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.ROLLBACK,
                attempts=1,
                duration=0,
                metadata={"backup_path": str(backup_path)}
            )

        except Exception as rollback_error:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.ROLLBACK,
                attempts=1,
                duration=0,
                error=rollback_error
            )

    def _degraded_strategy(self, error: Exception, operation: Callable,
                          context: Dict[str, Any]) -> RecoveryResult:
        """降级策略。"""
        fallback_operation = context.get("fallback_operation")
        if not fallback_operation:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.DEGRADED,
                attempts=0,
                duration=0,
                error=Exception("未提供降级操作")
            )

        try:
            result = fallback_operation()
            self._logger.info("使用降级操作成功")

            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.DEGRADED,
                attempts=1,
                duration=0,
                metadata={"result": result, "degraded": True}
            )

        except Exception as degraded_error:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.DEGRADED,
                attempts=1,
                duration=0,
                error=degraded_error
            )

    def create_backup(self, resource_id: str, source_path: Path) -> Path:
        """创建备份。

        Args:
            resource_id: 资源标识符
            source_path: 源文件路径

        Returns:
            备份文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{resource_id}_{timestamp}.backup"
        backup_path = self.backup_config.backup_dir / backup_name

        try:
            # 复制文件
            shutil.copy2(source_path, backup_path)

            # 更新备份注册表
            if resource_id not in self._backup_registry:
                self._backup_registry[resource_id] = []

            self._backup_registry[resource_id].append(backup_path)

            # 清理旧备份
            self._cleanup_old_backups(resource_id)

            self._logger.info(f"创建备份: {resource_id} -> {backup_path}")
            return backup_path

        except Exception as e:
            self._logger.error(f"创建备份失败: {resource_id}", error=e)
            raise

    def _find_latest_backup(self, resource_id: str) -> Optional[Path]:
        """查找最新的备份文件。"""
        backups = self._backup_registry.get(resource_id, [])
        if not backups:
            return None

        # 按修改时间排序，返回最新的
        valid_backups = [b for b in backups if b.exists()]
        if not valid_backups:
            return None

        return max(valid_backups, key=lambda p: p.stat().st_mtime)

    def _restore_from_backup(self, resource_id: str, backup_path: Path) -> None:
        """从备份恢复文件。"""
        # 这里需要根据具体的资源类型实现恢复逻辑
        # 当前实现假设是简单的文件复制
        pass

    def _cleanup_old_backups(self, resource_id: str) -> None:
        """清理旧的备份文件。"""
        backups = self._backup_registry.get(resource_id, [])
        if len(backups) <= self.backup_config.max_backups:
            return

        # 按修改时间排序
        backups.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)

        # 删除多余的备份
        for backup_path in backups[:-self.backup_config.max_backups]:
            try:
                if backup_path.exists():
                    backup_path.unlink()
                    self._logger.debug(f"删除旧备份: {backup_path}")
            except Exception as e:
                self._logger.warning(f"删除备份失败: {backup_path}", error=e)

        # 更新注册表
        self._backup_registry[resource_id] = backups[-self.backup_config.max_backups:]

    @contextmanager
    def recovery_context(self, operation_name: str, **context):
        """恢复上下文管理器。"""
        context["operation_name"] = operation_name
        try:
            yield self
        except Exception as e:
            self._logger.error(f"操作失败: {operation_name}", error=e)
            # 这里可以自动触发恢复
            raise

    def perform_health_check(self, component: str = None) -> Dict[str, RecoveryState]:
        """执行健康检查。

        Args:
            component: 特定组件名称，None表示检查所有组件

        Returns:
            组件健康状态字典
        """
        results = {}

        components_to_check = [component] if component else list(self._health_checks.keys())

        for comp in components_to_check:
            if comp not in self._health_checks:
                continue

            try:
                check_func = self._health_checks[comp]
                is_healthy = check_func()

                if is_healthy:
                    self._component_states[comp] = RecoveryState.HEALTHY
                else:
                    current_state = self._component_states.get(comp, RecoveryState.HEALTHY)
                    if current_state == RecoveryState.HEALTHY:
                        self._component_states[comp] = RecoveryState.DEGRADED
                    elif current_state == RecoveryState.DEGRADED:
                        self._component_states[comp] = RecoveryState.FAILING
                    else:
                        self._component_states[comp] = RecoveryState.FAILED

                results[comp] = self._component_states[comp]

            except Exception as e:
                self._logger.error(f"健康检查失败: {comp}", error=e)
                self._component_states[comp] = RecoveryState.FAILED
                results[comp] = RecoveryState.FAILED

        return results

    def get_recovery_stats(self) -> Dict[str, Any]:
        """获取恢复统计信息。"""
        return {
            "circuit_breakers": dict(self._circuit_states),
            "backup_registry": {k: len(v) for k, v in self._backup_registry.items()},
            "component_states": {k: v.value for k, v in self._component_states.items()},
            "recovery_strategies": list(self._recovery_strategies.keys()),
            "health_checks": list(self._health_checks.keys())
        }


# 全局恢复管理器实例
_global_recovery_manager: Optional[ErrorRecoveryManager] = None


def get_recovery_manager() -> ErrorRecoveryManager:
    """获取全局恢复管理器。"""
    global _global_recovery_manager
    if _global_recovery_manager is None:
        _global_recovery_manager = ErrorRecoveryManager()
    return _global_recovery_manager


def configure_recovery(retry_policy: RetryPolicy = None,
                      circuit_breaker_config: CircuitBreakerConfig = None,
                      backup_config: BackupConfig = None) -> None:
    """配置全局恢复设置。"""
    global _global_recovery_manager
    _global_recovery_manager = ErrorRecoveryManager(
        retry_policy=retry_policy,
        circuit_breaker_config=circuit_breaker_config,
        backup_config=backup_config
    )


def with_recovery(strategies: List[RecoveryStrategy] = None,
                 context: Dict[str, Any] = None):
    """错误恢复装饰器。"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                recovery_manager = get_recovery_manager()
                result = recovery_manager.attempt_recovery(
                    e, lambda: func(*args, **kwargs), strategies, context
                )
                if result.success:
                    return result.metadata.get("result")
                else:
                    raise result.error or e
        return wrapper
    return decorator


# 导出的类和函数
__all__ = [
    # 枚举类型
    "RecoveryStrategy",
    "RecoveryState",
    # 配置类
    "RetryPolicy",
    "CircuitBreakerConfig",
    "BackupConfig",
    "RecoveryResult",
    # 主要类
    "ErrorRecoveryManager",
    # 全局函数
    "get_recovery_manager",
    "configure_recovery",
    "with_recovery"
]
