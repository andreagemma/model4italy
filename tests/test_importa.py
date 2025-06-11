import pytest

def test_importa_all():
    try:
        import libs
    except ImportError as e:
        pytest.fail(f"Failed to import libs: {e}")
        return
    assert hasattr(libs, 'utils')
    assert hasattr(libs, 'TaskBase')
    assert hasattr(libs, 'IniClass')
    assert hasattr(libs, 'ParamsParser')
    assert hasattr(libs, 'log')
    assert hasattr(libs, 'matrix')
    assert hasattr(libs, 'graphs')
    assert hasattr(libs, 'connectors')    
    assert hasattr(libs, 'server')
    assert hasattr(libs, 'database')
    assert hasattr(libs, 'simulators')
    assert hasattr(libs, 'assignment_models')
    assert hasattr(libs, 'fcd')
    assert hasattr(libs, 'ops')
    assert hasattr(libs, 'Dispatcher')

def test_importa_specific_modules():
    try:
        from libs import utils, IniClass, ParamsParser, log
        from libs import matrix, graphs, connectors, server, database
        from libs import simulators, assignment_models, fcd, ops, Dispatcher
    except ImportError as e:
        pytest.fail(f"Failed to import libs: {e}")
        return
    assert hasattr(Dispatcher, 'run_dynamic_assignment')
    assert hasattr(assignment_models, 'AssignmentModel')
    assert hasattr(ops, 'OP')
    assert hasattr(IniClass, 'load_parameters')
    assert hasattr(simulators, 'BaseSimulator')
    assert hasattr(connectors, 'Loader')
    assert hasattr(utils, 'Parallel')
    assert hasattr(log, 'Logger')
    assert hasattr(ParamsParser, 'get')
    assert hasattr(database, 'Execution')
    assert hasattr(fcd, 'RTServer')
    assert hasattr(graphs, 'DynamicGraph')
    assert hasattr(server, 'start_server')
    assert hasattr(matrix, 'MatrixOD')
