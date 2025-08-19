#!/bin/bash
set -e
poetry run python main.py init_db
poetry run python main.py run