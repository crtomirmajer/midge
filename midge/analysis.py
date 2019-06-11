from collections import OrderedDict, defaultdict
from statistics import mean, pstdev
from typing import List, Union

import numpy as np

from midge.record import (
    ActionLog, FullReport, PerformanceReport, RequestsReport, ResponseTimesReport, ResponsesReport,
)


def analyze(logs: List[ActionLog]) -> FullReport:
    partitions = defaultdict(list)
    for log in logs:
        partitions[log.action].append(log)

    full_report: FullReport = OrderedDict()
    full_report['*'] = _analyze(logs)
    if len(partitions) > 1:
        for action_name, action_logs in partitions.items():
            report = _analyze(action_logs)
            full_report[action_name] = report
    return full_report


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


def _analyze(logs: List[ActionLog]) -> PerformanceReport:
    # sort by request time
    logs = sorted(logs, key=lambda x: x.start)

    # count
    count = len(logs)

    # duration analysis
    start = logs[0].start
    end = logs[-1].end
    duration = end - start

    # request / response analysis
    succeeded = sum(1 for log in logs if log.success)
    failed = count - succeeded
    success_rate = succeeded / count
    actual_avg_rps = count / (duration / 1000)
    response_times = [(log.end - log.start) for log in logs]

    # response times analysis
    rt_total = sum(response_times)
    rt_mean = mean(response_times)
    rt_stdev = pstdev(response_times)
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
