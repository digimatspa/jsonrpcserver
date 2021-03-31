"""
Dispatcher.

The dispatch() function takes a JSON-RPC request, logs it, calls the appropriate method,
then logs and returns the response.
"""
import asyncio
import logging
import os
from collections.abc import Iterable
from configparser import ConfigParser
from contextlib import contextmanager
from json import JSONDecodeError
from json import dumps as default_serialize, loads as default_deserialize
from types import SimpleNamespace
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Union,
)

from apply_defaults import apply_config  # type: ignore
from jsonschema import ValidationError  # type: ignore
from jsonschema.validators import validator_for  # type: ignore
from pkg_resources import resource_string

from .log import log_
from .methods import Method, Methods, global_methods, validate_args, lookup
from .request import Request, is_notification, NOID
from .response import (
    ApiErrorResponse,
    BatchResponse,
    ExceptionResponse,
    InvalidJSONResponse,
    InvalidJSONRPCResponse,
    InvalidParamsResponse,
    MethodNotFoundResponse,
    NotificationResponse,
    Response,
    SuccessResponse,
)
from .exceptions import MethodNotFoundError, InvalidParamsError, ApiError

request_logger = logging.getLogger(__name__ + ".request")
response_logger = logging.getLogger(__name__ + ".response")

# Prepare the jsonschema validator
schema = default_deserialize(resource_string(__name__, "request-schema.json"))
klass = validator_for(schema)
klass.check_schema(schema)
validator = klass(schema)

DEFAULT_REQUEST_LOG_FORMAT = "--> %(message)s"
DEFAULT_RESPONSE_LOG_FORMAT = "<-- %(message)s"

config = ConfigParser(default_section="dispatch")
config.read([".jsonrpcserverrc", os.path.expanduser("~/.jsonrpcserverrc")])

Context = NamedTuple(
    "Context",
    [("request", Request), ("extra", Any)],
)


def add_handlers() -> Tuple[logging.Handler, logging.Handler]:
    # Request handler
    request_handler = logging.StreamHandler()
    request_handler.setFormatter(logging.Formatter(fmt=DEFAULT_REQUEST_LOG_FORMAT))
    request_logger.addHandler(request_handler)
    request_logger.setLevel(logging.INFO)
    # Response handler
    response_handler = logging.StreamHandler()
    response_handler.setFormatter(logging.Formatter(fmt=DEFAULT_RESPONSE_LOG_FORMAT))
    response_logger.addHandler(response_handler)
    response_logger.setLevel(logging.INFO)
    return request_handler, response_handler


def remove_handlers(
    request_handler: logging.Handler, response_handler: logging.Handler
) -> None:
    request_logger.handlers = [
        h for h in request_logger.handlers if h is not request_handler
    ]
    response_logger.handlers = [
        h for h in response_logger.handlers if h is not response_handler
    ]


def log_request(request: str, trim_log_values: bool = False, **kwargs: Any) -> None:
    """Log a request"""
    return log_(request, request_logger, logging.INFO, trim=trim_log_values, **kwargs)


def log_response(response: str, trim_log_values: bool = False, **kwargs: Any) -> None:
    """Log a response"""
    return log_(response, response_logger, logging.INFO, trim=trim_log_values, **kwargs)


def validate(request: Union[Dict, List], schema: dict) -> Union[Dict, List]:
    """
    Wraps jsonschema.validate, returning the same object passed in.

    Args:
        request: The deserialized-from-json request.
        schema: The jsonschema schema to validate against.

    Raises:
        jsonschema.ValidationError
    """
    validator.validate(request)
    return request


def call(method: Method, *args: Any, **kwargs: Any) -> Any:
    """
    Validates arguments and then calls the method.

    Args:
        method: The method to call.
        *args, **kwargs: Arguments to the method.

    Returns:
        The "result" part of the JSON-RPC response (the return value from the method).
    """
    return validate_args(method, *args, **kwargs)(*args, **kwargs)


@contextmanager
def handle_exceptions(request: Request, debug: bool) -> Generator:
    handler = SimpleNamespace(response=None)
    try:
        yield handler
    except MethodNotFoundError:
        handler.response = MethodNotFoundResponse(
            id=request.id, data=request.method, debug=debug
        )
    except (InvalidParamsError, AssertionError) as exc:
        # InvalidParamsError is raised by validate_args. AssertionError is raised inside
        # the methods, however it's better to raise InvalidParamsError inside methods.
        # AssertionError will be removed in the next major release.
        handler.response = InvalidParamsResponse(
            id=request.id, data=str(exc), debug=debug
        )
    except ApiError as exc:  # Method signals custom error
        handler.response = ApiErrorResponse(
            str(exc), code=exc.code, data=exc.data, id=request.id, debug=debug
        )
    except asyncio.CancelledError:
        # Allow CancelledError from asyncio task cancellation to bubble up. Without
        # this, CancelledError is caught and handled, resulting in a "Server error"
        # response object from the dispatcher, but because the CancelledError doesn't
        # bubble up the rpc_server task doesn't exit. See PR
        # https://github.com/bcb/jsonrpcserver/pull/132
        raise
    except Exception as exc:  # Other error inside method - server error
        logging.exception(exc)
        handler.response = ExceptionResponse(exc, id=request.id, debug=debug)
    finally:
        if is_notification(request):
            handler.response = NotificationResponse()


