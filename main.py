#!/bin/env python
"""The main entry point for the ultimate pollbot."""
from contextlib import contextmanager
import asyncio
import logging

import typer
from sqlalchemy_utils.functions import database_exists, create_database, drop_database

from pollbot.db import engine, base
from pollbot.models import *  # noqa
from pollbot.pollbot import application
from pollbot.config import config

cli = typer.Typer()
logger = logging.getLogger(__name__)


@contextmanager
def wrap_echo(msg: str):
    typer.echo(f"{msg}... ", nl=False)
    yield
    typer.echo("done.")


@cli.command()
def init_db():
    """Initialize the database."""
    if not database_exists(engine.url):
        with wrap_echo("Creating database"):
            create_database(engine.url)

    with wrap_echo("Creating tables"):
        base.metadata.create_all(engine)


@cli.command()
def drop_db():
    """Drop the database."""
    if database_exists(engine.url):
        with wrap_echo("Dropping database"):
            drop_database(engine.url)


@cli.command()
def run():
    """Run the bot."""
    if not database_exists(engine.url):
        typer.echo("Database does not exist. Run init-db first.")
        raise typer.Exit(1)

    typer.echo("Starting the bot in polling mode.")
    application.run_polling()


if __name__ == "__main__":
    cli()
