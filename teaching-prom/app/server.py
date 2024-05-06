import asyncio
import aiologger
from aiologger.handlers.streams import AsyncStreamHandler
import random
from fastapi import FastAPI
from prometheus_client import (
  Histogram,
  generate_latest,
  CONTENT_TYPE_LATEST,
)
from starlette.responses import Response
import uvicorn


# configure asynchronous logging
#
logger = aiologger.Logger.with_default_handlers()


# create the FastAPI instance
#
prom_demo_app = FastAPI(
  title = "Backend API for Metric Generations",
  summary = "The backend application to generate various Prometheus metrics.",
)


# Define Prometheus histogram
REQUEST_DURATION_HISTOGRAM = Histogram(
  "sim_call_request_duration_seconds",
  "Simulated HTTP Request Duration in Seconds",
  buckets=[0.1, 0.2, 0.5, 1, 2, 5]  # Define custom buckets
)


# Function to simulate requests and observe durations
async def simulate_requests():
  while True:
    # normal / gaussian distribution with an avg. 300 ms with 50 ms STD
    duration = random.gauss(mu=0.3, sigma=0.05)

    # log duration / observation
    REQUEST_DURATION_HISTOGRAM.observe(duration)

    # note: cannot use 'transitions' with aiologger; ie. %f
    await logger.info("simulating duration:[%f]" % duration)
    
    # sleep for the simulated duration before the next iteration
    await asyncio.sleep(duration)


# app initialization
#
@prom_demo_app.on_event("startup")
async def startup_event():
  # simulate the constantly running request
  asyncio.create_task(simulate_requests())


# Define a route to return a message
#
@prom_demo_app.get("/")
async def root():
  return {"message": "Welcome to FastAPI DEMO with Prometheus metrics!"}


# endpoint for Prometheus to scrape metrics
#
@prom_demo_app.get("/service/metrics")
async def metrics():
  return Response(generate_latest(), media_type = CONTENT_TYPE_LATEST)


# Run the FastAPI application
if __name__ == "__main__":
  uvicorn.run(
    prom_demo_app,
    host = "0.0.0.0",
    port = 18000, # use the target port defined in the 'prometheus.yml'
  )