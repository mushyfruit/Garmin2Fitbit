import os
import logging


def get_logger(name):
    log_path = os.path.expanduser('~/.cron_jobs/logs/')
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        filename=os.path.join(log_path, 'garmin_sync.log'),
                        filemode='a')

    return logging.getLogger(name)
