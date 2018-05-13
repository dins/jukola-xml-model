import pandas as pd
import numpy as np


in_file_name = 'data/grouped_paces_ju.tsv'
df = pd.read_csv(in_file_name, delimiter="\t")
full6 = df.dropna()

df.logp_1 = np.log(df.pace_1)
df.logp_2 = np.log(df.pace_2)
df.logp_3 = np.log(df.pace_3)
df.logp_4 = np.log(df.pace_4)
df.logp_5 = np.log(df.pace_5)
df.logp_6 = np.log(df.pace_6)

df.logmean = np.mean(df.logp_1)
print(df.logmean)
