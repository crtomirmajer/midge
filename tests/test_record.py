import json

import pytest

from midge.record import (
    ActionLog,
    PerformanceReport,
    RequestsReport,
    ResponseTimesReport,
    ResponsesReport,
    dumpd,
    dumps,
    loadd,
    loads,
)


@pytest.mark.parametrize('obj, obj_dict', [
    (
        ActionLog(
            midge='M1',
            action='dummy',
            start=1.1,
            end=1.2,
            success=True,
            response={'status': 'OK'}
        ),
        {
            'midge': 'M1',
            'action': 'dummy',
            'start': 1.1,
            'end': 1.2,
            'success': True,
            'response': {'status': 'OK'}
        }

    ),
    (
        PerformanceReport(
            duration=10.11,
            requests=RequestsReport(
                total=1,
                avg_per_sec=1,
            ),
            responses=ResponsesReport(
                success_rate=1,
                succeeded=10,
                failed=0,
                response_times=ResponseTimesReport(
                    total=10,
                    mean=1,
                    stdev=0,
                    min=1,
                    p50=1,
                    p75=1,
                    p90=1,
                    p95=1,
                    p99=1,
                    max=1,
                ),
            )
        ),
        {
            'duration': 10.11,
            'requests': {
                'total': 1,
                'avg_per_sec': 1,
            },
            'responses': {
                'success_rate': 1,
                'succeeded': 10,
                'failed': 0,
                'response_times': {
                    'total': 10,
                    'mean': 1,
                    'stdev': 0,
                    'min': 1,
                    'p50': 1,
                    'p75': 1,
                    'p90': 1,
                    'p95': 1,
                    'p99': 1,
                    'max': 1,
                },
            }
        }
    )
])
def test_serialization(obj, obj_dict):
    assert dumpd(obj) == obj_dict
    assert dumps(obj) == json.dumps(obj_dict, indent=2)
    cls = type(obj)
    assert loadd(obj_dict, cls) == obj
    assert loads(json.dumps(obj_dict), cls) == obj
