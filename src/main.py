from fastapi import FastAPI

from api.chat import api

app = FastAPI(title="deep_agents",version="0.1.0")


app.include_router(api)