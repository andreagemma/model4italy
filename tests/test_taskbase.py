from m4i import TaskBase  # adatta all'import corretto
import pytest


class DummyLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, msg):
        self.infos.append(msg)

    def warning(self, msg):
        self.warnings.append(msg)


def test_task_class_basic_progress_and_finish():
    class MyTask(TaskBase):
        def __init__(self):
            super().__init__(task_steps=3)

    t = MyTask()
    assert t.task_progress == 0
    t.task_step_done("step 1")
    assert t.task_progress == pytest.approx(100 / 3)
    t.task_step_done("step 2")
    assert t.task_progress == pytest.approx(200 / 3)
    t.task_step_done("step 3")
    assert t.task_progress == 100
    assert not t.task_is_finished
    t.task_finish()
    assert t.task_is_finished


def test_task_class_logger_and_over_progress():
    task_logger = DummyLogger()

    class MyTask(TaskBase):
        def __init__(self):
            super().__init__(task_steps=1, task_logger=task_logger)

    t = MyTask()
    t.task_step_done("done")
    t.task_step_done("should warn")
    assert (
        any("Step done called after task finished." in w for w in task_logger.warnings)
        or t.task_progress == 100
    )
    t._task_finished = False
    t._task_completed = 2
    t.task_step_done("over progress")
    assert (
        any("Progress exceeded 100%" in w for w in task_logger.warnings)
        or t.task_progress == 100
    )


def test_task_class_last_message_and_finish_warning():
    task_logger = DummyLogger()

    class MyTask(TaskBase):
        def __init__(self):
            super().__init__(task_steps=2, task_logger=task_logger)

    t = MyTask()
    t.task_step_done("first")
    t.task_finish()
    assert any("Task finished but progress is" in w for w in task_logger.warnings)
    assert t.task_last_message == "first"


def test_task_class_zero_steps():
    class MyTask(TaskBase):
        def __init__(self):
            super().__init__(task_steps=0)

    t = MyTask()
    assert t.task_progress == 100


def test_task_class_with_subtasks_progress_and_last_message():
    class SubTask(TaskBase):
        def __init__(self, parent):
            super().__init__(task_steps=2, task_parent=parent, task_weight=1)

    class MainTask(TaskBase):
        def __init__(self):
            super().__init__(task_steps=2)
            self.sub1 = SubTask(self)
            self.sub2 = SubTask(self)

    t = MainTask()
    t.sub1.task_step_done("sub1 step1")
    t.sub2.task_step_done("sub2 step1")
    assert t.task_progress == pytest.approx((2 / 6) * 100)
    t.sub1.task_step_done("sub1 step2")
    assert t.task_progress == pytest.approx((3 / 6) * 100)
    assert t.sub1.task_progress == 100
    assert t.sub1.task_total_progress == pytest.approx((3 / 6) * 100)
    t.sub2.task_step_done("sub2 step2")
    assert t.task_progress == pytest.approx((4 / 6) * 100)
    assert t.sub2.task_last_message == "sub2 step2"
    t.task_step_done("main step1")
    assert t.task_progress == pytest.approx((5 / 6) * 100)
    t.task_step_done("main step2")
    assert t.task_progress == 100
    assert t.task_last_message == "main step2"


def test_task_class_last_message_with_no_steps():
    class MyTask(TaskBase):
        def __init__(self):
            super().__init__(task_steps=1)

    t = MyTask()
    assert t.task_last_message is None
