import pytest
import timeit
import platform
import psutil


class AttributeFramework:
    def __init__(self):
        from m4i.graphs import (
            DynamicValueAttribute,
            DynamicTimeArrayAttribute,
            DynamicCallableAttribute,
            DynamicAttribute,
        )

        system_info = (
            f"System: {platform.node()}\n"
            f"CPU: {platform.processor()}\n"
            f"RAM: {psutil.virtual_memory().total / (1024**3):.2f} GB\n"
        )
        print(system_info)
        # Set up initial attributes for testing
        self.value_attr = DynamicValueAttribute(10)
        self.array_attr = DynamicTimeArrayAttribute(value=5, total_time=10, delta_t=2)
        self.callable_attr = DynamicCallableAttribute(
            lambda **kw: kw["t"] * 2, total_time=10, delta_t=2
        )


def attribute_tester():
    return AttributeFramework()


def test_value_attribute_operations():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    value_attr = self.value_attr.copy()
    value_attr += 5
    assert value_attr.get_value() == 15

    # Test in-place multiplication
    value_attr *= 2
    assert value_attr.get_value() == 30

    # Test value setting
    value_attr.set_value(50)
    assert value_attr.get_value() == 50

    assert list(value_attr.get_values()) == [50]
    assert list(value_attr.get_times()) == [0]
    assert list(value_attr.get_items()) == [(0, 50)]

    assert list(value_attr.get_values([1, 2])) == [50, 50]
    assert list(value_attr.get_items(list_t=[1, 2])) == [(1, 50), (2, 50)]

    tmp = value_attr + self.array_attr.copy()
    assert isinstance(tmp, DynamicTimeArrayAttribute)
    assert list(tmp.get_items()) == [(0, 55), (2, 55), (4, 55), (6, 55), (8, 55)]

    tmp = value_attr + self.callable_attr.copy()
    assert isinstance(tmp, DynamicCallableAttribute)
    assert list(tmp.get_items()) == [(0, 50), (2, 54), (4, 58), (6, 62), (8, 66)]

    value_attr.save("test.dill")
    tmp = DynamicAttribute.load("test.dill")
    assert isinstance(tmp, DynamicValueAttribute)


def test_time_array_attribute_operations():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    array_attr = self.array_attr.copy()

    # Test getting value at specific time
    value_at_time_3 = array_attr.get_value(t=3)
    assert value_at_time_3 == 5

    # Test in-place addition
    array_attr += 3
    assert array_attr.get_value(t=4) == 8

    # Test in-place multiplication
    array_attr *= 2
    assert array_attr.get_value(t=4) == 16

    array_attr.set_value(5, t=5)
    assert array_attr.get_value(t=5) == 5
    assert array_attr.get_value(t=1) == 16

    # Test resizing attribute
    array_attr.resize_attribute(new_total_time=20)
    assert array_attr.get_values() == [16, 16, 5, 16, 16, 16, 16, 16, 16, 16]

    tmp = array_attr + array_attr
    tmp /= 2
    assert tmp.get_items() == [
        (0, 16),
        (2, 16),
        (4, 5),
        (6, 16),
        (8, 16),
        (10, 16),
        (12, 16),
        (14, 16),
        (16, 16),
        (18, 16),
    ]

    array_attr.save("test.dill")
    tmp = DynamicAttribute.load("test.dill")
    assert isinstance(tmp, DynamicTimeArrayAttribute)

    array_attr.resize_attribute(new_total_time=12, new_delta_t=1)
    assert array_attr.get_items() == [
        (0, 16),
        (1, 16),
        (2, 16),
        (3, 16),
        (4, 5),
        (5, 5),
        (6, 16),
        (7, 16),
        (8, 16),
        (9, 16),
        (10, 16),
        (11, 16),
    ]

    tmp = array_attr + self.array_attr.copy()
    assert isinstance(tmp, DynamicTimeArrayAttribute)
    assert list(tmp.get_items()) == [
        (0, 21),
        (1, 21),
        (2, 21),
        (3, 21),
        (4, 10),
        (5, 10),
        (6, 21),
        (7, 21),
        (8, 21),
        (9, 21),
        (10, 21),
        (11, 21),
    ]

    tmp = array_attr + self.callable_attr.copy()
    assert isinstance(tmp, DynamicTimeArrayAttribute)
    assert list(tmp.get_items()) == [
        (0, 16),
        (1, 16 + 2),
        (2, 16 + 4),
        (3, 16 + 6),
        (4, 5 + 8),
        (5, 5 + 10),
        (6, 16 + 12),
        (7, 16 + 14),
        (8, 16 + 16),
        (9, 16 + 18),
        (10, 16 + 20),
        (11, 16 + 22),
    ]

    array_attr += 1
    assert array_attr.get_items() == [
        (0, 17),
        (1, 17),
        (2, 17),
        (3, 17),
        (4, 6),
        (5, 6),
        (6, 17),
        (7, 17),
        (8, 17),
        (9, 17),
        (10, 17),
        (11, 17),
    ]

    array_attr += DynamicValueAttribute(-1)
    assert array_attr.get_items() == [
        (0, 16),
        (1, 16),
        (2, 16),
        (3, 16),
        (4, 5),
        (5, 5),
        (6, 16),
        (7, 16),
        (8, 16),
        (9, 16),
        (10, 16),
        (11, 16),
    ]


