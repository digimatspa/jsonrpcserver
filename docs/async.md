# Async

Async dispatch is supported.

```python
from jsonrpcserver import method, Success, async_dispatch

@method
async def ping() -> Result:
    return Success("pong")

await async_dispatch('{"jsonrpc": "2.0", "method": "ping", "id": 1}')
```

Some reasons to use this:

1. Use it with an asynchronous transport protocol like [websockets](examples#websockets).
2. `await` long-running functions from your method.
3. Batch requests are dispatched concurrently.

## Notifications

A notification is a request with no `id`. We should not respond to
notifications, so jsonrpcserver gives an empty string to signify *there is no
response*.

```python
>>> await async_dispatch('{"jsonrpc": "2.0", "method": "ping"}')
''
```

If the response is an empty string, don't send it. Otherwise, send it.

```python
if response := dispatch(request):
    send(response)
```

```{note}
A synchronous protocol like HTTP requires a response no matter what, so we can
send back the empty string. However with async protocols, we have the choice of
responding or not.
```
