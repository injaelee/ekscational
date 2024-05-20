from aiologger.handlers.streams import AsyncStreamHandler
from fastapi import FastAPI
from prometheus_client import (
  CONTENT_TYPE_LATEST,
  CollectorRegistry,
  Counter,
  Histogram,
  Gauge,
  generate_latest,
  push_to_gateway,
)
from starlette.responses import Response
import aiologger
import asyncio
import math
import random
import time
import uuid
import uvicorn


# configure asynchronous logging
#
logger = aiologger.Logger.with_default_handlers()


# this is defined in our docker-compose.yml
#
PUSH_GATEWAY_URL = "http://localhost:19091"


# prom collector registry for metrics
# - there is a default if you create any metrics without a specific collector registry
#   - added here just to be explicit and demonstrate the registry concept
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

  # jobs for demonstrating the push gateway
  for (job_name, runtime, std) in [
    ("long_running_job", 600, 30),
    ("medium_running_job", 300, 30),
    ("short_running_job", 60, 10),
  ]:
    asyncio.create_task(simulate_process_state_change(
      job_name = job_name,
      base_run_time_in_seconds = runtime,
      std = std,
    ))


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
    REQUEST_DURATION_HISTOGRAM.labels(
      method = "POST",
      path = "/magical/method",
      status = status,
    ).observe(duration)

    # note: cannot use 'transitions' with aiologger; ie. %f
    await logger.info("simulating duration:[%f]" % duration)

    # sleep for the simulated duration before the next iteration
    await asyncio.sleep(duration)


def generate_sin_wave(
  time_value: float,
  amplitude: float = 1.0,
  frequency: float = 1.0,
  phase_shift: float = 0.0,
  vertical_shift: float = 0.0,
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
  sampling_rate = 3.0 # let's keep it at 3 a second
  frequency = 1/600 # complete a cycle every 10 min (=600s)
  while True:
    current_time = time.time()
    amp_noise = random.randrange(1, 10)

    v = generate_sin_wave(
      current_time,
      amplitude = amp_noise,
      frequency = frequency,
    )
    pod_v = max(v, 0) * 100 # ensure v is positive and 100 multiples

    RHYTHEMIC_REQUEST_COUNTER.labels(
      component = "front_page",
      action = "view",
    ).inc(pod_v)

    # note: cannot use 'transitions' with aiologger; ie. %f
    await logger.info("increment by:[%f, %f]" % (v, pod_v))

    await asyncio.sleep(1.0 / sampling_rate)


async def push_job_status(
  job: str,
  status: str,
):
  # note: create registry before every push to the Pushgateway,
  #       ensures each set of metrics is isolcated and prevents the error
  #       'was collected before with the same name and label values'
  #
  job_state_registry = CollectorRegistry()
  Gauge(
    "sim_job_status",
    "Status of simulated job status",
    labelnames = [
      "job",
      "status"
    ],
    registry = job_state_registry,
  ).labels(
    job = job,
    status = status,
  ).set_to_current_time()

  push_to_gateway(
    PUSH_GATEWAY_URL,
    job = job,
    registry = job_state_registry,
  )


# Using Gauge to track state of an entity
#
async def simulate_process_state_change(
  job_name: str,
  base_run_time_in_seconds: float,
  std: float,
):

  while True:
    job_state_registry = CollectorRegistry()
    job_status_gauge = Gauge(
      "sim_job_status",
      "Status of simulated job status",
      labelnames = [
        "status"
      ],
      registry = job_state_registry,
    )
    exec_id = str(uuid.uuid4())

    # mark the start
    job_status_gauge.labels(
      status = "start",
    ).set_to_current_time()
    push_to_gateway(
      PUSH_GATEWAY_URL,
      job = job_name,
      grouping_key = {"exec_id": exec_id},
      registry = job_state_registry,
    )

    run_time_s = random.gauss(mu = base_run_time_in_seconds, sigma = std)
    await logger.info("executing job[%s] with runtime[%f]s" % (job_name, run_time_s))
    await asyncio.sleep(run_time_s)

    # roll the dice for possible outcomes
    possible_outcomes = ["failure", "success"]
    outcome = random.choices(
      possible_outcomes,
      weights = [0.1, 0.9],
      k = 1,
    )[0]

    await logger.info("done job[%s] with runtime[%f]s with result:[%s]" % (
      job_name, run_time_s, outcome))

    # mark the final outcome
    job_status_gauge.labels(
      status = outcome,
    ).set_to_current_time()
    push_to_gateway(
      PUSH_GATEWAY_URL,
      job = job_name,
      grouping_key = {"exec_id": exec_id},
      registry = job_state_registry,
    )


# Run the FastAPI application
if __name__ == "__main__":
  uvicorn.run(
    prom_demo_app,
    host = "0.0.0.0",
    port = 18000, # use the target port defined in the 'prometheus.yml'
  )