def test_callable_attribute_operations():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    callable_attr = self.callable_attr.copy()

    # Test getting value from callable attribute
    value_at_time_3 = callable_attr.get_value(t=3)
    assert value_at_time_3 == 6

    # Test in-place addition with a scalar
    callable_attr += 4
    assert callable_attr.get_value(t=3) == 10

    # Test resizing callable attribute
    callable_attr.resize_attribute(new_total_time=5, new_delta_t=1)
    assert callable_attr["total_time"] == 5
    assert callable_attr["num_intervals"] == 5
    assert callable_attr.get_values() == [4 + 0, 4 + 2, 4 + 4, 4 + 6, 4 + 8]
    assert callable_attr.get_times() == [0, 1, 2, 3, 4]
    assert callable_attr.get_items() == [
        (0, 4 + 0),
        (1, 4 + 2),
        (2, 4 + 4),
        (3, 4 + 6),
        (4, 4 + 8),
    ]

    tmp = callable_attr + callable_attr
    tmp /= 2
    assert tmp.get_values() == [4 + 0, 4 + 2, 4 + 4, 4 + 6, 4 + 8]

    callable_attr.save("test.dill")
    tmp = DynamicAttribute.load("test.dill")
    assert isinstance(tmp, DynamicCallableAttribute)

    tmp = callable_attr + self.array_attr.copy()
    assert isinstance(tmp, DynamicCallableAttribute)
    assert list(tmp.get_values()) == [9, 11, 13, 15, 17]

    tmp = callable_attr + self.callable_attr.copy()
    assert isinstance(tmp, DynamicCallableAttribute)
    assert list(tmp.get_values()) == [4, 8, 12, 16, 20]

    tmp += 1
    assert list(tmp.get_values()) == [5, 9, 13, 17, 21]

    tmp += DynamicValueAttribute(-1)
    assert tmp.get_values() == [4, 8, 12, 16, 20]

    tmp.set_value(7, 17)
    assert tmp.get_values(list_t=[17, 14]) == [7, 60]


def test_performance():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    # Performance test for large number of operations
    large_array_attr = DynamicTimeArrayAttribute(value=2, total_time=10000, delta_t=1)
    duration = timeit.timeit(lambda: large_array_attr.__imul__(3), number=1)
    duration += timeit.timeit(lambda: large_array_attr + 1, number=1)
    print(f"Performance test duration: {duration:.6f} seconds")
    # assert duration < 1, "Performance issue: Operation took too long."


def test_attribute_copy_operations():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test deep copy functionality"""
    value_attr = self.value_attr.copy()
    array_attr = self.array_attr.copy()
    callable_attr = self.callable_attr.copy()

    # Modify copies and ensure originals are unchanged
    value_attr += 10
    array_attr += 5
    callable_attr += 3

    assert self.value_attr.get_value() == 10
    assert self.array_attr.get_value(t=0) == 5
    assert self.callable_attr.get_value(t=0) == 0


def test_attribute_subtraction_operations():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test subtraction operations between different attribute types"""
    value_attr = DynamicValueAttribute(20)
    array_attr = DynamicTimeArrayAttribute(value=15, total_time=6, delta_t=2)

    # Test subtraction with value attribute
    result = array_attr - value_attr
    assert isinstance(result, DynamicTimeArrayAttribute)
    assert list(result.get_items()) == [(0, -5), (2, -5), (4, -5)]

    # Test subtraction with scalar
    result = array_attr - 5
    assert list(result.get_items()) == [(0, 10), (2, 10), (4, 10)]


def test_attribute_division_operations():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test division operations"""
    array_attr = DynamicTimeArrayAttribute(value=20, total_time=6, delta_t=2)

    # Test division by scalar
    result = array_attr / 4
    assert list(result.get_items()) == [(0, 5.0), (2, 5.0), (4, 5.0)]

    # Test in-place division
    array_attr /= 2
    assert list(array_attr.get_items()) == [(0, 10.0), (2, 10.0), (4, 10.0)]


def test_attribute_boundary_conditions():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test boundary conditions and edge cases"""
    # Test with zero values
    zero_attr = DynamicValueAttribute(0)
    array_attr = self.array_attr.copy()

    result = array_attr + zero_attr
    assert list(result.get_items()) == [(0, 5), (2, 5), (4, 5), (6, 5), (8, 5)]

    # Test with negative values
    neg_attr = DynamicValueAttribute(-5)
    result = array_attr + neg_attr
    assert list(result.get_items()) == [(0, 0), (2, 0), (4, 0), (6, 0), (8, 0)]


