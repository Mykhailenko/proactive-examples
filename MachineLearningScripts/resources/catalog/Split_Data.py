__file__ = variables.get("PA_TASK_NAME")

if str(variables.get("TASK_ENABLED")).lower() != 'true':
  print("Task " + __file__ + " disabled")
  quit()

print("BEGIN " + __file__)

import sys, bz2, uuid
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split

TRAIN_SIZE = variables.get("TRAIN_SIZE")
assert TRAIN_SIZE is not None and TRAIN_SIZE is not ""
TRAIN_SIZE = float(TRAIN_SIZE)
test_size = 1 - TRAIN_SIZE

input_variables = {'task.dataframe_id': None}
for key in input_variables.keys():
  for res in results:
    value = res.getMetadata().get(key)
    if value is not None:
      input_variables[key] = value
      break

dataframe_id = input_variables['task.dataframe_id']
print("dataframe id (in): ", dataframe_id)

dataframe_json = variables.get(dataframe_id)
assert dataframe_json is not None
dataframe_json = bz2.decompress(dataframe_json).decode()

dataframe = pd.read_json(dataframe_json, orient='split')

# Split dataframe into train/test sets
X_train, X_test = train_test_split(dataframe, test_size=test_size)

dataframe1 = X_train.reset_index(drop=True)
dataframe2 = X_test.reset_index(drop=True)

dataframe_json1 = dataframe1.to_json(orient='split').encode()
dataframe_json2 = dataframe2.to_json(orient='split').encode()

compressed_data1 = bz2.compress(dataframe_json1)
compressed_data2 = bz2.compress(dataframe_json2)

dataframe_id1 = str(uuid.uuid4())
dataframe_id2 = str(uuid.uuid4())

variables.put(dataframe_id1, compressed_data1)
variables.put(dataframe_id2, compressed_data2)

print("Train set:")
print("dataframe id1 (out): ", dataframe_id1)
print('dataframe size (original):   ', sys.getsizeof(dataframe_json1), " bytes")
print('dataframe size (compressed): ', sys.getsizeof(compressed_data1), " bytes")
print(dataframe1.head())

print("Test set:")
print("dataframe id2 (out): ", dataframe_id2)
print('dataframe size (original):   ', sys.getsizeof(dataframe_json2), " bytes")
print('dataframe size (compressed): ', sys.getsizeof(compressed_data2), " bytes")
print(dataframe2.head())

resultMetadata.put("task.name", __file__)
resultMetadata.put("task.dataframe_id_train", dataframe_id1)
resultMetadata.put("task.dataframe_id_test", dataframe_id2)

LIMIT_OUTPUT_VIEW = variables.get("LIMIT_OUTPUT_VIEW")
LIMIT_OUTPUT_VIEW = 5 if LIMIT_OUTPUT_VIEW is None else int(LIMIT_OUTPUT_VIEW)
if LIMIT_OUTPUT_VIEW > 0:
  print("task result limited to: ", LIMIT_OUTPUT_VIEW, " rows")
  dataframe = dataframe.head(LIMIT_OUTPUT_VIEW).copy()

#============================== Preview results ===============================
#***************# HTML PREVIEW STYLING #***************#
styles = [
    dict(selector="th", props=[("font-weight", "bold"),
                               ("text-align", "center"),
                               ("font-size", "15px"),
                               ("background", "#0B6FA4"),
                               ("color", "#FFFFFF")]),
                               ("padding", "3px 7px"),
    dict(selector="td", props=[("text-align", "right"),
                               ("padding", "3px 3px"),
                               ("border", "1px solid #999999"),
                               ("font-size", "13px"),
                               ("border-bottom", "1px solid #0B6FA4")]),
    dict(selector="table", props=[("border", "1px solid #999999"),
                               ("text-align", "center"),
                               ("width", "100%"),
                               ("border-collapse", "collapse")])
]
#******************************************************#

with pd.option_context('display.max_colwidth', -1):
  result = dataframe.style.set_table_styles(styles).render().encode('utf-8')
  resultMetadata.put("file.extension", ".html")
  resultMetadata.put("file.name", "output.html")
  resultMetadata.put("content.type", "text/html")
#==============================================================================

print("END " + __file__)