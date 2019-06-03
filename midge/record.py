import json
from typing import Any, Dict, List, Optional, TypeVar, Union

from dataclass_marshal import dataclass, marshal, unmarshal
from numpy import NaN

MidgeId = str
T = TypeVar('T')


class Record:
    pass


WritableRecord = Union[Record, List[Record], Dict[str, Record]]


# Action logs

@dataclass
class ActionLog(Record):
    midge: MidgeId
    action: str
    start: float
    end: float
    success: bool
    response: Any


# Reports

@dataclass
class RequestsReport(Record):
    total: int
    avg_per_sec: float

    def compare(self, b: 'RequestsReport') -> 'RequestsReport':
        return RequestsReport(
            total=delta(self.total, b.total),
            avg_per_sec=delta(self.avg_per_sec, b.avg_per_sec),
        )


@dataclass
class ResponseTimesReport(Record):
    total: int
    mean: float
    stdev: float
    min: float
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float
    max: float

    def compare(self, b: 'ResponseTimesReport') -> 'ResponseTimesReport':
        return ResponseTimesReport(
            total=delta(self.total, b.total),
            mean=delta(self.mean, b.mean),
            stdev=delta(self.stdev, b.stdev),
            min=delta(self.min, b.min),
            p50=delta(self.p50, b.p50),
            p75=delta(self.p75, b.p75),
            p90=delta(self.p90, b.p90),
            p95=delta(self.p95, b.p95),
            p99=delta(self.p99, b.p99),
            max=delta(self.max, b.max),
        )


@dataclass
class ResponsesReport(Record):
    success_rate: float
    succeeded: int
    failed: int
    response_times: ResponseTimesReport

    def compare(self, b: 'ResponsesReport') -> 'ResponsesReport':
        return ResponsesReport(
            success_rate=delta(self.success_rate, b.success_rate),
            succeeded=delta(self.succeeded, b.succeeded),
            failed=delta(self.failed, b.failed),
            response_times=self.response_times.compare(b.response_times),
        )


@dataclass
class PerformanceReport(Record):
    duration: float
    requests: RequestsReport
    responses: ResponsesReport

    def compare(self, b: 'PerformanceReport') -> 'PerformanceReport':
        return PerformanceReport(
            duration=delta(self.duration, b.duration),
            requests=self.requests.compare(b.requests),
            responses=self.responses.compare(b.responses),
        )


FullReport = Dict[str, PerformanceReport]


# Utils

def delta(a: float, b: float) -> Dict[str, float]:
    absolute = round(a - b, 3)
    if b == 0:
        relative = NaN
    else:
        relative = round(absolute / b, 3)
    return {'relative': relative, 'absolute': absolute}


# Serialization

def dump(obj: WritableRecord, file_name: str) -> None:
    data = marshal(obj)
    with open(file_name, 'w') as output_file:
        json.dump(data, output_file, indent=2)


def dumpd(obj: WritableRecord) -> Dict[Any, Any]:
    return marshal(obj)


def dumps(obj: WritableRecord) -> str:
    data = dumpd(obj)
    return json.dumps(data, indent=2)


def load(file_name: str, cls: Optional[T] = None) -> T:
    with open(file_name.lower(), 'r') as input_file:
        data = json.load(input_file)
    return unmarshal(data, cls) if cls else data


def loadd(payload: Dict[Any, Any], cls: T) -> T:
    return unmarshal(payload, cls)


def loads(payload: str, cls: Optional[T] = None) -> T:
    data = json.loads(payload)
    return loadd(data, cls) if cls else data
