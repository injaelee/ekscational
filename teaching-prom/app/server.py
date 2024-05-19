import asyncio
import aiologger
from aiologger.handlers.streams import AsyncStreamHandler
import random
from fastapi import FastAPI
from prometheus_client import (
  CONTENT_TYPE_LATEST,
  CollectorRegistry,
  Counter,
  Histogram,
  generate_latest,
)
from starlette.responses import Response
import uvicorn
import time
import math


# configure asynchronous logging
#
logger = aiologger.Logger.with_default_handlers()


#
#
metric_registry = CollectorRegistry()


# create the FastAPI instance
#
prom_demo_app = FastAPI(
  title = "Backend API for Metric Generations",
  summary = "The backend application to generate various Prometheus metrics.",
)

# app initialization
#
@prom_demo_app.on_event("startup")
async def startup_event():
  # simulate the constantly running request
  asyncio.create_task(simulate_requests())
  asyncio.create_task(simulate_seasonal_counts())


# Define a route to return a message
#
@prom_demo_app.get("/")
async def root():
  return {"message": "Welcome to FastAPI DEMO with Prometheus metrics!"}


# endpoint for Prometheus to scrape metrics
#
@prom_demo_app.get("/service/metrics")
async def metrics():
  return Response(
    generate_latest(metric_registry),
    media_type = CONTENT_TYPE_LATEST,
  )




"""

# Finer granularity (more buckets, closer together)
  allows for more precise measurements but can increase
  storage and processing costs.

# Coarser granularity (fewer buckets, farther apart)
  reduces storage and processing costs but can obscure details
  and result in less precise measurements.

"""
# define Prometheus histogram
#
REQUEST_DURATION_HISTOGRAM = Histogram(
  "sim_call_request_duration_seconds",
  "Simulated HTTP Request Duration in Seconds",
  labelnames = [
    "method",
    "path",
    "status",
  ],
  unit = "seconds",
  buckets = [0.1, 0.2, 0.5, 1, 2, 5],  # Define custom buckets
  registry = metric_registry,
)


# Function to simulate requests and observe durations
async def simulate_requests():
  while True:
    # normal / gaussian distribution with an avg. 0.3s (300ms) with 0.05s (50 ms) STD
    duration = random.gauss(mu=0.3, sigma=0.05)

    # HTTP response status distribution
    #                    1%   80%    |------10%------|  |---5%---| |---- 4% ----|
    available_status = [101,  200,   201,   202,  204,  400,  405, 500, 501, 504]
    status_weights   = [  1,   80,   7.5,   1.5,    1,    2,    3,   3, 0.5, 0.5]
    status = random.choices(available_status, weights = status_weights, k = 1)[0]

    # log duration / observation
    labeled_req_duration_histogram = REQUEST_DURATION_HISTOGRAM.labels(
      method = "POST",
      path = "/magical/method",
      status = status,
    )
    labeled_req_duration_histogram.observe(duration)

    # note: cannot use 'transitions' with aiologger; ie. %f
    await logger.info("simulating duration:[%f]" % duration)

    # sleep for the simulated duration before the next iteration
    await asyncio.sleep(duration)


def generate_sin_wave(
  time_value: float,
  amplitude: int = 1,
  frequency: int = 1,
  phase_shift: int = 0,
  vertical_shift: int = 0,
):
    """
    Generate a sinusoidal value for a given time t.

    Parameters:
    - time: Time at which to calculate the sinusoidal value (can be a float for higher precision).
    - amplitude: Amplitude of the wave (default is 1).
    - frequency: Frequency of the wave in Hertz (default is 1).
    - phase_shift: Phase shift of the wave in radians (default is 0).
    - vertical_shift: Vertical shift of the wave (default is 0).

    Returns:
    - Sinusoidal value at time t.

    """
    return amplitude * math.sin(
      2 * math.pi * frequency * time_value + phase_shift
    ) + vertical_shift


RHYTHEMIC_REQUEST_COUNTER = Counter(
  "rhythm_component",
  "Counter that goes up in a rhythm",
  labelnames = [
    "component",
    "action",
  ],
  registry = metric_registry,
)


# The Guage metric keeps the value as is until updates or overridden
#
async def simulate_seasonal_counts():
  sampling_rate = 1 # let's keep it at 1 a second
  while True:
    current_time = time.time()
    amp_noise = random.randrange(1, 10)

    v = generate_sin_wave(current_time, amplitude = amp_noise)
    pod_v = max(v, 0) * 100 # ensure v is positive and 100 multiples

    RHYTHEMIC_REQUEST_COUNTER.labels(
      component = "front_page",
      action = "view",
    ).inc(pod_v)

    # note: cannot use 'transitions' with aiologger; ie. %f
    await logger.info("increment by:[%f, %f]" % (v, pod_v))

    await asyncio.sleep(1 / sampling_rate)


# Using Gauge to track state of an entity
#
async def simulate_process_state_change():
  pass


# Run the FastAPI application
if __name__ == "__main__":
  uvicorn.run(
    prom_demo_app,
    host = "0.0.0.0",
    port = 18000, # use the target port defined in the 'prometheus.yml'
  )