import os
import datetime
import getpass
import requests

from garth.exc import GarthHTTPError
from garminconnect import Garmin as GarminConnect

import logging_config

logger = logging_config.get_logger(__name__)

_token_store = os.getenv('GARMINTOKENSTORE') or "~/.garminconnect"


class Garmin(object):
    def __init__(self):
        self._garmin_api = init_garmin_api()
        self.today = datetime.date.today().isoformat()

    def get_steps_for_range(self, start=None, end=None):
        if start is None:
            start = self.today
        if end is None:
            end = self.today

        try:
            daily_steps = self._garmin_api.get_daily_steps(start, end)
        except (requests.exceptions.RequestException, GarthHTTPError) as e:
            logger.error("Exception occurred when querying daily step endpoint.")
            logger.error("Switching to fallback step data method...")

            garmin_list = self._daily_step_query_fallback(start, end)
            if garmin_list:
                return garmin_list
            else:
                logger.error("Fallback query failed!")
                raise

        return daily_steps

    def _daily_step_query_fallback(self, start, end):
        query_date = start
        garmin_list = []
        if isinstance(end, str):
            end = datetime.date.fromisoformat(end)

        while query_date <= end:
            data = self._garmin_api.get_steps_data(query_date)
            if data:
                total = 0
                for item in data:
                    total += item["steps"]
                garmin_list.append({"totalSteps": total, "calendarDate": query_date})
                query_date += datetime.timedelta(days=1)
            else:
                return None

        return garmin_list

    def get_calories_for_day(self, day=None):
        if day is None:
            day = self.today

        daily_stats = self._garmin_api.get_stats_and_body(day)
        if daily_stats:
            return int(daily_stats["totalKilocalories"])


def init_garmin_api():
    tokenstore = os.path.expanduser(_token_store)
    if os.path.exists(tokenstore):
        garmin = GarminConnect()
        garmin.login(tokenstore)
        logger.info(f"Logged in successfully with {tokenstore}")
    else:
        email = input("Connect email: ")
        password = getpass.getpass("Connect password: ")

        garmin = GarminConnect(email, password)
        garmin.login()

        garmin.garth.dump(_token_store)
        logger.info(f"OAuth token stored at {tokenstore} for future logins.")

    return garmin
