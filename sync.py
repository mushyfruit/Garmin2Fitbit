import os
import datetime
import sys
import traceback

from fitbit_api import Fitbit
from garmin_api import Garmin
import logging_config

logger = logging_config.get_logger(__name__)


def _sync(start_date, end_date):
    garmin = Garmin()

    client_id = os.getenv("GARMIN_CLIENT_ID")
    if client_id is None:
        logger.error("GARMIN_CLIENT_ID environment variable is not set")
        sys.exit(1)

    redirect_uri = os.getenv("GARMIN_REDIRECT_URI") or 'http://127.0.0.1:8080'
    fitbit = Fitbit(client_id, redirect_uri)

    try:
        daily_step_list = garmin.get_steps_for_range(start_date, end_date)
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(error_traceback)
        send_email("Garmin Sync for {0} failed".format(start_date), error_traceback)
        return

    if not daily_step_list:
        logger.error("No steps found for provided date range!")
        send_email("Garmin Sync for {0} failed".format(start_date),
                   "No steps found for provided date range!")
        return

    try:
        for day in daily_step_list:
            step_count = day["totalSteps"]
            calendar_date = day["calendarDate"]
            calories = garmin.get_calories_for_day(calendar_date)
            fitbit.post_step_count(step_count, date=calendar_date, calories=calories)
    except ValueError as e:
        logger_error = str(e)
        body = traceback.format_exc()
        send_email(logger_error, body)


def sync_today():
    today = datetime.date.today()
    _sync(today, today)


def sync_last_week():
    seven_days_ago = datetime.date.today() - datetime.timedelta(days=7)
    today = datetime.date.today().isoformat()
    _sync(seven_days_ago, today)


def sync_last_month():
    month_ago = datetime.date.today() - datetime.timedelta(days=30)
    today = datetime.date.today().isoformat()
    _sync(month_ago, today)


def send_email(subject, body):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    sender_email = os.getenv('SENDER_EMAIL')
    receiver_email = os.getenv('RECEIVER_EMAIL')
    password = os.getenv('APP_PASSWORD')

    if not sender_email or not receiver_email or not password:
        logger.error("Missing sender and receiver emails!")
        return False

    email = MIMEMultipart()
    email["From"] = sender_email
    email["To"] = receiver_email
    email["Subject"] = subject

    email.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, email.as_string())

    logger.info("Email sent!")


if __name__ == '__main__':
    logger.info("---------------------------------------------")
    logger.info("Starting sync for {0}".format(datetime.date.today()))
    sync_today()
    logger.info("Finished sync for {0}".format(datetime.date.today()))
    logger.info("---------------------------------------------")
