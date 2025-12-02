import sys
import os
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timezone, timedelta
from pprint import pprint
from dotenv import load_dotenv

load_dotenv()

def convert_timestamp_ms(timestamp_ms):
    timestamp_s = timestamp_ms / 1000
    vn_tz = timezone(timedelta(hours=7))
    dt_vn = datetime.fromtimestamp(timestamp_s, tz=vn_tz)
    return dt_vn

id='bitcoin'
key= os.getenv('COIN_GECKO_API')
def daily_crypto(id=id, key=key) :
    url = 'https://api.coingecko.com/api/v3/coins/{}/ohlc?vs_currency=usd&days=1&precision=full'.format(id)
    headers = {
        'Accepts': 'application/json',
        'x-cg-demo-api-key': key
    }
    print(url, key)
    session = Session()
    session.headers.update(headers)
    try:
        response = session.get(url)
        data = json.loads(response.text)
        for dt in data:
            dt[0] = convert_timestamp_ms(dt[0]).strftime("%Y-%m-%d %H:%M:%S %Z%z")
            dt[1] = 'open: ' + "{:.3f}".format(dt[1])
            dt[2] = 'high: ' + "{:.3f}".format(dt[2])
            dt[3] = 'low: ' + "{:.3f}".format(dt[3])
            dt[4] = 'close: ' + "{:.3f}".format(dt[4])
        pprint(data)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
}

with DAG(
    dag_id="daily_crypto",
    default_args=default_args,
    catchup=False,
    schedule='46-50 * * * *',
    tags=[ "crypto"],
) as dag:

    daily_bitcoin = PythonOperator(
        task_id="daily_bitcoin",
        python_callable=daily_crypto,
        op_kwargs={'id': 'bitcoin', 'key': key},
    )

    daily_eth = PythonOperator(
        task_id="daily_eth",
        python_callable=daily_crypto,
        op_kwargs={'id': 'colend', 'key': key},
    )

    [daily_bitcoin, daily_eth]