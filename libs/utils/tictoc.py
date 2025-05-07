from __future__ import annotations

import logging
from typing import Union, Optional, Dict, Callable
import time
from math import floor
from math import log
from time import localtime
from time import strftime
from time import time
import string
from itertools import product
from libs.utils.util import serialize
"""
Di seguito sono descritte una serie di classi per monitotare il tempo di esecuzione degli script.

TicTocTime: memorizza l'istante temporale e fornisce i comandi base per convertire l'istante in minuti, ore e secondi e stringa
TicTocSpeed: memorizza la velocità in esecuzioni al secondo e fornisce i comandi base per convertire la velocita in #/minuto, #/ora e #/secondo
TicTocInterval: memorizza un intervallo temporale per convertire la velocita in #/minuto, #/ora e #/secondo

TicToc è la classe principale che fornisce i metodi per monitorare i tempi di esecuzione
"""

class TicTocTime:

    def __init__(self, t: Union[int,float], dt_format: str = "%Y-%m-%d %H:%M:%S"):
        """
        The above function is a constructor that initializes the instance variables `t` and `dt_format`.
        
        :param t: The parameter "t" represents the epoch of time instant 
        :type t: Union[int,float]
        :param dt_format: The parameter "dt_format" represents the datetime format to print "t"
        :type dt_format: str
        """
        self.t: Union[int,float] = t
        self.dt_format: str = dt_format

    def __int__(self) -> int:
        """
        Return the epoch as integer
        :return: epoch as integer
        :rtype: int
        """
        return int(self.t)

    def __float__(self) -> float:
        """
        Return the epoch as float
        :return: epoch as float
        :rtype: float
        """
        return float(self.t)

    @property
    def to_s(self) -> Union[int,float]:
        """
        Return the number of seconds
        :return: seconds
        :rtype: Union[int,float]
        """        
        try:
            return self.t
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    @property
    def to_m(self) -> Union[int,float]:
        """
        Return the number of minutes
        :return: minutes
        :rtype: Union[int,float]
        """        
        try:
            return self.t * 60
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None
        
    @property
    def to_h(self) -> Union[int,float]:
        """
        Return the number of hours
        :return: hours
        :rtype: Union[int,float]
        """        
        try:
            return self.t * 3600
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None
  
    @property
    def to_d(self) -> Union[int,float]:
        """
        Return the number of days
        :return: days
        :rtype: Union[int,float]
        """        
        try:
            return self.t * 86400
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None
                      
    @property
    def to_str(self) -> str:
        """
        Return the epoch as datetime string
        :return: datetime string
        :rtype: str
        """        
        try:
            return strftime(self.dt_format, localtime(self.t))
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None


class TicTocSpeed:
    """ Store the speed in # per seconds"""
    def __init__(self, v: Union[int, float, TicTocInterval]):
        if v is None:
            raise ValueError("v is None")
        if isinstance(v, TicTocInterval):
            self.v: Union[int,float] = v.sec
        else:
            self.v: Union[int,float] = v

    @property
    def to_str(self) -> str:
        """
        Convert the speed in string
        """
        return str(self.v)

    @property
    def to_s(self) -> Union[int,float]:
        """
        Convert the speed in # per second
        """
        try:
            return self.v
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    @property
    def to_m(self) -> Union[int,float]:
        """
        Convert the speed in # per minute
        """
        try:
            return self.v * 60
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    @property
    def to_h(self) -> Union[int,float]:
        """
        Convert the speed in # per hour
        """
        
        try:
            return self.v * 3600
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    @property
    def to_d(self) -> Union[int,float]:
        """
        Convert the speed in # per day
        """        
        try:
            return self.v * 86400
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    def __int__(self) -> int:
        """
        Convert the speed in an integer
        """        
        return int(self.to_h)

    def __float__(self) -> float:
        """
        Convert the speed in a float
        """        
        return float(self.to_h)

    def __str__(self) -> str:
        """
        Convert the speed in a string
        """               
        return str(self.v)