def safe_call(
    request: Request, methods: Methods, *, debug: bool, extra: Any, serialize: Callable
) -> Response:
    """
    Call a Request, catching exceptions to ensure we always return a Response.

    Args:
        request: The Request object.
        methods: The list of methods that can be called.
        debug: Include more information in error responses.
        serialize: Function that is used to serialize data.

    Returns:
        A Response object.
    """
    with handle_exceptions(request, debug) as handler:
        if isinstance(request.params, list):
            result = call(
                lookup(methods, request.method),
                *([Context(request=request, extra=extra)] + request.params),
            )
        else:
            result = call(
                lookup(methods, request.method),
                Context(request=request, extra=extra),
                **request.params,
            )
        # Ensure value returned from the method is JSON-serializable. If not,
        # handle_exception will set handler.response to an ExceptionResponse
        serialize(result)
        handler.response = SuccessResponse(
            result=result, id=request.id, serialize_func=serialize
        )
    return handler.response


def call_requests(
    requests: Union[Request, Iterable[Request]],
    methods: Methods,
    *,
    extra: Any,
    debug: bool,
    serialize: Callable,
) -> Response:
    """
    Takes a request or list of Requests and calls them.

    Args:
        requests: Request object, or a collection of them.
        methods: The list of methods that can be called.
        debug: Include more information in error responses.
        serialize: Function that is used to serialize data.
    """
    return (
        BatchResponse(
            [
                safe_call(
                    r, methods=methods, debug=debug, extra=extra, serialize=serialize
                )
                for r in requests
            ],
            serialize_func=serialize,
        )
        if isinstance(requests, list)
        else safe_call(
            requests, methods=methods, debug=debug, extra=extra, serialize=serialize
        )
    )


def create_requests(
    requests: Union[Dict, List[Dict]],
) -> Union[Request, Set[Request]]:
    """
    Converts a raw deserialized request dictionary to a Request (namedtuple).

    Args:
        requests: Request dict, or a list of dicts.

    Returns:
        A Request object, or a list of them.
    """
    return (
        [
            Request(
                method=request["method"],
                params=request.get("params", []),
                id=request.get("id", NOID),
            )
            for request in requests
        ]
        if isinstance(requests, list)
        else Request(
            method=requests["method"],
            params=requests.get("params", []),
            id=requests.get("id", NOID),
        )
    )


def dispatch_pure(
    request: str,
    methods: Methods,
    *,
    debug: bool,
    extra: Any,
    serialize: Callable,
    deserialize: Callable,
) -> Response:
    """
    Pure version of dispatch - no logging, no optional parameters.

    Does two things:
        1. Deserializes and validates the string.
        2. Calls each request.

    Args:
        request: The incoming request string.
        methods: Collection of methods that can be called.
        debug: Include more information in error responses.
        extra: Will be included in the context dictionary passed to methods.
        serialize: Function that is used to serialize data.
        deserialize: Function that is used to deserialize data.
    Returns:
        A Response.
    """
    try:
        deserialized = validate(deserialize(request), schema)
    except JSONDecodeError as exc:
        return InvalidJSONResponse(data=str(exc), debug=debug)
    except ValidationError as exc:
        return InvalidJSONRPCResponse(data=None, debug=debug)
    return call_requests(
        create_requests(deserialized),
        methods=methods,
        extra=extra,
        debug=debug,
        serialize=serialize,
    )


@apply_config(config)
def dispatch(
    request: str,
    methods: Optional[Methods] = None,
    *,
    basic_logging: bool = False,
    extra: Optional[dict] = None,
    debug: bool = False,
    trim_log_values: bool = False,
    serialize: Callable = default_serialize,
    deserialize: Callable = default_deserialize,
    **kwargs: Any,
) -> Response:
    """
    Dispatch a request (or requests) to methods.

    This is the main public method, it's the only one with optional params, and the only
    one that can be configured with a config file/env vars.

    Args:
        request: The incoming request string.
        methods: Collection of methods that can be called. If not passed, uses the
            internal methods object.
        extra: Extra data available inside methods (as context.extra).
        debug: Include more information in error responses.
        trim_log_values: Show abbreviated requests and responses in log.
        serialize: Function that is used to serialize data.
        deserialize: Function that is used to deserialize data.

    Returns:
        A Response.

    Examples:
        >>> dispatch('{"jsonrpc": "2.0", "method": "ping", "id": 1}', methods)
    """
    # Use the global methods object if no methods object was passed.
    methods = global_methods if methods is None else methods
    # Add temporary stream handlers for this request, and remove them later
    if basic_logging:
        request_handler, response_handler = add_handlers()
    log_request(request, trim_log_values=trim_log_values)
    response = dispatch_pure(
        request,
        methods,
        debug=debug,
        extra=extra,
        serialize=serialize,
        deserialize=deserialize,
    )
    log_response(str(response), trim_log_values=trim_log_values)
    # Remove the temporary stream handlers
    if basic_logging:
        remove_handlers(request_handler, response_handler)
    return response
