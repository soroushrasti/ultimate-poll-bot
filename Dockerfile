FROM python:3.12-slim

COPY . /app
WORKDIR /app
RUN pip install poetry
RUN poetry install --no-root

CMD ["poetry", "run", "python", "main.py", "run"]
EXPOSE 8080
