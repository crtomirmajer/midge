import inspect
import json
from typing import Any


class MidgeValueError(ValueError):
    """ Inappropriate argument value (of correct type). """

    def __init__(self, message: str, frame: Any) -> None:
        super().__init__(message)
        self.msg = message
        self.argvals = argvals(frame)

    def __repr__(self) -> str:
        return f'"{self.msg}" \n\t ↳ argvals={self.argvals}'

    def __str__(self) -> str:
        return self.__repr__()


def argvals(frame) -> str:
    args, _, _, values = inspect.getargvalues(frame)
    ctx = {i: values[i] for i in args}
    return json.dumps(ctx)
