import logging

from dotenv import load_dotenv

load_dotenv()

import logfire

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logfire.configure(
    send_to_logfire="if-token-present",
    service_name="tour-gen",
    console=False,
)
logfire.instrument_pydantic_ai()
