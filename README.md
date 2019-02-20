# midge
Lightweight, protocol agnostic, versatile performance testing framework, that can be used 
to test HTTP servers, gRPC services, databases and much more!

## Install

Using `pip`:

    pip install git+https://github.com/crtomirmajer/midge.git

## Core concepts

* `midge.Midge` represents a single agent (user) on a target system; 
* `midge.action` contains the logic for executing single action on the target system (typically hitting one endpoint);
* `<Task>` is a definition of a task, typically consisted of multiple actions and executed by multiple agents;
* `midge.swarm` is a pool of agents executing a provided task at the same time;

## Examples

### HTTP

    import urllib.request
    
    import midge
    from midge import ActionResult
    
    
    @midge.swarm(
        population=5,
        rps_rate=5000,
        total_requests=50000,
    )
    class DummyTask:
        url = 'http://0.0.0.0:8000'
        
        @midge.action()
        def login(self) -> ActionResult:
            contents = urllib.request.urlopen(f'{self.url}/parse').read()
            return contents.decode('utf-8'), True
    
        @midge.action(weight=2)
        def get_user(self) -> ActionResult:
            contents = urllib.request.urlopen(f'{self.url}/get_user').read()
            return contents.decode('utf-8'), True
