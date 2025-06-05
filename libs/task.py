def task(cls=None, *, logger=None, on_init=None, on_step_done=None, on_finish=None, on_progress=None):
    def wrap(klass):
        orig_init = klass.__init__

        def __init__(self, *args, steps=0, task_parent=None, **kwargs):
            self._task_steps = steps
            self._task_completed = 0
            self._task_last_message = None
            self._task_finished = False
            self._task_logger = logger
            self._task_on_init = on_init
            self._task_on_step_done = on_step_done
            self._task_on_finish = on_finish
            self._task_on_progress = on_progress
            self.task_parent = task_parent
            orig_init(self, *args, **kwargs)
            if self._task_on_init:
                self._task_on_init(self)

        def set_steps(self, steps):
            if self._task_finished:
                if self._task_logger:
                    self._task_logger.warning("Cannot set steps after task is finished.")
                return
            self._task_steps = steps

        def step_done(self, message=""):
            if self._task_finished:
                if self._task_logger:
                    self._task_logger.warning("Step done called after task finished.")
                return
            self._task_completed += 1
            self._task_last_message = message
            if self._task_logger:
                self._task_logger.info(f"Step done: {message}")
            if self.task_progress > 100:
                if self._task_logger:
                    self._task_logger.warning("Progress exceeded 100%.")
                else:
                    print("Warning: Progress exceeded 100%.")
            if self._task_on_step_done:
                self._task_on_step_done(self, message)
            if self._task_on_progress:
                self._task_on_progress(self, self.task_progress)

        @property
        def progress(self):
            # Check for subtasks
            subtask_progress = []
            for attr in dir(self):
                if attr in ["__class__"]:
                    continue
                if attr in ["_task_steps", "_task_completed", "_task_last_message", "_task_finished", "_task_logger", "_task_on_init", "_task_on_step_done", "_task_on_finish", "_task_on_progress"]:
                    continue
                if attr in ["task_step_done", "task_progress", "task_last_message", "task_finish", "task_is_finished", "task_parent","task_total_progress"]:
                    continue
                value = getattr(self, attr)
                if hasattr(value, "_is_task_decorated"):
                    subtask_progress.append(value.task_progress/100)
            if subtask_progress:
                if self._task_steps == 0:                    
                    prog = sum(subtask_progress) / (len(subtask_progress))
                else:
                    partial_progress = sum(subtask_progress) 
                    total_steps = self._task_steps + len(subtask_progress)
                    prog = min(100, (self._task_completed + partial_progress) / total_steps * 100)
            else:
                if self._task_steps == 0:
                    prog = 100
                else:
                    prog = min(100, (self._task_completed / self._task_steps) * 100)

            return prog
        
        @property
        def total_progress(self):
            if self.task_parent:
                return self.task_parent.task_total_progress
            else:
                return self.task_progress

        @property
        def last_message(self):
            return self._task_last_message

        def finish(self):
            self._task_finished = True
            if self.task_progress < 100:
                msg = f"Task finished but progress is {self.task_progress:.2f}%"
                if self._task_logger:
                    self._task_logger.warning(msg)
                else:
                    print("Warning:", msg)
            if self._task_on_finish:
                self._task_on_finish(self)


        @property
        def is_finished(self):
            return self._task_finished

        klass.__init__ = __init__
        klass.task_step_done = step_done
        klass.task_finish = finish
        klass.task_progress = progress
        klass.task_total_progress = total_progress
        klass.task_last_message = last_message
        klass.task_is_finished = is_finished
        klass.task_set_steps = set_steps
        klass._is_task_decorated = True
        return klass

    if cls is None:
        return wrap
    return wrap(cls)

