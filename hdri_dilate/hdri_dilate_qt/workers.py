from __future__ import annotations

import logging
import sys
import time
import traceback
from collections.abc import Callable

from PySide6.QtCore import *

logger = logging.getLogger()

THREAD_POOL: QThreadPool = QThreadPool.globalInstance()


class WorkerSignals(QObject):
    started = Signal()
    finished = Signal()
    error = Signal(tuple)


class Worker(QRunnable):
    disable_measure_time = False

    def __init__(
            self,
            func: Callable = None,
            *args,
            **kwargs,
    ):
        super().__init__()
        self.setAutoDelete(True)

        self.active = False
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        self.signals.started.emit()
        func = self.func
        if not self.func:
            func = self.spam
        try:
            self.measure_time(
                func,
                *self.args,
                **self.kwargs,
            )
        except Exception as e:
            self.log_error(e)
        finally:
            self.signals.finished.emit()

    def log_error(self, exc: Exception):
        logger.error(exc)
        traceback.print_exc()
        exc_type, value = sys.exc_info()[:2]
        self.signals.error.emit(
            (exc_type, value, traceback.format_exc())
        )

    @staticmethod
    def spam(*args, **kwargs):
        print("SPAM SPAM SPAM!", *args, **kwargs)

    def measure_time(self, func: Callable, *args, **kwargs):
        start_time = time.perf_counter()
        func(*args, **kwargs)
        end_time = time.perf_counter()
        if not self.disable_measure_time:
            logger.debug(
                f"Overall {self.__class__.__name__} took {end_time - start_time:0.4f} secs"
            )


def run_func_in_thread(
        func: Callable,
        *args,
        on_finish: Callable = None,
        is_high_priority=False,
        **kwargs,
):
    worker = Worker(func, *args, **kwargs)
    if on_finish:
        worker.signals.finished.connect(on_finish)

    if is_high_priority:
        THREAD_POOL.setThreadPriority(QThread.Priority.HighPriority)
    else:
        THREAD_POOL.setThreadPriority(QThread.Priority.LowPriority)

    THREAD_POOL.start(worker)


def run_worker_in_thread(
        worker: Worker,
        on_finish: Callable = None,
        is_high_priority=False,
):
    if on_finish:
        worker.signals.finished.connect(on_finish)

    if is_high_priority:
        THREAD_POOL.setThreadPriority(QThread.Priority.HighPriority)
    else:
        THREAD_POOL.setThreadPriority(QThread.Priority.LowPriority)

    THREAD_POOL.start(worker)