def test_attribute_time_interpolation():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test time interpolation behavior"""
    array_attr = DynamicTimeArrayAttribute(value=10, total_time=10, delta_t=5)

    # Test values at exact time points
    assert array_attr.get_value(t=0) == 10
    assert array_attr.get_value(t=5) == 10

    # Test values between time points (should interpolate or use nearest)
    val_between = array_attr.get_value(t=3)
    assert val_between == 10  # Assuming constant interpolation


def test_attribute_serialization_roundtrip():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test complete serialization and deserialization cycle"""
    attrs_to_test = [
        ("value", self.value_attr),
        ("array", self.array_attr),
        ("callable", self.callable_attr),
    ]

    for name, attr in attrs_to_test:
        filename = f"test_{name}.dill"

        # Save original
        attr.save(filename)

        # Load copy
        loaded_attr = DynamicAttribute.load(filename)

        # Verify type preservation
        assert type(loaded_attr) == type(attr)

        # Verify value preservation
        if hasattr(attr, "get_items"):
            assert list(attr.get_items()) == list(loaded_attr.get_items())
        else:
            assert attr.get_value() == loaded_attr.get_value()


def test_callable_attribute_different_functions():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test callable attributes with different mathematical functions"""
    # Linear function
    linear_attr = DynamicCallableAttribute(
        lambda **kw: kw["t"] + 5, total_time=8, delta_t=2
    )
    assert list(linear_attr.get_values()) == [5, 7, 9, 11]

    # Quadratic function
    quad_attr = DynamicCallableAttribute(
        lambda **kw: kw["t"] ** 2, total_time=6, delta_t=2
    )
    assert list(quad_attr.get_values()) == [0, 4, 16]

    # Trigonometric function (using integer approximation)
    trig_attr = DynamicCallableAttribute(
        lambda **kw: int(kw["t"] % 4), total_time=8, delta_t=2
    )
    assert list(trig_attr.get_values()) == [0, 2, 0, 2]


def test_array_attribute_resize_edge_cases():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test array resizing with various parameters"""
    array_attr = DynamicTimeArrayAttribute(value=7, total_time=4, delta_t=1)

    # Test expanding array
    array_attr.resize_attribute(new_total_time=8)
    assert len(array_attr.get_values()) == 8

    # Test shrinking array
    array_attr.resize_attribute(new_total_time=3)
    assert len(array_attr.get_values()) == 3

    # Test changing delta_t
    array_attr.resize_attribute(new_total_time=6, new_delta_t=2)
    assert len(array_attr.get_values()) == 3
    assert array_attr.get_times() == [0, 2, 4]


def test_mixed_attribute_arithmetic_chains():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test complex arithmetic chains with mixed attribute types"""
    value_attr = DynamicValueAttribute(5)
    array_attr = DynamicTimeArrayAttribute(value=3, total_time=4, delta_t=2)
    callable_attr = DynamicCallableAttribute(
        lambda **kw: kw["t"], total_time=4, delta_t=2
    )

    # Complex chain: (value + array) * callable + scalar
    result = (value_attr + array_attr) * callable_attr + 10
    expected_values = [(8 * 0) + 10, (8 * 2) + 10]  # [10, 26]
    assert list(result.get_values()) == expected_values


@pytest.mark.parametrize("operation", ["+", "-", "*", "/"])
def test_attribute_operations_with_scalars(operation):
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test all arithmetic operations with scalar values"""
    array_attr = DynamicTimeArrayAttribute(value=8, total_time=4, delta_t=2)
    scalar = 2

    if operation == "+":
        result = array_attr + scalar
        expected = [10, 10]
    elif operation == "-":
        result = array_attr - scalar
        expected = [6, 6]
    elif operation == "*":
        result = array_attr * scalar
        expected = [16, 16]
    elif operation == "/":
        result = array_attr / scalar
        expected = [4.0, 4.0]

    assert list(result.get_values()) == expected


def test_attribute_error_handling():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test error handling for invalid operations"""
    array_attr = self.array_attr.copy()

    with pytest.raises(Exception):
        # Division by zero should raise an error
        array_attr / 0


def test_large_time_array_operations():
    from m4i.graphs import (
        DynamicValueAttribute,
        DynamicTimeArrayAttribute,
        DynamicCallableAttribute,
        DynamicAttribute,
    )

    self = attribute_tester()  # Test in-place addition
    """Test operations on large time arrays for memory efficiency"""
    large_attr = DynamicTimeArrayAttribute(value=1, total_time=1000, delta_t=1)

    # Test that operations complete in reasonable time and don't consume excessive memory
    start_time = timeit.default_timer()
    large_attr += 1
    duration = timeit.default_timer() - start_time

    assert duration < 0.1  # Should complete quickly
    assert large_attr.get_value(t=500) == 2  # Verify operation worked
