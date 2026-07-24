FROM public.ecr.aws/lambda/python:3.13

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

CMD ["tour_worker.handler.handler"]