class TicTocInterval:

    def __init__(self, sec: Union[int, float]):
        self.sec: Union[int, float] = sec

    @property
    def to_str(self) -> str:
        """
        The function `to_str` converts a given epoch time in seconds to a formatted string representation.        
        :return: The method returns a formatted string representation of interval.
        """  
        return TicTocInterval.__s2str(self.sec)

    @staticmethod
    def __s2str(epoch: Union[int,float]) -> str:
        """
        The function `__s2str` converts a given epoch time in seconds to a formatted string representation.
        
        :param epoch: The parameter "epoch" represents a time duration in seconds
        :type epoch: Union[int,float]
        :return: The method returns a formatted string representation of the input epoch time.
        """        
        try:
            sec = str(floor(epoch % 60)).zfill(2)
            m = str(floor((epoch % 3600) / 60)).zfill(2)
            h = str(floor((epoch % 86400) / 3600)).zfill(2)
            g = floor(epoch / 86400)
            if epoch < 0.001:
                return "%.6f s" % epoch
            elif epoch < 0.01:
                return "%.5f s" % epoch
            elif epoch < 0.1:
                return "%.4f s" % epoch
            elif epoch < 1:
                return "%.3f s" % epoch
            elif epoch < 10:
                return "%.2f s" % epoch
            elif epoch < 60:
                return "%.1f s" % epoch
            elif epoch < 3600:
                return "00:%s:%s" % (m, sec)
            elif epoch < 86400:
                return "%s:%s:%s" % (h, m, sec)
            else:
                return "%s.%s:%s:%s" % (g, h, m, sec)
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    def __int__(self) -> int:
        """
        Return the interval as int
        :return: interval as int
        :rtype: int
        """
        return int(self.sec)

    def __float__(self) -> float:
        """
        Return the interval as float
        :return: interval as float
        :rtype: float
        """        
        return float(self.sec)

    def __str__(self) -> str:
        return TicTocInterval.__s2str(self.sec)

    def __override(self, other, opname, create_new=True) -> TicTocInterval:
        try:
            if create_new:
                ret = TicTocInterval(self.sec)
            else:
                ret = self
            if isinstance(other, (int, float)):
                ret.sec = getattr(float, opname)(self.sec, other)
                return ret
            elif isinstance(other, self.__class__):
                ret.sec = getattr(float, opname)(self.sec, other.sec)
                return ret
            else:
                try:
                    ret.sec = getattr(float, opname)(self.sec, float(other))
                    return ret
                except:
                    raise NotImplementedError()
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    def __add__(self, other):
        return self.__override(other, '__add__')

    def __sub__(self, other):
        return self.__override(other, '__sub__')

    def __mul__(self, other):
        return self.__override(other, '__mul__')

    def __truediv__(self, other):
        return self.__override(other, '__truediv__')

    def __radd__(self, other):
        return self.__override(other, '__radd__')

    def __rsub__(self, other):
        return self.__override(other, '__rsub__')

    def __rmul__(self, other):
        return self.__override(other, '__rmul__')

    def __rtruediv__(self, other):
        return self.__override(other, '__rtruediv__')

    def __iadd__(self, other):
        return self.__override(other, '__add__', False)

    def __isub__(self, other):
        return self.__override(other, '__sub__', False)

    def __imul__(self, other):
        return self.__override(other, '__mul__', False)

    def __itruediv__(self, other):
        return self.__override(other, '__truediv__', False)

    @property
    def to_s(self) -> Union[int, float]:
        """
        Return the seconds of interval
        :return: seconds
        :rtype: Union[int, float]
        """                   
        try:
            return self.sec
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    @property
    def to_m(self) -> Union[int,float]:
        """
        Return the minutes of interval
        :return: minutes
        :rtype: Union[int, float]
        """          
        try:
            return self.sec / 60
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    @property
    def to_h(self) -> Union[int,float]:
        """
        Return the hours of interval
        :return: hours
        :rtype: Union[int, float]
        """          
        try:
            return self.sec / 3600
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

    @property
    def to_d(self) -> Union[int,float]:
        """
        Return the days of interval
        :return: days
        :rtype: Union[int, float]
        """          
        try:
            return self.sec / 86400
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return None

