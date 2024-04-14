import os
import json
import hashlib
import base64
import datetime

import requests
from urllib.parse import urlencode

from urllib.parse import urlparse, parse_qs
from oauthlib.oauth2 import WebApplicationClient

import logging_config

logger = logging_config.get_logger(__name__)


class Fitbit(object):
    def __init__(self, client_id, redirect_uri):
        self.client = FitBitOAuth2Handler(client_id, redirect_uri=redirect_uri)
        self.today = datetime.datetime.now().strftime('%Y-%m-%d')

    def get_daily_activities(self):
        today_date = datetime.datetime.now().strftime('%Y-%m-%d')
        url = "https://api.fitbit.com/1/user/-/activities/date/{0}.json".format(today_date)
        response = self.client.make_request(url, method='GET')
        print(response)

    def get_all_possible_activities(self):
        url = "https://api.fitbit.com/1/activities.json"
        response = self.client.make_request(url, method='GET')
        for item in response["categories"]:
            items = item["activities"]
            for activity in items:
                print(activity["name"], activity["id"])

    def post_step_count(self, step_count, date=None, calories=None, start_time=None, duration=None, retry_count=0):
        walk_id = 90013

        # Default to posting for today.
        post_date = date or self.today

        # Default activity to begin right at 12:01am.
        activity_start = start_time or "00:01"

        # Fallback to a 1-hour-long activity
        duration = duration or "3600000"

        params = {
            "distance": step_count,
            "distanceUnit": "Steps",
            "date": post_date,
            "activityId": walk_id,
            "startTime": activity_start,
            "durationMillis": duration,
        }

        if calories is not None:
            params.update({"manualCalories": calories})

        base_url = "https://api.fitbit.com/1/user/-/activities.json?"
        url = base_url + urlencode(params)
        response, status = self.client.make_request(url, method='POST')
        if status == 200 and retry_count <= 1:
            logger.info(f"Deleting existing step entry for {post_date} in order to update.")
            status_code = self.delete_entry(response)
            if status_code == 204:
                self.post_step_count(step_count,
                                     date=date, calories=calories,
                                     start_time=start_time, duration=duration,
                                     retry_count=retry_count + 1)
        elif status < 400:
            logger.info(f"Synced {step_count} steps for {post_date} to Fitbit.")
        else:
            error_string = f"Returned status code {status} for {post_date} to Fitbit. error_msg_body: {response}"
            logger.error(error_string)
            raise ValueError(error_string)

    def delete_entry(self, existing):
        activity_id = existing.get("activityLog", {}).get("logId", None)
        if not activity_id:
            return None

        url = "https://api.fitbit.com/1/user/-/activities/{0}.json".format(activity_id)
        _, status_code = self.client.make_request(url, method='DELETE')
        if status_code == 204:
            logger.info("Deleted existing entry for updating step count.")

        return status_code


class FitBitOAuth2Handler(object):
    def __init__(self, client_id, redirect_uri):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = "activity heartrate location nutrition profile settings sleep social weight"

        self.code_verifier = generate_code_verifier()
        self.code_challenge = generate_code_challenge(self.code_verifier)

        self.state = get_oauth2_authorization_state()

        self.client = WebApplicationClient(client_id, redirect_uri=redirect_uri)
        self.authorization_base_url = 'https://www.fitbit.com/oauth2/authorize'
        self.authorization_token_url = 'https://api.fitbit.com/oauth2/token'

        self.token = self.get_authorization_token()
        if self.token is None:
            self.authorize_token_url()
        else:
            logger.debug('Authorization token is %s' % self.token)

    def get_authorization_token(self):
        token_store = os.path.expanduser("~/.fitbit_token")
        if os.path.exists(os.path.join(token_store, "fitbit_oauth_token.json")):
            with open(os.path.join(token_store, "fitbit_oauth_token.json"), 'r') as f:
                token_data = json.load(f)
            return token_data

    def make_request(self, url, data=None, method=None, **kwargs):
        data = data or {}
        method = method or ('POST' if data else 'GET')
        headers = self.get_authorization_headers()

        try:
            response = requests.request(method, url, headers=headers, data=data, **kwargs)
            if response.ok:
                if method == 'DELETE' and response.status_code == 204:
                    logger.info("Successfully deleted entry for %s", url)
                    return None, response.status_code
                return response.json(), response.status_code
            else:
                logger.error("Request failed with status %d: %s", response.status_code, response.text)
                return response.json() if response.text else {}, response.status_code
        except requests.exceptions.RequestException as e:
            logger.error("Failed when making %s request to %s: %s", method, url, str(e))
            return {}, 500

    def get_authorization_headers(self):
        access_token = self.token["access_token"]
        return {"Authorization": f"Bearer {access_token}"}

    def authorize_token_url(self):
        authorization_data = self.client.prepare_authorization_request(
            self.authorization_base_url,
            scope=self.scope,
            state=self.state,
            code_challenge_method='S256',
            code_challenge=self.code_challenge
        )
        authorization_url = authorization_data[0]
        print("Visit this URL to authorize:", authorization_url)
        authorization_response = input('Enter the full callback URL: ')

        self.fetch_token(authorization_response)

    def fetch_token(self, authorization_response):
        parsed_url = urlparse(authorization_response)
        query_params = parse_qs(parsed_url.query)
        auth_code = query_params.get('code', [None])[0]

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        body = {
            'client_id': self.client_id,
            'grant_type': 'authorization_code',
            'code': auth_code,
            'code_verifier': self.code_verifier,
            'state': self.state,
        }

        response = requests.post(
            self.authorization_token_url,
            headers=headers,
            data=body)

        token = response.json()
        if response.status_code != 200:
            raise Exception(f"Failed to fetch token: {token.get('error_description', token)}")

        # Store the token for later use.
        dump_token(token)

        self.token = token
        return token


def generate_code_verifier(length=64):
    """ Generate a secure random code verifier. """
    token = os.urandom(length)
    return base64.urlsafe_b64encode(token).decode('utf-8').rstrip('=')


def generate_code_challenge(code_verifier):
    """ Generate a code challenge based on the code verifier. """
    sha256 = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(sha256).decode('utf-8').rstrip('=')


def get_oauth2_authorization_state(random_bytes=os.urandom(64)):
    return hashlib.sha256(random_bytes).hexdigest()


def dump_token(token):
    dir_path = os.path.expanduser("~/.fitbit_token")
    os.makedirs(dir_path, exist_ok=True)
    with open(os.path.join(dir_path, "fitbit_oauth_token.json"), 'w') as token_file:
        json.dump(token, token_file, indent=4)
