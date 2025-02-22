__file__ = variables.get("PA_TASK_NAME")

if str(variables.get("TASK_ENABLED")).lower() != 'true':
  print("Task " + __file__ + " disabled")
  quit()

print("BEGIN " + __file__)

import xml.sax.saxutils as saxutils 
from termcolor import colored
import os, sys, bz2, uuid, json
import random, pickle, sklearn
import numpy as np
import pandas as pd

from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_squared_error
from sklearn.metrics import mutual_info_score
from sklearn.metrics import confusion_matrix
from sklearn.metrics import precision_score
from sklearn.metrics import accuracy_score
from sklearn.metrics import r2_score
from sklearn.metrics.cluster import adjusted_mutual_info_score
from sklearn.metrics.cluster import completeness_score
from sklearn.metrics.cluster import homogeneity_score
from sklearn.metrics.cluster import v_measure_score

input_variables = {
  'task.dataframe_id': None, 
  'task.dataframe_id_test': None,
  'task.algorithm_json': None,
  'task.label_column': None,
  'task.model_id': None
}
for key in input_variables.keys():
  for res in results:
    value = res.getMetadata().get(key)
    if value is not None:
      input_variables[key] = value
      break

dataframe_id = None
if input_variables['task.dataframe_id'] is not None:
  dataframe_id = input_variables['task.dataframe_id']
if input_variables['task.dataframe_id_test'] is not None:
  dataframe_id = input_variables['task.dataframe_id_test']
print("dataframe id (in): ", dataframe_id)

dataframe_json = variables.get(dataframe_id)
assert dataframe_json is not None
dataframe_json = bz2.decompress(dataframe_json).decode()

dataframe = pd.read_json(dataframe_json, orient='split')

is_labeled_data = False
LABEL_COLUMN = variables.get("LABEL_COLUMN")
if LABEL_COLUMN is not None and LABEL_COLUMN is not "":
  is_labeled_data = True
else:
  LABEL_COLUMN = input_variables['task.label_column']
  if LABEL_COLUMN is not None and LABEL_COLUMN is not "":
    is_labeled_data = True

model_id = input_variables['task.model_id']
model_compressed = variables.get(model_id)
model_bin = bz2.decompress(model_compressed)
assert model_bin is not None
print("model id (in): ", model_id)
print("model size: ", sys.getsizeof(model_compressed), " bytes")
print("model size (decompressed): ", sys.getsizeof(model_bin), " bytes")

algorithm_json = input_variables['task.algorithm_json']
assert algorithm_json is not None
algorithm = json.loads(algorithm_json)
#-------------------------------------------------------------
class obj(object):
  def __init__(self, d):
    for a, b in d.items():
      if isinstance(b, (list, tuple)):
        setattr(self, a, [obj(x) if isinstance(x, dict) else x for x in b])
      else:
        setattr(self, a, obj(b) if isinstance(b, dict) else b)
#-------------------------------------------------------------
alg = obj(algorithm)

loaded_model = pickle.loads(model_bin)
dataframe_predictions = None

if is_labeled_data:
  columns = [LABEL_COLUMN]
  dataframe_test = dataframe.drop(columns, axis=1, inplace=False)
  dataframe_label = dataframe.filter(columns, axis=1)
  predictions = list(loaded_model.predict(dataframe_test.values))
  dataframe_predictions = pd.DataFrame(predictions)
  dataframe = dataframe.assign(predictions=dataframe_predictions)

  if alg.type == 'anomaly':
    pred_map = {-1: 1, 1: 0}
    dataframe["predictions"].replace(pred_map, inplace=True)
    predictions = dataframe["predictions"].tolist()
  
  if alg.type != 'clustering' and alg.type != 'anomaly':
    score = loaded_model.score(dataframe_test.values, dataframe_label.values.ravel())
    print("MODEL SCORE: %.2f" % score)

  #-------------------------------------------------------------
  # CLASSIFICATION AND ANOMALY DETECTION SCORE
  #
  if alg.type == 'classification' or alg.type == 'anomaly':
    reponse_good = '&#9989;'
    reponse_bad = '&#10060;'   
    dataframe['results'] = np.where((dataframe[LABEL_COLUMN] == dataframe['predictions']), saxutils.unescape(reponse_good), saxutils.unescape(reponse_bad))
    accuracy_score_result = accuracy_score(dataframe_label.values.ravel(), predictions)
    precision_score_result = precision_score(dataframe_label.values.ravel(), predictions, average='micro')
    confusion_matrix_result = confusion_matrix(dataframe_label.values.ravel(), predictions)
    print("********************** CLASSIFICATION SCORE **********************")
    print("ACCURACY SCORE: %.2f" % accuracy_score_result)
    print("PRECISION SCORE: %.2f" % precision_score_result)
    print("CONFUSION MATRIX:\n%s" % confusion_matrix_result)
    print("*******************************************************************")

  #-------------------------------------------------------------
  # REGRESSION SCORE
  #
  if alg.type == 'regression':
    dataframe['absolute_error'] = dataframe[LABEL_COLUMN] - dataframe['predictions']
    mean_squared_error_result = mean_squared_error(dataframe_label.values.ravel(), predictions)
    mean_absolute_error_result = mean_absolute_error(dataframe_label.values.ravel(), predictions)
    r2_score_result = r2_score(dataframe_label.values.ravel(), predictions) 
    print("********************** REGRESSION SCORES **********************")
    print("MEAN SQUARED ERROR: %.2f" % mean_squared_error_result)
    print("MEAN ABSOLUTE ERROR: %.2f" % mean_absolute_error_result)
    print("R2 SCORE: %.2f" % r2_score_result)
    print("***************************************************************")
  
  #-------------------------------------------------------------
  # CLUSTERING SCORE
  #
  if alg.type == 'clustering':
    adjusted_mutual_info_score_result = adjusted_mutual_info_score(dataframe_label.values.ravel(), predictions)
    completeness_score_result = completeness_score(dataframe_label.values.ravel(), predictions)
    homogeneity_score_result = homogeneity_score(dataframe_label.values.ravel(), predictions)
    mutual_info_score_result = mutual_info_score(dataframe_label.values.ravel(), predictions)
    v_measure_score_result = v_measure_score(dataframe_label.values.ravel(), predictions)
    print("********************** CLUSTERING SCORES **********************")
    print("ADJUSTED MUTUAL INFORMATION: %.2f" % adjusted_mutual_info_score_result)
    print("COMPLETENESS SCORE: %.2f" % completeness_score_result)
    print("HOMOGENEITY METRIC: %.2f" % homogeneity_score_result)
    print("MUTUAL INFORMATION: %.2f" % mutual_info_score_result)
    print("V-MEASURE CLUSTER MEASURE: %.2f" % v_measure_score_result)
    print("***************************************************************")
    #-------------------------------------------------------------
else:
  predictions = list(loaded_model.predict(dataframe.values))
  dataframe_predictions = pd.DataFrame(predictions)
  dataframe = dataframe.assign(predictions=dataframe_predictions)

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
resultMetadata.put("task.algorithm_json", algorithm_json)
resultMetadata.put("task.label_column", LABEL_COLUMN)

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