# The `TicToc` class is a timer utility that allows for measuring elapsed time, calculating remaining
# time, and displaying information about the timer progress.
class TicToc:

    def __init__(self, t: Optional[Union[int, float]] = None, logger=None):
        """
        This is a Python class that initializes various attributes and aliases for time-related
        calculations and logging.
        
        :param t: The parameter `t` is a time value that represents the starting time for the timer. It
        can be either an integer or a float. If no value is provided for `t`, the current time will be
        used as the starting time
        :type t: Optional[Union[int, float]]
        :param logger: The `logger` parameter is an optional parameter that allows you to pass a custom
        logger object. If no logger object is provided, it will use the default logger from the
        `logging` module
        """
        self._formatter = string.Formatter()

        self._t_origin: Union[int, float] = time() if t is None else t
        self._t: Union[int, float] = self._t_origin
        self._t_named: Dict[str, Union[int, float]] = {}
        self.counter: Optional[Union[int, float]] = None
        self.tot: Optional[Union[int, float]] = None

        # alias
        self.et = self.elapsed_time
        self.eot = self.elapsed_origin_time
        self.rt = self.remaining_time
        self.tt = self.total_time

        self.v = self.speed
        self.end = self.end_time
        self.start = self.start_time
        self.origin = self.origin_time

        self.info_format: str = "analyzed {counter} in {elapsed_time} - S: {start_time} - V: {speed:.0f} rec/h"
        self.info_tot_format: str = "analyzed {counter}/{tot} in {elapsed_time} - S: {start_time} - E: {end_time} - ETA: {remaining_time} - V: {speed.0f} rec/h"

        self.log = logging.getLogger() if logger is None else logger

    def get(self, t=None)->TicToc:
        ret = TicToc(t, logger=self.log)
        return ret
    
    def tic(self, name=None) -> Union[int, float]:
        """
        The function `tic` is a method that records the current time and returns it, or stores the time
        under a given name and returns it. If an error occurs, it logs the error and returns -1.
        
        :param name: The `name` parameter is an optional string that represents the name of the tic. If
        provided, it will store the current time in the `_t_named` dictionary with the given name as the
        key. If not provided, it will store the current time in the `_t` variable
        :return: either the current time as an integer or float value, or -1 if an error occurs.
        """
        try:
            if name is not None:
                self._t_named[name] = time()
                return self._t_named[name]
            else:
                self._t = time()
                return self._t
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return -1

    def __int__(self) -> int:
        return self._t

    def __float__(self) -> float:
        return self._t

    def __lt__(self, other: TicToc) -> bool:
        return self._t < other._t

    def __gt__(self, other: TicToc) -> bool:
        return self._t > other._t

    def __le__(self, other: TicToc) -> bool:
        return self._t <= other._t

    def __ge__(self, other: TicToc) -> bool:
        return self._t >= other._t

    def __add__(self, other) -> None:
        try:
            if isinstance(other, TicToc):  # aggiunge il tempo di other
                self._t -= other.et()
                for k in self._t_named.keys():
                    if k in other._t_named.items():
                        self._t_named[k] -= other.et(name=k)
            elif isinstance(other, (int, float)):
                self._t -= other
                for k in self._t_named.keys():
                    self._t_named[k] -= other
            else:
                raise NotImplementedError()
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)

    def elapsed_time(self, t: Union[int, float] = None, name=None) -> TicTocInterval:
        """
        The `elapsed_time` function calculates the elapsed time between the current time and a previous time
        point, either specified as an argument or stored as a named time point.
        
        :param t: The parameter `t` is an optional argument that represents a time value. It can be either
        an integer or a float
        :type t: Union[int, float]
        :param name: The `name` parameter is an optional string that represents the name of a specific
        interval. If provided, the elapsed time will be calculated between the current time and the time
        recorded for that specific interval
        :return: The function `elapsed_time` returns a `TicTocInterval` object.
        """
        try:
            if t is not None:
                return TicTocInterval(t - self._t)
            elif name is not None:
                return TicTocInterval(self._t_named[name] - self._t)
            else:
                return TicTocInterval(time() - self._t)
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return TicTocInterval(0)

    def elapsed_origin_time(self) -> TicTocInterval:
        """
        The function calculates the elapsed time since a specified origin time and returns it as a
        TicTocInterval object.
        :return: a TicTocInterval object.
        """
        try:
            return TicTocInterval(time() - self._t_origin)
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return TicTocInterval(0)

    def remaining_time(self, i: Optional[Union[int, float]] = None, tot: Optional[Union[int, float]] = None) -> TicTocInterval:
        """
        The `remaining_time` function calculates the estimated remaining time based on the current iteration
        and total iterations.
        
        :param i: The parameter `i` represents the current iteration or progress. It can be an integer or a
        float value. If not provided, it defaults to the value of `self.counter`
        :type i: Optional[Union[int, float]]
        :param tot: The parameter "tot" represents the total number of iterations or tasks that need to be
        completed
        :type tot: Optional[Union[int, float]]
        :return: a `TicTocInterval` object.
        """
        try:
            i = self.counter if i is None else i
            tot = self.tot if tot is None else tot
            if i is None or i == 0 or tot is None or tot == 0:
                return TicTocInterval(0)
            else:
                return TicTocInterval(self.et().to_s * (tot / i - 1))
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return TicTocInterval(0)

    def total_time(self, i: Optional[Union[int, float]] = None, tot: Optional[Union[int, float]] = None) -> TicTocInterval:
        """
        The `total_time` function calculates the total time based on the current counter value and the total
        value.
        
        :param i: The parameter `i` represents the current counter value. It is an optional parameter that
        can be either an integer or a float. If it is not provided, the value of `self.counter` will be used
        instead
        :type i: Optional[Union[int, float]]
        :param tot: The parameter "tot" represents the total number of iterations or total count. It is used
        to calculate the total time taken for the given number of iterations
        :type tot: Optional[Union[int, float]]
        :return: a `TicTocInterval` object.
        """
        try:
            i = self.counter if i is None else i
            tot = self.tot if tot is None else tot
            if i is None or i == 0 or tot is None or tot == 0:
                return TicTocInterval(0)
            else:
                return TicTocInterval(self.et().to_s * tot / i)
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return TicTocInterval(0)

    def speed(self, i: Optional[Union[int, float]] = None) -> TicTocSpeed:
        """
        The `speed` function calculates the speed of a process based on the counter and elapsed time, and
        returns a `TicTocSpeed` object.
        
        :param i: The parameter `i` is an optional argument that can be either an integer or a float. It
        represents the value to be used for calculating the speed. If `i` is not provided, it defaults to
        `None`
        :type i: Optional[Union[int, float]]
        :return: an instance of the `TicTocSpeed` class.
        """
        try:
            i = self.counter if i is None else i
            return TicTocSpeed(i / self.et())
        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
            return TicTocSpeed(0)

    def end_time(self, i: Optional[Union[int, float]] = None, tot=None) -> TicTocTime:
        """
        The `end_time` function returns the end time of a task by adding the total time to the start time.
        
        :param i: The parameter `i` is an optional argument that can be either an integer or a float. It is
        used to specify the number of iterations or steps that have been completed. If `i` is not provided,
        it defaults to `None`
        :type i: Optional[Union[int, float]]
        :param tot: The `tot` parameter is an optional argument that represents the total time in seconds.
        It is used in the `total_time` method to calculate the total time elapsed since the start of the
        timer. If `tot` is not provided, it defaults to `None`
        :return: an instance of the `TicTocTime` class.
        """
        return TicTocTime(self._t + self.total_time(i, tot).to_s)

    def start_time(self) -> TicTocTime:
        """
        The `start_time` function returns a `TicTocTime` object with the last stored time.
        :return: The method `start_time` is returning an instance of the `TicTocTime` class, initialized
        with the value of `self._t`.
        """
        return TicTocTime(self._t)

    def origin_time(self) -> TicTocTime:
        """
        The `origin_time` function returns a `TicTocTime` object representing the origin time.
        :return: The method `origin_time` is returning an instance of the `TicTocTime` class, initialized
        with the value of the `_t_origin` attribute.
        """
        return TicTocTime(self._t_origin)

    def info(self,iformat=None, counter: Optional[Union[int, float]] = None, tot: Optional[Union[int, float]] = None,                     
             dt_format="%Y-%m-%d %H:%M:%S",
             logger: logging.Logger = None,
             n_rows=None,
             **kwargs) -> TicToc:
        """
        The `info` function logs information about the progress of a task, including the counter, total,
        elapsed time, speed, remaining time, and other optional parameters.
        
        :param counter: The `counter` parameter is used to track the progress of a task. It can be an
        integer or a float
        :type counter: Optional[Union[int, float]]
        :param tot: The `tot` parameter represents the total number of iterations or items that you are
        processing. It is used to calculate the progress percentage and estimate the remaining time
        :type tot: Optional[Union[int, float]]
        :param iformat: The `iformat` parameter is used to specify the format of the information message
        that will be logged. It is a string that can contain placeholders for various values such as the
        counter, total, elapsed time, speed, etc. These placeholders will be replaced with their
        corresponding values when the message is logged
        all placeholder that you ca use in messages iformat
            counter, i
            tot
            elapsed_time*, et* with * as _s,_m,_h,_d,_str
            elapsed_origin_time*, eot* with * as _s,_m,_h,_d,_str
            speed*, v* with * as _s,_m,_h,_d,_str
            remaining_time*, rt* with * as _s,_m,_h,_d,_str
            total_time*, tt* with * as _s,_m,_h,_d,_str
            end_time*, end* with * as _str
            start_time*, start* with * as _str
            origin_time*, origin* with * as _str
            and all other kwargs defined        
        :param dt_format: The `dt_format` parameter is used to specify the format of the datetime values
        that will be displayed in the log messages. By default, it is set to "%Y-%m-%d %H:%M:%S", which
        represents the format "YYYY-MM-DD HH:MM:SS", defaults to %Y-%m-%d %H:%M:%S (optional)
        :param logger: The `logger` parameter is an optional parameter of type `logging.Logger`. It
        allows you to specify a custom logger object to use for logging the information. If no logger is
        provided, the method will use the default logger object `self.log`
        :type logger: logging.Logger
        :param n_rows: The parameter `n_rows` is used to specify the number of rows after which the
        information should be logged. If `n_rows` is `None` or the current counter value is divisible by
        `n_rows`, the information will be logged
        :return: The method `info` returns the instance of the class `TicToc` (self).
        

        """
        if n_rows is None or counter is None or counter % n_rows == 0:
            l: logging.Logger = self.log if logger is None else logger
            l.info(self.get_info(counter=counter, tot=tot, iformat=iformat, dt_format=dt_format, **kwargs))
        return self

    def debug(self,iformat=None, counter: Optional[Union[int, float]] = None, tot: Optional[Union[int, float]] = None,              
              dt_format="%Y-%m-%d %H:%M:%S",
              logger: logging.Logger = None,
              n_rows=None,
              **kwargs) -> TicToc:
        """
        The `debug` function logs information about the progress of a task, including the counter, total,
        elapsed time, speed, remaining time, and other optional parameters.
        
        :param counter: The `counter` parameter is used to track the progress of a task. It can be an
        integer or a float
        :type counter: Optional[Union[int, float]]
        :param tot: The `tot` parameter represents the total number of iterations or items that you are
        processing. It is used to calculate the progress percentage and estimate the remaining time
        :type tot: Optional[Union[int, float]]
        :param iformat: The `iformat` parameter is used to specify the format of the information message
        that will be logged. It is a string that can contain placeholders for various values such as the
        counter, total, elapsed time, speed, etc. These placeholders will be replaced with their
        corresponding values when the message is logged
        all placeholder that you ca use in messages iformat
            counter, i
            tot
            elapsed_time*, et* with * as _s,_m,_h,_d,_str
            elapsed_origin_time*, eot* with * as _s,_m,_h,_d,_str
            speed*, v* with * as _s,_m,_h,_d,_str
            remaining_time*, rt* with * as _s,_m,_h,_d,_str
            total_time*, tt* with * as _s,_m,_h,_d,_str
            end_time*, end* with * as _str
            start_time*, start* with * as _str
            origin_time*, origin* with * as _str
            and all other kwargs defined        
        :param dt_format: The `dt_format` parameter is used to specify the format of the datetime values
        that will be displayed in the log messages. By default, it is set to "%Y-%m-%d %H:%M:%S", which
        represents the format "YYYY-MM-DD HH:MM:SS", defaults to %Y-%m-%d %H:%M:%S (optional)
        :param logger: The `logger` parameter is an optional parameter of type `logging.Logger`. It
        allows you to specify a custom logger object to use for logging the information. If no logger is
        provided, the method will use the default logger object `self.log`
        :type logger: logging.Logger
        :param n_rows: The parameter `n_rows` is used to specify the number of rows after which the
        information should be logged. If `n_rows` is `None` or the current counter value is divisible by
        `n_rows`, the information will be logged
        :return: The method `info` returns the instance of the class `TicToc` (self).        
        """
        if n_rows is None or counter % n_rows == 0:
            l: logging.Logger = self.log if logger is None else logger
            l.debug(self.get_info(counter=counter, tot=tot, iformat=iformat, dt_format=dt_format, **kwargs))
        return self

    def get_info(self,iformat=None, counter: Optional[Union[int, float, str]] = None, tot: Optional[Union[int, float]] = None,                 
                 dt_format="%Y-%m-%d %H:%M:%S",
                 logger: logging.Logger = None,
                 **kwargs) -> str:
        """
        The `get_info` function logs information about the progress of a task, including the counter, total,
        elapsed time, speed, remaining time, and other optional parameters.
        
        :param counter: The `counter` parameter is used to track the progress of a task. It can be an
        integer or a float
        :type counter: Optional[Union[int, float]]
        :param tot: The `tot` parameter represents the total number of iterations or items that you are
        processing. It is used to calculate the progress percentage and estimate the remaining time
        :type tot: Optional[Union[int, float]]
        :param iformat: The `iformat` parameter is used to specify the format of the information message
        that will be logged. It is a string that can contain placeholders for various values such as the
        counter, total, elapsed time, speed, etc. These placeholders will be replaced with their
        corresponding values when the message is logged
        all placeholder that you ca use in messages iformat
            counter, i
            tot
            elapsed_time*, et* with * as _s,_m,_h,_d,_str
            elapsed_origin_time*, eot* with * as _s,_m,_h,_d,_str
            speed*, v* with * as _s,_m,_h,_d,_str
            remaining_time*, rt* with * as _s,_m,_h,_d,_str
            total_time*, tt* with * as _s,_m,_h,_d,_str
            end_time*, end* with * as _str
            start_time*, start* with * as _str
            origin_time*, origin* with * as _str
            and all other kwargs defined        
        :param dt_format: The `dt_format` parameter is used to specify the format of the datetime values
        that will be displayed in the log messages. By default, it is set to "%Y-%m-%d %H:%M:%S", which
        represents the format "YYYY-MM-DD HH:MM:SS", defaults to %Y-%m-%d %H:%M:%S (optional)
        :param logger: The `logger` parameter is an optional parameter of type `logging.Logger`. It
        allows you to specify a custom logger object to use for logging the information. If no logger is
        provided, the method will use the default logger object `self.log`
        :type logger: logging.Logger
        :return: The method `info` returns the instance of the class `TicToc` (self).        
        """
        try:
            counter = self.counter if counter is None else counter
            tot = self.tot if tot is None else tot

            if tot is None:
                iformat = iformat if iformat is not None else self.info_format
            else:
                iformat = iformat if iformat is not None else self.info_tot_format

            fields: set = {name for text, name, spec, conv in self._formatter.parse(iformat)}

            params = {}

            vals = [
                {"aliases": ("counter", "i"), "expr": 'counter'},
                {"aliases": ("tot", ), "expr": 'tot'},
                {"aliases": ("et", "elapsed_time"), "expr": 'self.elapsed_time()', "def": 'str', "units": ('s', 'm', 'h', 'd', "str")},
                {"aliases": ("eot", "elapsed_origin_time"), "expr": 'self.elapsed_origin_time()', "def": 'str', "units": ('s', 'm', 'h', 'd', "str")},
                {"aliases": ("v", "speed"), "expr": 'self.speed(counter) if counter is not None else None', "def": 'h', "units": ('s', 'm', 'h', 'd', "str")},
                {"aliases": ("rt", "remaining_time"), "expr": 'self.remaining_time(counter, tot) if counter is not None and tot is not None else None', "def": 'str',
                 "units": ('s', 'm', 'h', 'd', "str")},
                {"aliases": ("tt", "total_time"), "expr": 'self.total_time(counter, tot) if counter is not None and tot is not None else None', "def": 'str',
                 "units": ('s', 'm', 'h', 'd', "str")},
                {"aliases": ("end", "end_time"), 'expr': 'self.end_time()', "def": 'str', "units": ["str"]},
                {"aliases": ("start", "start_time"), 'expr': 'self.start_time()', "def": 'str', "units": ["str"]},
                {"aliases": ("origin", "origin_time"), 'expr': 'self.origin_time()', "def": 'str', "units": ["str"]},
            ]

            for val in vals:
                v = None
                for alias in val["aliases"]:
                    if alias in fields:
                        v = v if v is not None else eval(val["expr"])
                        if isinstance(v, (TicTocTime, TicTocInterval, TicTocSpeed)):
                            params[alias] = getattr(v, 'to_' + val["def"])
                        else:
                            params[alias] = v
                    units = []
                    if "units" in val.keys():
                        units = list(val["units"])
                    for unit in units:
                        name = alias + "_" + unit
                        if name in fields:
                            v = v if v is not None else eval(val["expr"])
                            if isinstance(v, (TicTocTime, TicTocInterval, TicTocSpeed)):
                                params[name] = getattr(v, 'to_' + unit)
                            else:
                                params[name] = eval("%s(%s)" % (unit, v))

            params.update(kwargs)

            missing = fields - set(params.keys())
            for m in missing:
                params[m] = None
            ret = iformat.format(**params)

            return ret

        except Exception as ex:
            logging.error("An error ignored: %s", ex, exc_info=True)
        return ""


    def __str__(self):
        return str(self.elapsed_time())

