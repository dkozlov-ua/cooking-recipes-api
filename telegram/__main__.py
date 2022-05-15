import logging

import click

from telegram.bot import bot


@click.command()
@click.option('--loglevel', help='Level for logging', default='INFO',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False))
def main(loglevel: str) -> None:
    logger_level = getattr(logging, loglevel.upper())
    bot.infinity_polling(logger_level=logger_level)


# pylint: disable=no-value-for-parameter
main()
