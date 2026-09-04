from math import isclose


class TaskBase:
    def __init__(
        self,
        task_steps=0,
        task_weight=1,
        task_parent=None,
        *,
        task_logger=None,
        task_on_init=None,
        task_on_finish=None,
        task_on_progress=None,
        **kwargs,
    ):
        self.task_steps = task_steps
        self.task_completed = 0
        self.task_last_message = None
        self.task_finished = False
        self.task_logger = task_logger
        self.task_on_init = task_on_init
        self.task_on_finish = task_on_finish
        self.task_on_progress = task_on_progress
        self.task_weight = task_weight
        self.task_parent = task_parent
        self.__total_progress = None
        if self.task_on_init:
            self.task_on_init(self)

    def clear_cache(self):
        """Reset the task to its initial state."""
        current = self
        while True:
            current.__total_progress = None  # Reset total progress
            if current.task_parent:
                current = current.task_parent
            else:
                break

    @property
    def _total_progress(self):
        return self.__total_progress

    @_total_progress.setter
    def _total_progress(self, value):
        self.__total_progress = value

    def calc_task_steps(self):
        if hasattr(self, "task_steps"):
            return self.task_steps if self.task_steps is not None else 0
        return 0

    def task_set_steps(self, steps):
        self.clear_cache()  # Reset total progress to recalculate
        if self.task_finished:
            if self.task_logger:
                self.task_logger.warning("Cannot set steps after task is finished.")
            return
        self.task_steps = steps

    def task_step_done(self, message="", w=1):
        self.clear_cache()  # Reset total progress to recalculate
        if self.task_finished:
            if self.task_logger:
                self.task_logger.warning("Step done called after task finished.")
            return
        self.task_completed += (self.task_weight / self.task_steps if self.task_steps > 0 else 1) * w
        self.task_last_message = message
        if self.task_logger and message:
            self.task_logger.info(f"Step done: {message}")
        if (not isclose(self.task_progress, 100, abs_tol=1e-3)) and self.task_progress > 100:
            warning_msg = "Progress exceeded 100%."
            if self.task_logger:
                self.task_logger.warning(warning_msg)
            else:
                print("Warning:", warning_msg)

        current = self
        while True:
            if current.task_on_progress:
                current.task_on_progress(self, message, self.task_progress)
            if current.task_parent:
                current = current.task_parent
            else:
                break

    @property
    def task_progress(self):
        if self._total_progress is not None:
            return self._total_progress
        subtask_progress = []
        subtask_weight = 0
        for attr in dir(self):
            if attr.startswith("_") or attr.startswith("task_"):
                continue
            value = getattr(self, attr)
            if isinstance(value, TaskBase) and value.task_parent is self:
                subtask_progress.append(value.task_progress / 100 * value.task_weight)
                subtask_weight += value.task_weight
        if subtask_progress:
            if self.task_steps == 0:
                prog = sum(subtask_progress) / subtask_weight * 100
            else:
                total_steps = self.task_weight + subtask_weight
                partial_progress = sum(subtask_progress)
                prog = min(100, (self.task_completed + partial_progress) / total_steps * 100)
        else:
            if self.task_steps == 0:
                prog = 100
            else:
                prog = min(100, self.task_completed / self.task_weight * 100)
        self._total_progress = prog
        return prog

    @property
    def task_total_progress(self):
        return self.task_grand_parent.task_progress

    @property
    def task_grand_parent(self):
        if self.task_parent:
            return self.task_parent.task_grand_parent
        else:
            return self

    def task_finish(self):
        self.task_finished = True
        if (not isclose(self.task_progress, 100, abs_tol=1e-3)) and self.task_progress < 100:
            msg = f"Task finished but progress is {self.task_progress:.2f}%"
            if self.task_logger:
                self.task_logger.warning(msg)
            else:
                print("Warning:", msg)
        if self.task_on_finish:
            self.task_on_finish(self)

    @property
    def task_is_finished(self):
        return self.task_finished

    @property
    def _is_task_decorated(self):
        return True
