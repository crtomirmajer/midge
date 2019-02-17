from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor
import inspect
import itertools
import logging
from statistics import mean, pstdev

import gevent
from gevent import monkey
import numpy as np

from midge.errors import MidgeValueError
from midge.record import (
    ActionLog, FullReport, MidgeId, PerformanceReport, RequestsReport, ResponseTimesReport, ResponsesReport,
)

monkey.patch_all()

import asyncio
import random
from threading import Timer, Lock
import time
from typing import Any, Callable, List, Optional, Tuple, Type, Union

ActionResult = Tuple[Any, bool]
ActionFunc = Callable[[Any], ActionResult]
AnyFunc = Callable[[Any], Any]

ROUND_PRECISION = 3

_loop = asyncio.get_event_loop()
_swarm_counter = 0

logging.basicConfig(level=logging.INFO)


# Decorators

def action(weight: int = 1) -> AnyFunc:
    if weight < 1:
        raise MidgeValueError('Invalid action setting/s', inspect.currentframe())

    def decorator(func: ActionFunc) -> ActionFunc:
        def midge_action(args) -> ActionResult:
            return func(args)

        midge_action.__midge_action__ = True
        midge_action.__weight__ = weight
        midge_action.__name__ = func.__name__
        return midge_action

    return decorator


def swarm(population: int = 1,
          rps_rate: Optional[int] = None,
          total_requests: Optional[int] = None,
          duration: Optional[int] = None) -> AnyFunc:
    global _swarm_counter
    _swarm_counter += 1

    if (population < 1
        or (rps_rate and rps_rate < 1)
        or (total_requests and total_requests < 1)
        or (duration and duration < 1)):
        raise MidgeValueError('Invalid swarm setting/s', inspect.currentframe())

    def decorator(cls: Type[Task]) -> ActionFunc:
        def midge_swarm() -> Any:
            return Swarm(_swarm_counter,
                         action_definitions=cls,
                         population=population,
                         rps_rate=rps_rate,
                         total_requests=total_requests,
                         duration=duration)

        midge_swarm.__midge_swarm_constructor__ = True
        return midge_swarm

    return decorator


# Classes

class Task:

    def __init__(self, action_definitions: Any):
        self._action_definitions = action_definitions
        actions = [action_method
                   for action_method in action_definitions.__class__.__dict__.values()
                   if getattr(action_method, '__midge_action__', False)]
        weight_sum = sum(action.__weight__ for action in actions)
        commutative_probability = 0
        self._action_probabilities = {}
        for action in actions:
            probability = action.__weight__ / weight_sum
            commutative_probability += probability
            self._action_probabilities[commutative_probability] = action

    def run(self, midge_id: MidgeId) -> ActionLog:
        start = now()
        action = self._choose_action()
        response, success = action(self._action_definitions)
        end = now()
        return ActionLog(midge=midge_id,
                         action=action.__name__,
                         start=start,
                         end=end,
                         success=success,
                         response=response)

    def _choose_action(self) -> ActionFunc:
        r = random.random()
        for commutative_probability, action in self._action_probabilities.items():
            if r <= commutative_probability:
                return action


class Midge:
    """
    Represents a single worker executing a given task
    """

    _executor = None

    def __init__(self, identifier: int,
                 swarm: "Swarm",
                 task: Task,
                 on_action_finished: Callable[[ActionLog], None],
                 rps: Optional[int] = None) -> None:
        self._identifier = f'M{identifier}@{swarm._identifier}'
        self._task = task
        self._on_action_finished = on_action_finished
        self._rps = rps
        self._active = True

    async def run(self) -> MidgeId:
        logging.info(f'action="Midge {self._identifier} is now running!"')
        i = 0
        while self._active:
            if self._rps:
                # run once per second to meet RPS requirements;
                # randomly distribute requests over one second period,
                # than wait for approximately 1 second before triggering again
                start = time.time()
                attacks = [self.attack(delay=_rand_delay()) for _ in range(self._rps)]
                await asyncio.wait(attacks)
                wait_duration = 1 - (time.time() - start)
                await asyncio.sleep(wait_duration)
            else:
                # no RPS to meet, simply execute task one after another as previous one finishes
                delay = _rand_delay() if i == 0 else 0  # delay first request
                await self.attack(True, delay=delay)
            i += 1

        return self._identifier

    async def attack(self, wait: bool = False, delay: int = 0):

        await asyncio.sleep(delay)
        # Gevent is used only for running blocking tasks
        greenlet = gevent.spawn(self._task.run, self._identifier)
        greenlet.link_value(lambda greenlet: self._on_action_finished(greenlet.value))

        if wait:
            await _loop.run_in_executor(Midge._executor, gevent.wait, [greenlet])

    def stop(self) -> None:
        self._active = False

    @classmethod
    def init_executor(cls, max_workers: int):
        cls._executor = ThreadPoolExecutor(max_workers=max_workers + 10)


