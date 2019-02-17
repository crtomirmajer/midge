import json
from typing import Any, Dict, List, Optional, Union

from dataclass_marshal import dataclass, marshal, unmarshal

MidgeId = str


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
            total=self.total / b.total,
            avg_per_sec=self.avg_per_sec / b.avg_per_sec,
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
            total=self.total / b.total,
            mean=self.mean / b.mena,
            stdev=self.stdev / b.stdev,
            min=self.min / b.min,
            p50=self.p50 / b.p50,
            p75=self.p75 / b.p75,
            p90=self.p90 / b.p90,
            p95=self.p95 / b.p95,
            p99=self.p99 / b.p99,
            max=self.max / b.max,
        )


@dataclass
class ResponsesReport(Record):
    success_rate: float
    succeeded: int
    failed: int
    response_times: ResponseTimesReport

    def compare(self, b: 'ResponsesReport') -> 'ResponsesReport':
        return ResponsesReport(
            success_rate=self.success_rate / b.success_rate,
            succeeded=self.succeeded / b.succeeded,
            failed=self.failed / b.failed,
            response_times=self.response_times.compare(b.response_times),
        )


@dataclass
class PerformanceReport(Record):
    duration: float
    requests: RequestsReport
    responses: ResponsesReport

    def compare(self, b: 'PerformanceReport') -> 'PerformanceReport':
        return PerformanceReport(
            duration=self.duration / b.duration,
            request=self.requests.compare(b.requests),
            responses=self.responses.compare(b.responses),
        )


FullReport = Dict[str, PerformanceReport]


# Utils

def dump(obj: WritableRecord, file_name: str) -> None:
    data = marshal(obj)
    with open(file_name, 'w') as output_file:
        json.dump(data, output_file, indent=2)


def dumpd(obj: WritableRecord) -> Dict[Any, Any]:
    return marshal(obj)


def dumps(obj: WritableRecord) -> str:
    data = dumpd(obj)
    return json.dumps(data, indent=2)


def load(file_name: str, cls: Optional[type] = None) -> Union[WritableRecord, Dict[Any, Any]]:
    with open(file_name.lower(), 'r') as input_file:
        data = json.load(input_file)
    return unmarshal(data, cls) if cls else data


def loadd(payload: Dict[Any, Any], cls: type) -> WritableRecord:
    return unmarshal(payload, cls)


def loads(payload: str, cls: Optional[type] = None) -> Union[WritableRecord, Dict[Any, Any]]:
    data = json.loads(payload)
    return loadd(data, cls) if cls else data
