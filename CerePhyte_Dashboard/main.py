import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query

NODEMCU_BASE_URL = "http://192.168.4.1"
NODEMCU_DATA_URL = f"{NODEMCU_BASE_URL}/api/data"

latest_data = {"ok": False, "error": "Waiting for NodeMCU"}
client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    client = httpx.AsyncClient(timeout=1.0)
    task = asyncio.create_task(poll_nodemcu())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await client.aclose()
        client = None


app = FastAPI(title="CerePhyte API", lifespan=lifespan)


async def poll_nodemcu():
    global latest_data
    while True:
        try:
            assert client is not None
            response = await client.get(NODEMCU_DATA_URL)
            response.raise_for_status()
            latest_data = response.json()
        except (httpx.HTTPError, ValueError):
            latest_data = {"ok": False, "error": "NodeMCU unavailable"}
        await asyncio.sleep(0.2)


@app.get("/telemetry")
async def telemetry():
    return latest_data


@app.get("/api/mux1")
async def set_mux1(channel: int = Query(..., ge=0, le=7)):
    assert client is not None
    try:
        response = await client.get(f"{NODEMCU_BASE_URL}/api/mux1?channel={channel}")
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="Failed to communicate with NodeMCU for MUX 1")


@app.get("/api/mux2")
async def set_mux2(channel: int = Query(..., ge=0, le=7)):
    assert client is not None
    try:
        response = await client.get(f"{NODEMCU_BASE_URL}/api/mux2?channel={channel}")
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="Failed to communicate with NodeMCU for MUX 2")