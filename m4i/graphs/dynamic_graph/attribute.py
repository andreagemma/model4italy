from __future__ import annotations
from typing import *
from numbers import Number
from copy import deepcopy
from operator import add, sub, truediv, mul, pow
from numpy import arange
from numpy import array as nparray
from importlib import import_module
import dill

T = TypeVar("T")  # Defines a generic type


class DynamicAttribute(dict, Generic[T]):
    """
    Base class for attributes.

    This class serves as a blueprint for different types of attributes, supporting arithmetic operations,
    value setting, and retrieval operations.
    """

    def __init__(self, **kwargs) -> DynamicAttribute[T]:
        """
        Initialize the attribute with given keyword arguments.

        :param kwargs: Key-value pairs to initialize the attribute.
        """
        super().__init__()
        self.update(kwargs)

    def copy(self) -> DynamicAttribute[T]:
        """
        Create a deep copy of the attribute.

        :return: A deep copy of the attribute.
        """
        return deepcopy(self)

    def __iadd__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        In-place addition operator.

        :param b: Value or another attribute to be added.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def __add__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Addition operator.

        :param b: Value or another attribute to be added.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def __isub__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        In-place subtraction operator.

        :param b: Value or another attribute to be subtracted.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def __sub__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Subtraction operator.

        :param b: Value or another attribute to be subtracted.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def __imul__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        In-place multiplication operator.

        :param b: Value or another attribute to be multiplied.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def __mul__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Multiplication operator.

        :param b: Value or another attribute to be multiplied.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def __itruediv__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        In-place true division operator.

        :param b: Value or another attribute to be divided.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def __truediv__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        True division operator.

        :param b: Value or another attribute to be divided.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def __ipow__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        In-place exponentiation operator.

        :param b: Value or another attribute to be exponentiated.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def __pow__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Exponentiation operator.

        :param b: Value or another attribute to be exponentiated.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def get_value(self, **kwargs) -> T:
        """
        Get the value of the attribute.

        :param t: Time at which to get the value.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def set_value(self, value: T, **kwargs) -> DynamicAttribute[T]:
        """
        Set the value of the attribute.

        :param value: The value to set.
        :param t: Time at which to set the value.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def reset(self, value: T, *args, **kwargs) -> DynamicAttribute[T]:
        """
        Set the value of the attribute to all instances.

        :param value: The value to set.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def resize_attribute(self, new_total_time: Number, new_delta_t: Optional[Number] = None, offset: Number = 0, **kwargs) -> DynamicAttribute[T]:
        """
        Resize the attribute based on new total seconds and optionally a new delta_t.

        :param new_total_time: The new total time duration.
        :param new_delta_t: The new time step (optional).
        """
        pass

    def get_items(self, list_t: Iterable[Number] = None, **kwargs) -> List[Tuple[Number, T]]:
        """
        Get the values of the attribute at specified times.

        :param list_t: Iterable of time points at which values are requested.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def get_times(self, **kwargs) -> List[Number]:
        """
        Get the values of the attribute at specified times.

        :param list_t: Iterable of time points at which values are requested.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def get_values(self, list_t: Optional[Iterable[Number]] = None, **kwargs) -> List[T]:
        """
        Get the values of the attribute at specified times.

        :param list_t: Iterable of time points at which values are requested.
        :raises NotImplementedError: Must be implemented in derived classes.
        """
        raise NotImplementedError()

    def save(self, filename: str):
        """
        Save the attribute to a file.

        :param filename: Filename to save the attribute
        """
        with open(filename, "wb") as f:
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filename: str) -> DynamicAttribute[T]:
        """
        Load an attribute from a file.

        :param filename: Filename to load the attribute from
        :return: Attribute object
        """
        with open(filename, "rb") as f:
            ret = dill.load(f)
        return ret


class DynamicValueAttribute(DynamicAttribute, Generic[T]):
    """
    Attribute for a single value of type T.

    This class represents a constant attribute, providing methods to perform arithmetic
    operations, value setting, and retrieval on the attribute.
    """

    def __init__(self, value: T, **kwargs) -> DynamicValueAttribute[T]:
        """
        Initialize the ValueAttribute with a given value.

        :param value: The value of the attribute.
        :param kwargs: Additional key-value pairs to initialize the attribute.
        """
        super().__init__(type="value", value=value, **kwargs)

    def _apply_inplace_operation(self, b, op) -> None:
        """
        Apply an in-place operation on `self["value"]` based on the type of `b`.

        :param b: The operand to apply the operation with.
        :param op: The operator function (e.g., add, sub).
        """
        if isinstance(b, tuple):
            b, t= b

        if isinstance(b, DynamicValueAttribute):
            dict.__setitem__(self, "value", op(dict.__getitem__(self, "value"), dict.__getitem__(b, "value")))
        elif isinstance(b, DynamicAttribute):
            raise NotImplementedError()
        else:
            dict.__setitem__(self, "value", op(dict.__getitem__(self, "value"), b))

    def __iadd__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicValueAttribute[T]:
        """
        In-place addition operator.

        :param b: The value or attribute to add.
        :return: Updated ValueAttribute after addition.
        """
        self._apply_inplace_operation(b, add)
        return self

    def __isub__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicValueAttribute[T]:
        """
        In-place subtraction operator.

        :param b: The value or attribute to subtract.
        :return: Updated ValueAttribute after subtraction.
        """
        self._apply_inplace_operation(b, sub)
        return self

    def __imul__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicValueAttribute[T]:
        """
        In-place multiplication operator.

        :param b: The value or attribute to multiply.
        :return: Updated ValueAttribute after multiplication.
        """
        self._apply_inplace_operation(b, mul)
        return self

    def __itruediv__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicValueAttribute[T]:
        """
        In-place true division operator.

        :param b: The value or attribute to divide.
        :return: Updated ValueAttribute after division.
        """
        self._apply_inplace_operation(b, truediv)
        return self

    def __ipow__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicValueAttribute[T]:
        """
        In-place exponentiation operator.

        :param b: The value or attribute to exponentiate.
        :return: Updated ValueAttribute after exponentiation.
        """
        self._apply_inplace_operation(b, pow)
        return self

    # Copy-based operators that rely on in-place methods
    def __add__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Addition operator (non in-place).

        :param b: The value or attribute to add.
        :return: New attribute after addition.
        """
        if isinstance(b, (DynamicTimeArrayAttribute, DynamicCallableAttribute)):
            b, self = self, b
        ret = self.copy()
        ret += b
        return ret

    def __sub__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Subtraction operator (non in-place).

        :param b: The value or attribute to subtract.
        :return: New attribute after subtraction.
        """
        if isinstance(b, (DynamicTimeArrayAttribute, DynamicCallableAttribute)):
            b, self = self, b
        ret = self.copy()
        ret -= b
        return ret

    def __mul__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Multiplication operator (non in-place).

        :param b: The value or attribute to multiply.
        :return: New attribute after multiplication.
        """
        if isinstance(b, (DynamicTimeArrayAttribute, DynamicCallableAttribute)):
            b, self = self, b
        ret = self.copy()
        ret *= b
        return ret

    def __truediv__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        True division operator (non in-place).

        :param b: The value or attribute to divide.
        :return: New attribute after division.
        """
        if isinstance(b, (DynamicTimeArrayAttribute, DynamicCallableAttribute)):
            b, self = self, b
        ret = self.copy()
        ret /= b
        return ret

    def __pow__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Exponentiation operator (non in-place).

        :param b: The value or attribute to exponentiate.
        :return: New attribute after exponentiation.
        """
        if isinstance(b, (DynamicTimeArrayAttribute, DynamicCallableAttribute)):
            b, self = self, b
        ret = self.copy()
        ret **= b
        return ret

    def get_value(self, *args, **kwargs) -> T:
        """
        Get the value of type T.

        :return: The value of the attribute.
        """
        default = kwargs.get("default")
        value = dict.__getitem__(self, "value")
        return value if value is not None else default

    def set_value(self, value: T, *args, **kwargs) -> DynamicValueAttribute[T]:
        """
        Set the value of the attribute.

        :param value: The value to set.
        :return: The updated ValueAttribute.
        """
        dict.__setitem__(self, "value", value)
        return self
        

    def reset(self, value: T, *args, **kwargs) -> DynamicValueAttribute[T]:
        """
        Set a constant value for all.

        :param value: The value to set.
        :return: The updated ValueAttribute.
        """
        dict.__setitem__(self, "value", value)
        return self

    def get_values(self, list_t: Optional[Iterable[Number]] = None, **kwargs) -> List[T]:
        """
        Generate a list of values associated with time points.

        :param list_t: Iterable of time points.
        :return: A generator of time-value pairs.
        """
        if list_t is None:
            list_t = [0]
        ret = []
        for t in list_t:
            ret.append(dict.__getitem__(self, "value"))
        return ret

    def get_times(self, **kwargs) -> List[Number]:
        """
        Generate a list of values associated with time points.

        :return: A list of time values.
        """
        return [0]

    def get_items(self, list_t: Optional[Iterable[Number]] = None, **kwargs) -> List[Tuple[Number, T]]:
        """
        Generate a list of values associated with time points.

        :param list_t: Iterable of time points.
        :return: A generator of time-value pairs.
        """
        if list_t is None:
            list_t = [0]
        ret = []
        for t in list_t:
            ret.append((t, dict.__getitem__(self, "value")))
        return ret


