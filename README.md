> August 16, 2021: Version 5 has been released. Read about the [changes in
> version 5](https://composed.blog/jsonrpcserver-5-changes), or read the [full
> documentation](https://www.jsonrpcserver.com/en/stable/).
> Version 5 is for Python 3.8+ only. For earlier versions jump to the [4.x
> branch](https://github.com/explodinglabs/jsonrpcserver/tree/4.x) or read the
> [documentation for version 4](https://www.jsonrpcserver.com/en/4.2.0/).

<img
    alt="jsonrpcserver"
    style="margin: 0 auto;"
    src="https://github.com/explodinglabs/jsonrpcserver/blob/main/docs/logo.png?raw=true"
/>

Process incoming JSON-RPC requests in Python.

![PyPI](https://img.shields.io/pypi/v/jsonrpcserver.svg)
![Downloads](https://pepy.tech/badge/jsonrpcserver/week)
![Checks](https://github.com/explodinglabs/jsonrpcserver/actions/workflows/code-quality.yml/badge.svg)
![Coverage Status](https://coveralls.io/repos/github/explodinglabs/jsonrpcserver/badge.svg?branch=main)

```python
from jsonrpcserver import Success, method, serve

@method
def ping():
    return Success("pong")

if __name__ == "__main__":
    serve()
```

Full documentation is at [jsonrpcserver.com](https://www.jsonrpcserver.com/).

See also: [jsonrpcclient](https://github.com/explodinglabs/jsonrpcclient)
