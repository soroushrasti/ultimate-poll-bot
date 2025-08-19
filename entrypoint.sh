#!/bin/bash
set -e
poetry run python main.py init-db
poetry run python main.py run