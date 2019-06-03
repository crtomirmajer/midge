import inspect
import os
import sys
from typing import Any, Callable, Dict

from midge.core import Swarm


def is_midge_swarm(item: Any) -> bool:
    item = item[1]
    return inspect.isfunction(item) and getattr(item, '__midge_swarm_constructor__', True)


def import_midge_file(file_path: str) -> Dict[str, Callable[[], Swarm]]:
    # Get directory and locustfile name
    directory, definition_file = os.path.split(file_path)
    # If the directory isn't in the PYTHONPATH, add it so our import will work
    added_to_path = False
    index = None
    if directory not in sys.path:
        sys.path.insert(0, directory)
        added_to_path = True
    else:
        i = sys.path.index(directory)
        if i != 0:
            # Store index for later restoration
            index = i
            # Add to front, then remove from original position
            sys.path.insert(0, directory)
            del sys.path[i + 1]
    # Perform the import (trimming off the .py)
    imported = __import__(os.path.splitext(definition_file)[0])
    # Remove directory from path if we added it ourselves (just to be neat)
    if added_to_path:
        del sys.path[0]
    # Put back in original index if we moved it
    if index is not None:
        sys.path.insert(index + 1, directory)
        del sys.path[0]

    tasks = dict(filter(is_midge_swarm, vars(imported).items()))
    return tasks
