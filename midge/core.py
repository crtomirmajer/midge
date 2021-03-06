import asyncio
import hashlib
import itertools
import logging
import random
from threading import Timer
import time
from typing import Any, Callable, Coroutine, List, Optional, Tuple, Union
import uuid

import math

from midge.errors import MidgeValueError
from midge.record import (
    ActionLog, MidgeId,
)

ActionResult = Tuple[Any, bool]
ActionFunc = Callable[[Any], Coroutine[Any, Any, ActionResult]]
AnyFunc = Callable[[Any], Any]

TIME_PRECISION = 1000
ROUND_PRECISION = 3
WAIT_SEC = 0.99999

_loop = asyncio.get_event_loop()
_swarm_counter = 0


# Decorators

def action(weight: int = 1) -> AnyFunc:
    if weight < 1:
        raise MidgeValueError('Invalid action setting/s', locals())

    def decorator(func: ActionFunc) -> ActionFunc:
        async def midge_action(*args) -> ActionResult:
            try:
                return await func(*args)
            except Exception:
                return None, False

        midge_action.__midge_action__ = True
        midge_action.__weight__ = weight
        midge_action.__name__ = func.__name__
        return midge_action

    return decorator


def swarm(population: int = 1,
          rps: Optional[int] = None,
          total_requests: Optional[int] = None,
          duration: Optional[int] = None,
          warm_up: Optional[int] = None) -> AnyFunc:
    global _swarm_counter
    _swarm_counter += 1

    if (population < 1
        or (rps and rps < 1)
        or (total_requests and total_requests < 1)
        or (duration and duration < 1)):
        raise MidgeValueError('Invalid swarm setting/s', locals())

    def decorator(cls: type) -> Callable[[], Swarm]:
        def midge_swarm() -> Swarm:
            return Swarm(_swarm_counter,
                         task_definition=cls,
                         population=population,
                         rps=rps,
                         total_requests=total_requests,
                         duration=duration,
                         warm_up=warm_up)

        midge_swarm.__midge_swarm_constructor__ = True
        return midge_swarm

    return decorator


# Classes

class Task:

    def __init__(self, task_definition: type):
        self._instance = task_definition()
        self._init_action_probabilities()

    async def setup(self):
        if hasattr(self._instance, 'setup'):
            await self._instance.setup()

    async def run(self, midge_id: MidgeId) -> ActionLog:
        action = self._choose_action()
        start = now()
        response, success = await action(self._instance)
        end = now()
        return ActionLog(midge=midge_id,
                         action=action.__name__,
                         start=start,
                         end=end,
                         success=success,
                         response=response)

    async def teardown(self):
        if hasattr(self._instance, 'teardown'):
            await self._instance.teardown()

    # Utils

    def _init_action_probabilities(self):
        actions = [
            action_method
            for action_method in self._instance.__class__.__dict__.values()
            if getattr(action_method, '__midge_action__', False)
        ]

        weight_sum = sum(action.__weight__ for action in actions)
        commutative_probability = 0
        self._action_probabilities = {}

        for action in actions:
            probability = action.__weight__ / weight_sum
            commutative_probability += probability
            self._action_probabilities[commutative_probability] = action

    def _choose_action(self) -> ActionFunc:
        r = random.random()
        for commutative_probability, action in self._action_probabilities.items():
            if r <= commutative_probability:
                return action


class Midge:
    """
    Represents a single worker executing a given task
    """

    def __init__(self, identifier: str,
                 swarm: "Swarm",
                 task: Task,
                 on_action_complete: Callable[[Union[asyncio.Task, ActionLog]], None],
                 rps: Optional[int] = None,
                 chance_of_action: float = 1) -> None:
        self._id = f'{identifier}@{swarm._id}'
        self._task = task
        self._on_action_complete = on_action_complete
        self._rps = rps
        self._chance_of_action = chance_of_action
        self._active = True

    def set_chance_of_action(self, chance_of_action):
        self._chance_of_action = chance_of_action

    async def setup(self):
        await self._task.setup()

    async def run(self) -> MidgeId:
        logging.info(f'{self._id} is running')
        i = 0
        while self._active:
            if self._rps:
                # run once per second to meet RPS requirements;
                # randomly distribute requests over one second period,
                # than wait for approximately 1 second before triggering again
                attacks = [self._perform_action(delay=rand_delay()) for _ in range(self._rps)]
                await asyncio.wait(attacks)
                fraction, _ = math.modf(time.time())
                wait_duration = WAIT_SEC - fraction
                await asyncio.sleep(wait_duration)
            else:
                # no RPS to meet, simply execute task one after another as previous one finishes
                delay = rand_delay() if i == 0 else 0  # delay first request
                await self._perform_action(wait=True, delay=delay)
            i += 1

        return self._id

    async def _perform_action(self, wait: bool = False, delay: int = 0):
        await asyncio.sleep(delay)

        if self._chance_of_action < 1 and random.random() > self._chance_of_action:
            if wait:
                # default to 1 sec sleep
                await asyncio.sleep(WAIT_SEC)
            return

        if wait:
            res = await self._task.run(self._id)
            self._on_action_complete(res)
        else:
            future = _loop.create_task(self._task.run(self._id))
            future.add_done_callback(self._on_action_complete)

    def stop(self) -> None:
        self._active = False

    def reset(self):
        self._active = True

    async def teardown(self) -> None:
        await self._task.teardown()