class DynamicTimeArrayAttribute(DynamicAttribute, Generic[T]):
    """
    Attribute for a time-based array.

    This class represents attributes that vary over time, defined as an array of values
    at different time intervals.
    """

    def __init__(
        self,
        value: Union[Callable, List[T], T],
        total_time: Number = 1,
        delta_t: Number = 1,
        **kwargs,
    ) -> DynamicTimeArrayAttribute[T]:
        """
        Initialize the TimeArrayAttribute with a given value, total time, and time step.

        :param value: The initial value, which can be a callable, list, or scalar.
        :param total_time: The total duration of time for the attribute.
        :param delta_t: The time step between values.
        :param kwargs: Additional key-value pairs to initialize the attribute.
        """

        num_intervals = total_time // delta_t

        super().__init__(type="array", value=value, total_time=total_time, delta_t=delta_t, num_intervals=num_intervals, **kwargs)

        if callable(value):  # If value is a function, generate values for each interval
            dict.__setitem__(self, "value", [value(i) for i in range(num_intervals)])
        elif isinstance(value, Iterable):  # If value is iterable, adjust its length to num_intervals
            value = list(value)
            if num_intervals > len(value):
                value.extend([value[-1]] * (num_intervals - len(value)))
            else:
                value = value[:num_intervals]
            dict.__setitem__(self, "value", value)
        else:  # If value is a scalar, fill the intervals with the same value
            dict.__setitem__(self, "value", [value] * num_intervals)

    def _apply_inplace_operation(self, b, operation) -> None:
        """
        Apply an in-place operation to `self["value"]` based on the type of `b`.

        :param b: Operand for the operation (scalar, attribute, or callable).
        :param operation: The operation function (e.g., add, sub).
        """
        t = None
        if isinstance(b, tuple):
            b, t= b

        values = dict.__getitem__(self, "value")
        num_intervals = dict.__getitem__(self, "num_intervals")
        delta_t = dict.__getitem__(self, "delta_t")

        if isinstance(b, DynamicTimeArrayAttribute) and dict.__getitem__(b, "num_intervals") == num_intervals and dict.__getitem__(b, "delta_t") == delta_t:
            # If b is a TimeArrayAttribute, apply the operation to corresponding elements
            operand = dict.__getitem__(b, "value")
            if t is None:
                for index in range(num_intervals):
                    values[index] = operation(values[index], operand[index])
            else:
                index = int(t // dict.__getitem__(self, "delta_t"))
                values[index] = operation(values[index], operand[index])
        elif isinstance(b, DynamicAttribute):
            # If b is an Attribute, generate operand values dynamically based on time
            if t is None:
                for index in range(num_intervals):
                    operand = b.get_value(t=index * delta_t)
                    values[index] = operation(values[index], operand)
            else:
                index = int(t // dict.__getitem__(self, "delta_t"))
                operand = b.get_value(t=index * delta_t)
                values[index] = operation(values[index], operand)
        else:
            # If b is a scalar, apply it to each interval
            if t is None:
                for index in range(num_intervals):
                    values[index] = operation(values[index], b)
            else:
                index = int(t // dict.__getitem__(self, "delta_t"))
                values[index] = operation(values[index], b)

    # In-place addition
    def __iadd__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicTimeArrayAttribute[T]:
        """
        In-place addition operator.

        :param b: The value or attribute to add.
        :return: Updated TimeArrayAttribute after addition.
        """
        self._apply_inplace_operation(b, add)
        return self

    # Addition
    def __add__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Addition operator (non in-place).

        :param b: The value or attribute to add.
        :return: New attribute after addition.
        """
        ret = self.copy()
        ret += b
        return ret

    # In-place subtraction
    def __isub__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicTimeArrayAttribute[T]:
        """
        In-place subtraction operator.

        :param b: The value or attribute to subtract.
        :return: Updated TimeArrayAttribute after subtraction.
        """
        self._apply_inplace_operation(b, sub)
        return self

    # Subtraction
    def __sub__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Subtraction operator (non in-place).

        :param b: The value or attribute to subtract.
        :return: New attribute after subtraction.
        """
        ret = self.copy()
        ret -= b
        return ret

    # In-place multiplication
    def __imul__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicTimeArrayAttribute[T]:
        """
        In-place multiplication operator.

        :param b: The value or attribute to multiply.
        :return: Updated TimeArrayAttribute after multiplication.
        """
        self._apply_inplace_operation(b, mul)
        return self

    # Multiplication
    def __mul__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Multiplication operator (non in-place).

        :param b: The value or attribute to multiply.
        :return: New attribute after multiplication.
        """
        ret = self.copy()
        ret *= b
        return ret

    # In-place division
    def __itruediv__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicTimeArrayAttribute[T]:
        """
        In-place true division operator.

        :param b: The value or attribute to divide.
        :return: Updated TimeArrayAttribute after division.
        """
        self._apply_inplace_operation(b, truediv)
        return self

    # Division
    def __truediv__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        True division operator (non in-place).

        :param b: The value or attribute to divide.
        :return: New attribute after division.
        """
        ret = self.copy()
        ret /= b
        return ret

    # In-place exponentiation
    def __ipow__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicTimeArrayAttribute[T]:
        """
        In-place exponentiation operator.

        :param b: The value or attribute to exponentiate.
        :return: Updated TimeArrayAttribute after exponentiation.
        """
        self._apply_inplace_operation(b, pow)
        return self

    def __pow__(self, b: Union[T, DynamicAttribute[T]]) -> DynamicAttribute[T]:
        """
        Exponentiation operator (non in-place).

        :param b: The value or attribute to exponentiate.
        :return: New attribute after exponentiation.
        """
        ret = self.copy()
        ret **= b
        return ret

    def get_value(self, t: Number = 0, **kwargs) -> T:
        """
        Get the value at a specific time.

        :param t: Time at which to get the value.
        :param default: Default value if time is out of bounds.
        :return: The value at the given time.
        """
        index = int(t // dict.__getitem__(self, "delta_t"))
        values = dict.__getitem__(self, "value")
        if index < len(values):
            return values[index]
        elif len(values) == 0:
            return kwargs.get("default",0)
        else:
            return values[-1]

    def set_value(self, value: T, t: Number = 0, **kwargs) -> DynamicTimeArrayAttribute[T]:
        """
        Set a value at a specific time.

        :param value: The value to set.
        :param t: Time at which to set the value.
        :return: The updated TimeArrayAttribute.
        """
        index = int(t // dict.__getitem__(self, "delta_t"))
        values = dict.__getitem__(self, "value")
        if index < len(values):
            values[index] = value
        elif len(values) == 0:
            values.extend([None] * (index - len(values)))
            values.append(value)
            dict.__setitem__(self, "total_time", (index + 1) * dict.__getitem__(self, "delta_t"))
        else:
            values.extend([values[-1]] * (index - len(values)))
            values.append(value)
            dict.__setitem__(self, "total_time", (index + 1) * dict.__getitem__(self, "delta_t"))
        return self

    def reset(self, value: Any, **kwargs) -> DynamicTimeArrayAttribute[T]:
        """
        Set a value for all time intervals.

        :param value: The value to set for all intervals.
        :return: The updated TimeArrayAttribute.
        """
        values = dict.__getitem__(self, "value")
        if isinstance(value, Iterable):
            for i, v in enumerate(value):
                values[i] = v
        else:
            for i in range(len(values)):
                values[i] = value
        return self

    def resize_attribute(self, new_total_time: Optional[Number] = None, new_delta_t: Optional[Number] = None, offset: Number=0, **kwargs) -> DynamicTimeArrayAttribute[T]:
        """
        Resize the attribute based on new total time and optionally a new delta_t.

        :param new_total_time: The new total time duration.
        :param new_delta_t: The new time step (optional).
        :return: The updated TimeArrayAttribute.
        """
        if new_delta_t is None:
            new_delta_t = dict.__getitem__(self, "delta_t")

        if new_total_time is None:
            new_total_time = dict.__getitem__(self, "total_time")

        if new_delta_t != dict.__getitem__(self, "delta_t") or new_total_time != dict.__getitem__(self, "total_time"):
            dict.__setitem__(
                self,
                "value",
                [self.get_value(t=t, default=0) for t in arange(offset, new_total_time+offset, new_delta_t)],
            )
        dict.__setitem__(self, "delta_t", new_delta_t)
        dict.__setitem__(self, "total_time", new_total_time)
        dict.__setitem__(self, "num_intervals", len(dict.__getitem__(self, "value")))
        return self

    def get_values(self, list_t: Optional[Iterable[Number]] = None, **kwargs) -> List[T]:
        """
        Generate a list of values associated with time points.

        :param list_t: Iterable of time points.
        :return: A generator of time-value pairs.
        """
        if list_t is None:
            return list(dict.__getitem__(self, "value").copy())
        else:
            ret = []
            for t in list_t:
                ret.append(self.get_value(t, **kwargs))
            return ret

    def get_times(self, **kwargs) -> List[Number]:
        """
        Generate a list of values associated with time points.

        :return: A list of time values.
        """
        num_intervals = dict.__getitem__(self, "num_intervals")
        delta_t = dict.__getitem__(self, "delta_t")
        ret = []
        for i in range(num_intervals):
            ret.append(i * delta_t)
        return ret

    def get_items(self, list_t: Optional[Iterable[Number]] = None, **kwargs) -> List[Tuple[Number, T]]:
        """
        Get the values of the attribute at specified time points.

        :param list_t: Iterable of time points.
        :return: A generator yielding time-value pairs.
        """
        values = dict.__getitem__(self, "value")
        ret = []
        if list_t is None:
            delta_t = dict.__getitem__(self, "delta_t")
            for i, v in enumerate(values):
                ret.append((i * delta_t, v))
        else:
            for t in list_t:
                ret.append((t, self.get_value(t, **kwargs)))
        return ret




class DynamicCallableAttribute(DynamicAttribute, Generic[T]):
    """
    Attribute for callable functions.

    This class represents an attribute defined as a callable function, allowing operations
    such as arithmetic between callables and other types of attributes.
    """

    def __init__(self, value: Union[str, Callable[..., T]], total_time: Number = 1, delta_t: Number = 1, **kwargs) -> DynamicCallableAttribute[T]:
        """
        Initialize the CallableAttribute with a callable function or reference.

        :param value: A callable or a string reference to a callable function.
        :param total_time: The total time for which the callable is defined.
        :param delta_t: The time step.
        :param kwargs: Additional arguments for the attribute.
        """        
        num_intervals = total_time // delta_t
        fn: Callable = None
        if callable(value):
            fn = value
        elif isinstance(value, str):
            try:
                module_name, fn_name = value.split(":")
            except ValueError:
                raise ValueError(f"Invalid value '{value}'. Expected 'module:function_name', e.g., function.vdf:bpr to use bpr function in function.vdf module")
            module = import_module(module_name)
            fn = getattr(module, fn_name)

        super().__init__(type="callable", value=value, total_time=total_time, delta_t=delta_t, num_intervals=num_intervals, fn=fn, **kwargs)

    def _apply_inplace_operation(self, b, op):
        """
        Apply an in-place operation on the function with either an Attribute or a scalar.

        :param b: Operand for the operation.
        :param op: Operation to apply.
        """
        t = None
        if isinstance(b, tuple):
            b, t= b        
        fn = dict.__getitem__(self, "fn")
        if isinstance(b, DynamicCallableAttribute):
            b = b.copy()
            fnb = dict.__getitem__(b, "fn")            
            if t is None:
                dict.__setitem__(self, "fn", lambda **kw: op(fn(**kw), fnb(**kw)))
            else:
                dict.__setitem__(self, "fn", lambda **kw: fn(**kw) if kw["t"] != t else op(fn(**kw), fnb(**kw)))
        elif isinstance(b, DynamicAttribute):
            b = b.copy()
            if t is None:
                dict.__setitem__(self, "fn", lambda **kw: op(fn(**kw), b.get_value(**kw)))
            else:
                dict.__setitem__(self, "fn", lambda **kw: fn(**kw) if kw["t"] != t else op(fn(**kw), b.get_value(**kw)))
        elif isinstance(b, Callable):
            b = b.copy()
            if t is None:
                dict.__setitem__(self, "fn", lambda **kw: op(fn(**kw), b(**kw)))
            else:
                dict.__setitem__(self, "fn", lambda **kw: fn(**kw) if kw["t"] != t else op(fn(**kw), b(**kw)))
        else:
            if t is None:
                dict.__setitem__(self, "fn", lambda **kw: op(fn(**kw), b))
            else:
                dict.__setitem__(self, "fn", lambda **kw: fn(**kw) if kw["t"] != t else op(fn(**kw), b))

    # In-place operators
    def __iadd__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        In-place addition operator.

        :param b: Value, attribute, or callable to add.
        :return: Updated CallableAttribute after addition.
        """
        self._apply_inplace_operation(b, add)
        return self

    def __isub__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        In-place subtraction operator.

        :param b: Value, attribute, or callable to subtract.
        :return: Updated CallableAttribute after subtraction.
        """
        self._apply_inplace_operation(b, sub)
        return self

    def __imul__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        In-place multiplication operator.

        :param b: Value, attribute, or callable to multiply.
        :return: Updated CallableAttribute after multiplication.
        """
        self._apply_inplace_operation(b, mul)
        return self

    def __itruediv__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        In-place true division operator.

        :param b: Value, attribute, or callable to divide.
        :return: Updated CallableAttribute after division.
        """
        self._apply_inplace_operation(b, truediv)
        return self

    def __ipow__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        In-place exponentiation operator.

        :param b: Value, attribute, or callable to exponentiate.
        :return: Updated CallableAttribute after exponentiation.
        """
        self._apply_inplace_operation(b, pow)
        return self

    # Copy-based operators that use the in-place methods
    def __add__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        Addition operator (non in-place).

        :param b: Value, attribute, or callable to add.
        :return: New CallableAttribute after addition.
        """
        ret = self.copy()
        ret += b
        return ret

    def __sub__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        Subtraction operator (non in-place).

        :param b: Value, attribute, or callable to subtract.
        :return: New CallableAttribute after subtraction.
        """
        ret = self.copy()
        ret -= b
        return ret

    def __mul__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        Multiplication operator (non in-place).

        :param b: Value, attribute, or callable to multiply.
        :return: New CallableAttribute after multiplication.
        """
        ret = self.copy()
        ret *= b
        return ret

    def __truediv__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        True division operator (non in-place).

        :param b: Value, attribute, or callable to divide.
        :return: New CallableAttribute after division.
        """
        ret = self.copy()
        ret /= b
        return ret

    def __pow__(self, b: Union[T, DynamicAttribute, Callable[..., T]]) -> DynamicCallableAttribute[T]:
        """
        Exponentiation operator (non in-place).

        :param b: Value, attribute, or callable to exponentiate.
        :return: New CallableAttribute after exponentiation.
        """
        ret = self.copy()
        ret **= b
        return ret

    def get_value(self, t: Number = 0, **kwargs) -> T:
        """
        Get the value of the callable at a specific time.

        :param t: Time at which to get the value.
        :param default: Default value if the callable returns None.
        :return: The value at the given time.
        """
        kwargs["t"] = t
        kwargs["attr"] = self
        ret = dict.__getitem__(self, "fn")(**kwargs)
        return ret if ret is not None else kwargs.get("default",0)

    def set_value(self, value: T, t: Number = 0, **kwargs) -> DynamicCallableAttribute[T]:
        """
        Set the value of the callable at a specific time.

        :param value: The value to set.
        :param t: Time at which to set the value.
        :return: The updated CallableAttribute.
        """
        fn = dict.__getitem__(self, "fn")
        dict.__setitem__(self, "fn", lambda **kw: (value if t == kw["t"] else fn(**kw)))
        return self

    def resize_attribute(self, new_total_time: Number, new_delta_t: Optional[Number] = None, offset: Number = 0, **kwargs) -> DynamicCallableAttribute[T]:
        """
        Resize the callable attribute for a new total time and optionally a new delta_t.

        :param new_total_time: The new total time duration.
        :param new_delta_t: The new time step (optional).
        :return: The updated CallableAttribute.
        """
        if new_delta_t is not None:
            dict.__setitem__(self, "delta_t", new_delta_t)
        dict.__setitem__(self, "num_intervals", new_total_time // dict.__getitem__(self, "delta_t"))
        dict.__setitem__(self, "total_time", new_total_time)
        return self

    def get_values(self, list_t: Optional[Iterable[Number]] = None, **kwargs) -> List[T]:
        """
        Get the values of the callable attribute at specified time points.

        :param list_t: Iterable of time points.
        :return: A generator yielding time-value pairs.
        """
        num_intervals = dict.__getitem__(self, "num_intervals")
        delta_t = dict.__getitem__(self, "delta_t")
        ret = []
        if list_t is None:
            list_t = [i * delta_t for i in range(num_intervals)]
        for t in list_t:
            ret.append(self.get_value(t, **kwargs))
        return ret

    def get_times(self, **kwargs) -> List[T]:
        """
        Get the values of the callable attribute at specified time points.

        :param list_t: Iterable of time points.
        :return: A generator yielding time-value pairs.
        """
        num_intervals = dict.__getitem__(self, "num_intervals")
        delta_t = dict.__getitem__(self, "delta_t")
        return [i * delta_t for i in range(num_intervals)]

    def get_items(self, list_t: Optional[Iterable[Number]] = None, **kwargs) -> List[Tuple[Number, T]]:
        """
        Get the values of the callable attribute at specified time points.

        :param list_t: Iterable of time points.
        :return: A generator yielding time-value pairs.
        """
        num_intervals = dict.__getitem__(self, "num_intervals")
        delta_t = dict.__getitem__(self, "delta_t")
        ret = []
        if list_t is None:
            list_t = [i * delta_t for i in range(num_intervals)]
        for t in list_t:
            ret.append((t, self.get_value(t, **kwargs)))
        return ret
