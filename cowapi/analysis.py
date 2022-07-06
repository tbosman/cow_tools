import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from util.dbtools import get_postgres_engine
engine = get_postgres_engine()
pdf = pd.read_sql('select * from cow.rates', engine)

pdf['time'] = pd.to_datetime( pdf['expiry'])
pdf['logprice'] = np.log(pdf['price'])


fig = plt.figure()
fig.clf()

plot_tokens = ['USDC', 'USDT', 'DAI']
graph = sns.lineplot(x='time', y='price', hue ='pair', data=(pdf.sort_values(['pair', 'expiry'])
[
    ~pdf['buysymbol'].isin(['LUSD']) & ~pdf['sellsymbol'].isin(['LUSD'])
    & (pdf['sellsymbol'].isin(plot_tokens) )
    & (pdf['buysymbol'].isin(plot_tokens))
    ]
                                                     ).iloc[:500000])

graph.xaxis.set_major_locator(mdates.HourLocator(interval = 1))
graph.xaxis.set_major_formatter(mdates.DateFormatter('%H'))
graph.set_ylim(0.995, 1.005)

fig.show()


# fig.savefig('images/rates.png')