class Swarm:
    """
    Manages a swarm of midges
    """

    def __init__(self, identifier: int,
                 task_definition: type,
                 population: int = 1,
                 rps: Optional[int] = None,
                 total_requests: Optional[int] = None,
                 duration: Optional[int] = None,
                 warm_up: Optional[int] = None):
        self._id = f'S{identifier}'
        self._task_definition = task_definition
        self._population = population
        self._rps = rps
        self._total_requests_limit = total_requests
        self._duration = duration
        self._warm_up = warm_up
        self._total_requests_counter = itertools.count()
        self._active = False

    async def setup(self):
        self._midges = self._spawn_midges(self._population, self._rps)
        coros = [midge.setup() for midge in self._midges]
        await asyncio.gather(*coros)
        logging.info(f'Swarm {self._id} with {len(self._midges)} Midges is ready')

    async def warmup(self, steps: int = 10) -> None:
        step_time = self._warm_up / steps
        # Gradually increase chance of action for midges
        for i in range(steps):
            Timer(i * step_time, self._modify_midges, kwargs=dict(chance_of_action=i / steps)).start()
        # End warm-up
        Timer(self._warm_up, self.stop, kwargs=dict(reason='Warm-up finished')).start()

        coros = [midge.run() for midge in self._midges]
        await asyncio.gather(*coros)

        self._modify_midges(1)
        [midge.reset() for midge in self._midges]

    async def run(self) -> List[ActionLog]:

        if self._warm_up:
            await self.warmup()

        self._active = True
        self._logs = []

        if self._duration:
            t = Timer(self._duration, self.stop, kwargs=dict(reason='Time duration is reached'))
            t.start()

        logging.info(f'Swarming started')

        coros = [midge.run() for midge in self._midges]
        await asyncio.gather(*coros)

        logging.info(f'Swarming finished')

        return self._logs

    def stop(self, reason: str):
        logging.info(f'Stopping Midges - {reason}')
        self._active = False
        for t in self._midges:
            t.stop()

    async def teardown(self):
        coros = [midge.teardown() for midge in self._midges]
        await asyncio.gather(*coros)
        del self._midges

    # Utils

    def _spawn_midges(self, n: int, rps: int) -> List[Midge]:
        rps_per_midges = [None] * n
        if rps:
            # distribute RPS rate across midges
            rps_per_midge = int(rps / n)
            rps_remaining = rps - (rps_per_midge * n)
            rps_per_midges = [rps_per_midge + 1 if i < rps_remaining else rps_per_midge
                              for i, _ in enumerate(rps_per_midges)]
        return [
            Midge(identifier=str(hashlib.md5(uuid.uuid4().bytes).hexdigest()[:6]),
                  swarm=self,
                  task=Task(self._task_definition),
                  on_action_complete=self._on_action_complete,
                  rps=rps)
            for i, rps in enumerate(rps_per_midges)
        ]

    def _modify_midges(self, chance_of_action: float):
        logging.info(f'Modifying midges - COA={chance_of_action}')
        for midge in self._midges:
            midge.set_chance_of_action(chance_of_action)

    # Callbacks

    def _on_action_complete(self, result: Union[asyncio.Task, ActionLog]) -> None:
        if not self._active:
            return

        count = next(self._total_requests_counter)
        if (count + 1) >= self._total_requests_limit:
            self.stop('Total requests are reached')

        if isinstance(result, asyncio.Task):
            result = result.result()
        self._logs.append(result)

# Utils

def rand_delay(min: float = 0., max: float = 1.) -> int:
    # return random delay in seconds
    if min >= max:
        raise ValueError('Invalid range - max must be bigger than min')
    return min + (random.random() % (max - min))


def now() -> float:
    # return current time in milliseconds
    return round(time.time() * TIME_PRECISION)
