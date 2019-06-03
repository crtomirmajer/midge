import asyncio
import inspect
from unittest.mock import MagicMock, call

import pytest

import midge
from midge.core import ActionResult, Swarm, now, Midge, Task
from midge.record import ActionLog

_MIDGE_ID_FORMAT = 'M{}@S{}'


class DummyActions:
    spy = MagicMock()
    callers = set()

    @midge.action()
    async def ping(self) -> ActionResult:
        caller = inspect.currentframe().f_back
        while not isinstance(caller.f_locals.get('self'), Task):
            caller = caller.f_back
        caller = caller.f_locals['self']
        self.callers.add(caller)
        self.spy(caller)
        await asyncio.sleep(0.1)
        return 'OK', True


@pytest.mark.parametrize('swarm_id, population, rps, total_requests', [
    (1337, 3, 30, 300),
    (1338, 10, 10, 50),
    # (1339, 30, None, 3000)
])
def test_swarm_limit_requests(swarm_id, population, rps, total_requests):
    duration_tolerance_ms = 100

    swarm = Swarm(
        identifier=swarm_id,
        population=population,
        task_definition=DummyActions,
        rps=rps,
        total_requests=total_requests,
        duration=None
    )

    loop = asyncio.get_event_loop()

    loop.run_until_complete(swarm.setup())
    # run swarm
    start_ms = now()
    action_logs = loop.run_until_complete(swarm.run())
    end_ms = now()

    loop.run_until_complete(swarm.teardown())

    # validate

    midge_ids = {_MIDGE_ID_FORMAT.format(i, swarm_id) for i in range(1, population + 1)}

    assert DummyActions.spy.call_count >= total_requests
    assert len(action_logs) == total_requests
    assert all(isinstance(log, ActionLog) for log in action_logs)
    assert all(log.success is True and
               log.midge in midge_ids and
               log.start >= start_ms and log.start < end_ms and
               log.end > start_ms and log.end <= end_ms and
               log.response == 'OK'
               for log in action_logs)

    # assert that there were N different action callers (midges),
    # each making (total_request/population) calls; N=population
    assert len(DummyActions.callers) == population
    if rps:
        calls = []
        calls_per_midge = int(total_requests / population)
        for caller in DummyActions.callers:
            calls.extend([call(caller)] * calls_per_midge)
        DummyActions.spy.assert_has_calls(calls, any_order=True)

        # swarm should run for approximately (total_requests/rps) seconds
        duration_ms = end_ms - start_ms
        expected_duration_ms = (total_requests / rps) * 1000  # multiply by 1000 to get milliseconds

        assert duration_ms >= (expected_duration_ms - duration_tolerance_ms)
        assert duration_ms < (expected_duration_ms + duration_tolerance_ms)

    # reset
    DummyActions.spy = MagicMock()
    DummyActions.callers = set()
