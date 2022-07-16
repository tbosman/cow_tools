import json, requests, logging, time
from datetime import datetime
from util.dbtools import get_postgres_engine
import pandas as pd
api_url = 'https://api.cow.fi/mainnet/api/v1/auction'

time_str = str(datetime.now().replace(microsecond=0))

engine = get_postgres_engine()

while True:
    print('Round')
    auction_json = requests.get(api_url).content
    auction = json.loads(auction_json)
    time_str = str(datetime.now().replace(microsecond=0))
    timestamp = time.time()
    orders = auction['orders']
    for o in orders:
        o['timestamp'] = timestamp
        o['block'] = auction['block']
        o['latestSettlementBlock'] = auction['latestSettlementBlock']

    old_pdf = pd.read_sql('select * from cow.orders', engine)

    pdf = pd.DataFrame(orders)
    pdf = pd.concat([pdf, old_pdf])

    pdf.columns = [col.lower() for col in pdf.columns]

    pdf.to_sql('orders', engine, if_exists='append', schema='cow', index=False)
    print(f'time: {time_str} block: {auction["block"]} | latestSB: {auction["latestSettlementBlock"]} '
          f'hash: {hash(json.dumps(sorted([ (o["validTo"], o) for o in orders ], key=lambda x: x[0])))} norders: {len(auction["orders"])}')
    time.sleep(10)