class Swarm:
    """
    Manages a swarm of midges
    """

    def __init__(self, identifier: int,
                 action_definitions: type,
                 population: int = 1,
                 rps_rate: int = None,
                 total_requests: int = None,
                 duration: int = None):
        self._identifier = f'S{identifier}'
        self._action_definitions = action_definitions
        self._population = population
        self._rps_rate = rps_rate
        self._total_requests_limit = total_requests
        self._duration = duration

        self._total_requests_counter = itertools.count()
        self._lock = Lock()
        self._active = False

    def run(self) -> List[ActionLog]:
        self._active = True
        self._logs = []

        if self._rps_rate is None:
            Midge.init_executor(self._population)

        self._midges = self._spawn_midges(self._population)

        logging.info(f'action="Swarm {self._identifier} consisting of {len(self._midges)} Midges is starting!"')

        if self._duration:
            t = Timer(self._duration, self.stop, kwargs=dict(reason='Time duration reached'))
            t.start()

        coroutines = [midge.run() for midge in self._midges]
        _loop.run_until_complete(self._collect_midges(coroutines))

        return self._logs

    def stop(self, reason: str):
        logging.info(f'action="Stopping Midges!" reason="{reason}"')
        self._active = False
        for t in self._midges:
            t.stop()
        del self._midges

    def _spawn_midges(self, n: int) -> List[Midge]:
        rps_per_midges = [None] * n
        if self._rps_rate:
            # distribute RPS rate across midges
            rps_per_midge = int(self._rps_rate / n)
            rps_remaining = self._rps_rate - (rps_per_midge * n)
            rps_per_midges = [rps_per_midge + 1 if i < rps_remaining else rps_per_midge
                              for i, _ in enumerate(rps_per_midges)]
        return [Midge(identifier=i + 1,
                      swarm=self,
                      task=Task(self._action_definitions()),
                      on_action_finished=self._on_action_finished,
                      rps=rps)
                for i, rps in enumerate(rps_per_midges)]

    async def _collect_midges(self, tasks):
        for res in asyncio.as_completed(tasks):
            midge_id = await res
            logging.info(f'action="{midge_id} stopped!"')

    def _on_action_finished(self, result: ActionLog) -> None:
        with self._lock:
            if not self._active:
                return
            count = next(self._total_requests_counter)
            if (count + 1) >= self._total_requests_limit:
                self.stop('Total requests reached')
            self._logs.append(result)


# Core Functions

def analyze(logs: List[ActionLog]) -> FullReport:
    partitions = defaultdict(list)
    for log in logs:
        partitions[log.action].append(log)

    full_report: FullReport = OrderedDict()
    full_report['*'] = analyze_performance(logs)
    if len(partitions) > 1:
        for action_name, action_logs in partitions.items():
            report = analyze_performance(action_logs)
            full_report[action_name] = report
    return full_report


def analyze_performance(logs: List[ActionLog]) -> PerformanceReport:
    # sort by request time
    logs = sorted(logs, key=lambda x: x.start)

    # count
    count = len(logs)

    # duration analysis
    start = logs[0].start
    end = logs[-1].end
    duration = end - start

    # request / response analysis
    succeeded = len([log.success for log in logs])
    failed = count - succeeded
    success_rate = round(succeeded / count, ROUND_PRECISION)
    actual_avg_rps = round(count / (duration / 1000), ROUND_PRECISION)
    response_times = [(log.end - log.start) for log in logs]

    # response times analysis
    rt_total = sum(response_times)
    rt_mean = round(mean(response_times), ROUND_PRECISION)
    rt_stdev = round(pstdev(response_times), ROUND_PRECISION)
    rt_min = min(response_times)
    rt_max = max(response_times)
    rt_p50 = np.percentile(response_times, 50)
    rt_p75 = np.percentile(response_times, 75)
    rt_p90 = np.percentile(response_times, 90)
    rt_p95 = np.percentile(response_times, 95)
    rt_p99 = np.percentile(response_times, 99)

    return PerformanceReport(
        duration=duration,
        requests=RequestsReport(
            total=count,
            avg_per_sec=actual_avg_rps,
        ),
        responses=ResponsesReport(
            success_rate=success_rate,
            succeeded=succeeded,
            failed=failed,
            response_times=ResponseTimesReport(
                total=rt_total,
                mean=rt_mean,
                stdev=rt_stdev,
                min=rt_min,
                p50=rt_p50,
                p75=rt_p75,
                p90=rt_p90,
                p95=rt_p95,
                p99=rt_p99,
                max=rt_max,
            )
        ),
    )


def compare(report: Union[PerformanceReport, FullReport],
            baseline: Union[PerformanceReport, FullReport]) -> Union[PerformanceReport, FullReport]:
    assert type(report) == type(baseline)

    if isinstance(report, PerformanceReport):
        return baseline.compare(report)
    else:
        comparison: FullReport = {
            key: baseline[key].compare(report[key])
            for key in report.keys()
        }
        return comparison


# Utils

def _rand_delay(min: float = 0., max: float = 1.) -> int:
    # return random delay in seconds
    if min >= max:
        raise ValueError('Invalid range - max must be bigger than min')
    return min + (random.random() % (max - min))


def now() -> float:
    # return current time in milliseconds
    return round(time.time() * 1000)
