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
* `midge.swarm` is a pool of agents executing a provided task concurrently;

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
