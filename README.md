Garmin Connect to Fitbit
========================

**Usage** 

Simple utility to manage authorization with the API's and sync daily steps from Garmin Connect to Fitbit. Designed to run as part of a cron job to ensure that the steps stay in sync.

### Usage
1. Register your own app, following the steps on https://dev.fitbit.com/build/reference/web-api/developer-guide/getting-started/
2. Run `pip install -r requirements.txt` to download the relevant dependencies.
3. The script looks for the `FITBIT_CLIENT_ID` and `FITBIT_REDIRECT_URI` environment variables which can be provided directly from your environment or a configuration file.
4. Optionally, the script will look for environment variables for email updates if the Garmin to Fitbit sync fails.
5. Create a cron job to run the script at your desired frequency. 

Example cron to sync from Garmin to Fitbit every 2 hours.
```
0 */2 * * * /home/user/Garmin2Fitbit/example_cron.sh
```
