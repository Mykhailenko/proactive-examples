__file__ = variables.get("PA_TASK_NAME")

if str(variables.get("TASK_ENABLED")).lower() != 'true':
  print("Task " + __file__ + " disabled")
  quit()

print("BEGIN " + __file__)

import sys, bz2, uuid, json
import pandas as pd
import numpy as np

COLUMNS_NAME = variables.get("COLUMNS_NAME")
assert COLUMNS_NAME is not None and COLUMNS_NAME is not ""

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

#-------------------------------------------------------------
def encode_columns(dataframe, columns):
  from sklearn.preprocessing import LabelEncoder
  columns2encode = None
  if isinstance(columns, str):
    columns2encode = [x.strip() for x in columns.split(',')]
  else:
    columns2encode = columns
  assert columns2encode is not None
  encode_map = {}
  dataframe_aux = dataframe.copy()
  for col in columns2encode:
    unique_vector = dataframe[col].unique()
    LE = LabelEncoder()
    LE.fit(unique_vector)
    enc_values = LE.transform(unique_vector)
    enc_map = dict(zip(unique_vector, enc_values))
    dataframe_aux[col] = dataframe[col].map(enc_map)
    encode_map[col] = enc_map
  return dataframe_aux, encode_map

def apply_encoder(dataframe, columns, encode_map):
  columns2encode = None
  if isinstance(columns, str):
    columns2encode = [x.strip() for x in columns.split(',')]
  else:
    columns2encode = columns
  assert columns2encode is not None
  dataframe_aux = dataframe.copy()
  for col in columns2encode:
    col_mapper = encode_map[col]
    dataframe_aux[col] = dataframe[col].map(col_mapper)
  return dataframe_aux
#-------------------------------------------------------------

columns = [x.strip() for x in COLUMNS_NAME.split(',')]
dataframe, encode_map = encode_columns(dataframe, columns)
print(dataframe.head())
print(encode_map)

def default(o):
  if isinstance(o, np.int64):
    return int(o)  
  raise TypeError
encode_map_json = json.dumps(encode_map, default=default)

dataframe_json = dataframe.to_json(orient='split').encode()
compressed_data = bz2.compress(dataframe_json)

dataframe_id = str(uuid.uuid4())
variables.put(dataframe_id, compressed_data)

print("dataframe id (out): ", dataframe_id)
print('dataframe size (original):   ', sys.getsizeof(dataframe_json), " bytes")
print('dataframe size (compressed): ', sys.getsizeof(compressed_data), " bytes")
print(dataframe.head())

resultMetadata.put("task.name", __file__)
resultMetadata.put("task.dataframe_id", dataframe_id)
resultMetadata.put("task.encode_map_json", encode_map_json)

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