# FAQ

## How to disable schema validation?

Roughly 40% of dispatching time is spent on schema validation. If you know the
incoming requests are valid, you can disable the validation for better
performance.

```python
dispatch(request, validator=lambda _: None)
```

## How to get the response in other forms

(Todo)

## Which HTTP status code to respond with?

(Todo)
