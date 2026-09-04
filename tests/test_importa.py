import pytest


def test_importa_all():
    try:
        import m4i
    except ImportError as e:
        pytest.fail(f"Failed to import m4i: {e}")
        return
    assert hasattr(m4i, "utils")
    assert hasattr(m4i, "TaskBase")
    assert hasattr(m4i, "IniClass")
    assert hasattr(m4i, "ParamsParser")
    assert hasattr(m4i, "log")
    assert hasattr(m4i, "matrix")
    assert hasattr(m4i, "graphs")
    assert hasattr(m4i, "connectors")
    assert hasattr(m4i, "server")
    assert hasattr(m4i, "database")
    assert hasattr(m4i, "simulators")
    assert hasattr(m4i, "assignment_models")
    assert hasattr(m4i, "fcd")
    assert hasattr(m4i, "ops")
    assert hasattr(m4i, "Dispatcher")


def test_importa_specific_modules():
    try:
        from m4i import utils, IniClass, ParamsParser, log
        from m4i import matrix, graphs, connectors, server, database
        from m4i import simulators, assignment_models, fcd, ops, Dispatcher
    except ImportError as e:
        pytest.fail(f"Failed to import m4i: {e}")
        return
    assert hasattr(Dispatcher, "run_dynamic_assignment")
    assert hasattr(assignment_models, "AssignmentModel")
    assert hasattr(ops, "OP")
    assert hasattr(IniClass, "load_parameters")
    assert hasattr(simulators, "BaseSimulator")
    assert hasattr(connectors, "Loader")
    assert hasattr(utils, "Parallel")
    assert hasattr(log, "Logger")
    assert hasattr(ParamsParser, "get")
    assert hasattr(database, "Execution")
    assert hasattr(fcd, "RTServer")
    assert hasattr(graphs, "DynamicGraph")
    assert hasattr(server, "start_server")
    assert hasattr(matrix, "MatrixOD")


if __name__ == "__main__":
    test_importa_all()
    test_importa_specific_modules()
