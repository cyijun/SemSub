"""
任务队列 - 生产者消费者模式

实现 CPU 预处理和 GPU 处理的并行化
"""

import queue
import threading
from typing import Callable, Optional, Tuple, Any
from enum import Enum


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskResult:
    """任务结果"""
    def __init__(self, task_id: str, status: TaskStatus, result: Any = None, error: Optional[Exception] = None):
        self.task_id = task_id
        self.status = status
        self.result = result
        self.error = error


class TaskQueue:
    """任务队列 - 生产者消费者模式"""

    def __init__(self, max_workers: int = 2):
        """
        初始化任务队列

        Args:
            max_workers: 最大工作线程数
        """
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.max_workers = max_workers
        self.workers = []
        self._stop_event = threading.Event()
        self._task_counter = 0
        self._lock = threading.Lock()

    def _get_next_task_id(self) -> str:
        """获取下一个任务 ID"""
        with self._lock:
            self._task_counter += 1
            return f"task_{self._task_counter}"

    def submit(self, task_fn: Callable, *args, **kwargs) -> str:
        """
        提交任务

        Args:
            task_fn: 任务函数
            *args, **kwargs: 任务函数参数

        Returns:
            任务 ID
        """
        task_id = self._get_next_task_id()
        self.task_queue.put((task_id, task_fn, args, kwargs))
        return task_id

    def start(self):
        """启动工作线程"""
        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, name=f"TaskWorker-{i}", daemon=True)
            t.start()
            self.workers.append(t)

    def _worker_loop(self):
        """工作线程循环"""
        while not self._stop_event.is_set():
            try:
                task_id, task_fn, args, kwargs = self.task_queue.get(timeout=0.1)
                try:
                    result = task_fn(*args, **kwargs)
                    self.result_queue.put(TaskResult(task_id, TaskStatus.COMPLETED, result=result))
                except Exception as e:
                    self.result_queue.put(TaskResult(task_id, TaskStatus.FAILED, error=e))
            except queue.Empty:
                continue
            except Exception as e:
                # 记录异常但不中断工作线程
                import logging
                logging.getLogger(__name__).error(f"工作线程异常: {e}")

    def get_result(self, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """
        获取任务结果

        Args:
            timeout: 超时时间（秒）

        Returns:
            任务结果，超时返回 None
        """
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        """停止所有工作线程"""
        self._stop_event.set()
        for w in self.workers:
            w.join(timeout=5)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
