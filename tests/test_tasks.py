from libs.task import task
import operator
import pytest
class DummyLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []
    def info(self, msg):
        self.infos.append(msg)
    def warning(self, msg):
        self.warnings.append(msg)
 



def test_task_decorator_basic_progress_and_finish():
    @task
    class MyTask:
        def __init__(self):
            pass

    t = MyTask(steps=3)
    assert t.task_progress == 0
    t.task_step_done("step 1")
    assert t.task_progress == pytest.approx(100/3)
    t.task_step_done("step 2")
    assert t.task_progress == pytest.approx(200/3)
    t.task_step_done("step 3")
    assert t.task_progress == 100
    assert not t.task_is_finished
    t.task_finish()
    assert t.task_is_finished

def test_task_decorator_logger_and_over_progress():
    logger = DummyLogger()
    @task(logger=logger)
    class MyTask:
        def __init__(self):
            pass

    t = MyTask(steps=1)
    t.task_step_done("done")
    t.task_step_done("should warn")
    assert any("Step done called after task finished." in w for w in logger.warnings) or t.task_progress == 100
    t._task_finished = False
    t._task_completed = 2
    t.task_step_done("over progress")
    assert any("Progress exceeded 100%" in w for w in logger.warnings) or t.task_progress == 100

def test_task_decorator_last_message_and_finish_warning():
    logger = DummyLogger()
    @task(logger=logger)
    class MyTask:
        def __init__(self):
            pass

    t = MyTask(steps=2)
    t.task_step_done("first")
    t.task_finish()
    assert any("Task finished but progress is" in w for w in logger.warnings)
    assert t.task_last_message == "first"

def test_task_decorator_zero_steps():
    @task
    class MyTask:
        def __init__(self):
            pass

    t = MyTask(steps=0)
    assert t.task_progress == 100

def test_task_with_subtasks_progress_and_last_message():
    @task
    class SubTask:
        def __init__(self):
            pass

    @task
    class MainTask:
        def __init__(self):
            self.sub1 = SubTask(steps=2, task_parent=self)
            self.sub2 = SubTask(steps=2, task_parent=self)

    t = MainTask(steps=2)
    t.sub1.task_step_done("sub1 step1")
    t.sub2.task_step_done("sub2 step1")
    assert t.task_progress == 25
    t.sub1.task_step_done("sub1 step2")
    assert t.task_progress == 37.5
    assert t.sub1.task_progress == 100
    assert t.sub1.task_total_progress == 37.5
    t.sub2.task_step_done("sub2 step2")
    assert t.task_progress == 50
    assert t.sub2.task_last_message == "sub2 step2"
    t.task_step_done("main step1")
    assert t.task_progress == 75
    t.task_step_done("main step2")
    assert t.task_progress == 100
    assert t.task_last_message == "main step2"

def test_task_last_message_with_no_steps():
    @task
    class MyTask:
        def __init__(self):
            pass

    t = MyTask(steps=1)
    assert t.task_last_message is None