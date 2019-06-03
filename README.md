# midge
Lightweight, protocol agnostic, versatile performance testing framework, that can be used 
to test HTTP servers, gRPC services, databases and much more!

## Install

Using `pip`:

    pip install git+https://github.com/crtomirmajer/midge.git

## Commands

**run** performance test:

    midge run performance_test.py

**analyze** results:

    midge analyze dummytest.log

## Core concepts

* `midge.Midge` represents a single _agent_ (user) on a target system; 
* `midge.action` contains the _logic_ for executing single action on the target system (typically hitting one endpoint);
* `<Task>` definition of a performance test, consisting of multiple _actions_ and executed by multiple agents;
* `midge.swarm` is a _pool_ of agents executing a provided task concurrently;

## Examples

### HTTP

    import aiohttp

    import midge
    from midge import ActionResult
    
    
    @midge.swarm(
        population=10,
        rps=100,
        total_requests=5000,
    )
    class DummyTask:
        url = 'https://somewhere.on.the.webz'
    
        async def setup(self):
            self.session = aiohttp.ClientSession()
    
        @midge.action()
        async def get_profile(self) -> ActionResult:
            async with self.session.get(f'{self.url}/profile') as response:
                return await response.text(), True
    
        @midge.action()
        async def get_time(self) -> ActionResult:
            async with self.session.get(f'{self.url}/time') as response:
                return await response.text(), True
    
        async def teardown(self):
            await self.session.close()
