"""FastAPI server"""
from fastapi import FastAPI, Request, Response
import uvicorn
from jsonrpcserver import dispatch, method, Ok, Result

app = FastAPI()


@method
def ping() -> Result:
    """JSON-RPC method"""
    return Ok("pong")


@app.post("/")
async def index(request: Request) -> Response:
    """Handle FastAPI request"""
    return Response(dispatch(await request.body()))


if __name__ == "__main__":
    uvicorn.run(app, port=5000)
