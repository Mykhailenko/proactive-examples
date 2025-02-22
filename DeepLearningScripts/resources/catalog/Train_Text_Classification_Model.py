print("BEGIN Train_Text_Classification_Model")

import os
import uuid
import time
import torch
import shutil
import numpy as np
import time, random
import pandas as pd
import torch.nn as nn
from tqdm import tqdm
import dill as pickle
from itertools import *
from torchtext import data
import torch.optim as optim
from torchtext import vocab
from os.path import join, exists
import torch.nn.functional as F
from torch.autograd import Variable
from torchtext.vocab import Vectors, FastText, GloVe, CharNGram


MODEL_ONNX_TYPE = True

#-------------------------evaluate function definition--------------------------
def evaluate(model, test, data_iter, label_field, loss_function, name):
    model.eval()
    avg_loss = 0.0
    truth_res = []
    pred_res = []
    i=0
    acc = 0
    pd.options.display.max_colwidth = 500
    result =  pd.DataFrame(columns=['text','prediction','label'])
    for batch in data_iter:
        i=i+1
        sent, label = batch.text, batch.label
        label.data.sub_(1)
        truth_res += list(label.data)
        model.batch_size = len(test)
        model.hidden = model.init_hidden()
        pred = model(sent)
        pred_label = pred.data.max(1)[1].numpy()
        for i in range(model.batch_size):
            test_fields = vars(test[i])
            test_text = test_fields["text"]
            test_label = test_fields["label"]
            prede_label = pred_label[i]
            gd_label = label[i]
            result.loc[i] = [' '.join(test_text),label_field.vocab.itos[prede_label+1], test_label]
        pred_res += [x for x in pred_label]
        if name is 'test_labeled':
            loss = loss_function(pred, label)
            avg_loss += loss.item()
    if name is 'test_labeled':
        avg_loss /= len(test)
        pred_res = torch.LongTensor(pred_res)
        acc = get_accuracy(truth_res, pred_res)
        print(name + ': loss %.2f acc %.1f' % (avg_loss, acc*100))
    return acc, result

#-------------------------get_accuracy function definition--------------------------
def get_accuracy(truth, pred):
     assert len(truth)==len(pred)
     right = 0
     for i in range(len(truth)):
        if truth[i]==pred[i]:
            right += 1.0
     return right/len(truth)
     
#-------------------------train function definition--------------------------     
def train_epoch_progress(model, train_iter, train, loss_function, optimizer, text_field, label_field, epoch):
    #model.train()
    avg_loss = 0.0
    truth_res = []
    pred_res = []
    count = 0
    for batch in train_iter:
        sent, label = batch.text, batch.label
        label.data.sub_(1)
        truth_res += list(label.data)
        model.batch_size = len(train)
        model.hidden = model.init_hidden()
        pred = model(sent)
        pred_label = pred.data.max(1)[1].numpy()
        pred_res += [np.float64(x) for x in pred_label]
        model.zero_grad()
        loss = loss_function(pred, label)
        avg_loss += loss.item()
        count += 1
        loss.backward()
        optimizer.step()
    avg_loss /= len(train)
    pred_res = torch.LongTensor(pred_res)
    acc = get_accuracy(truth_res, pred_res)
    return avg_loss, acc

#-------------------------main code --------------------------

#--------Get the task parameters--------

#True or False
TRAINABLE = 'False'
#42B, 840B, twitter.27B, 6B
GLOVE = '6B'
LEARNING_RATE = '0.0001'
#Adam,RMS, SGD, Adagrad, Adadelta
OPTIMIZER = 'Adam'
EPOCHS = 2
#L1Loss, MSELoss, CrossEntropyLoss, NLLLoss ....
LOSS_FUNCTION = 'NLLLoss'
#True or False
USE_GPU = 'False'

if 'variables' in locals():
    #True or False
    if variables.get("TRAINABLE") is not None:
        TRAINABLE = variables.get("TRAINABLE")
    else:
        print("TRAINABLE not defined by the user. Using the default value:"+TRAINABLE)
    #42B, 840B, twitter.27B, 6B
    if variables.get("GLOVE") is not None:
        GLOVE = variables.get("GLOVE")
    else:
        print("GLOVE not defined by the user. Using the default value:"+GLOVE)
    if variables.get("LEARNING_RATE") is not None:
        LEARNING_RATE = variables.get("LEARNING_RATE")
    else:
        print("LEARNING_RATE not defined by the user. Using the default value:"+LEARNING_RATE)
    #Adam,RMS, SGD, Adagrad, Adadelta
    if variables.get("OPTIMIZER") is not None:
        OPTIMIZER = variables.get("OPTIMIZER")
    else:
        print("OPTIMIZER not defined by the user. Using the default value:"+OPTIMIZER)
    if variables.get("EPOCHS") is not None:
        EPOCHS = int(variables.get("EPOCHS"))
    else:
        print("EPOCHS not defined by the user. Using the default value:"+EPOCHS)
    #L1Loss, MSELoss, CrossEntropyLoss, NLLLoss ....
    if variables.get("LOSS_FUNCTION") is not None:
        LOSS_FUNCTION = variables.get("LOSS_FUNCTION")
    else:
        print("LOSS_FUNCTION not defined by the user. Using the default value:"+LOSS_FUNCTION)
    if variables.get("EMBEDDING_DIM") is not None:
        EMBEDDING_DIM = int(variables.get('EMBEDDING_DIM'))
    else:
        print("EMBEDDING_DIM not defined by the user. Using the default value:"+EMBEDDING_DIM)
    if variables.get("HIDDEN_DIM") is not None:
        HIDDEN_DIM = int(variables.get('HIDDEN_DIM'))
    else:
        print("HIDDEN_DIM not defined by the user. Using the default value:"+HIDDEN_DIM)
    if variables.get("DROPOUT") is not None:
        DROPOUT = float(variables.get('DROPOUT'))
    else:
        print("DROPOUT not defined by the user. Using the default value:"+DROPOUT)
    if variables.get("USE_GPU") is not None:
        USE_GPU = variables.get('USE_GPU')
    else:
        print("USE_GPU not defined by the user. Using the default value:"+USE_GPU)
    if variables.get("TOKENIZER") is not None:
        TOKENIZER = variables.get('TOKENIZER')
    else:
        print("TOKENIZER not defined by the user. Using the default value:"+TOKENIZER)
    if variables.get("IS_LABELED_DATA") is not None:
        IS_LABELED_DATA = variables.get('IS_LABELED_DATA')
    else:
        print("IS_LABELED_DATA not defined by the user. Using the default value:"+IS_LABELED_DATA)

#--------Define GPU or CPU environment-------- 

if (USE_GPU == 'True' and torch.cuda.is_available()):
    USE_GPU = 1
    DEVICE = 1
    print('GPU ressource will be used')
else:
    USE_GPU = 0
    DEVICE = -1
    print('GPU ressource will not be used')
        
#--------Load Dataset--------
DATASET_ITERATOR_UNL = None
if 'variables' in locals():
    if variables.get("IS_LABELED_DATA") is not None:
        IS_LABELED_DATA = variables.get("IS_LABELED_DATA")
    if IS_LABELED_DATA == 'True':
        DATASET_ITERATOR = variables.get("DATASET_ITERATOR")
        DATASET_PATH = variables.get("DATASET_PATH")
    else:
        DATASET_ITERATOR = variables.get("DATASET_ITERATOR_UNL")
        DATASET_PATH = variables.get("DATASET_PATH_UNL")
    if DATASET_ITERATOR is not None:
        exec(DATASET_ITERATOR)

#--------Load Model---------

if 'variables' in locals():
    if variables.get("MODEL_CLASS") is not None:
        MODEL_CLASS = variables.get("MODEL_CLASS")
    if variables.get("MODEL_DEF") is not None:
        MODEL_DEF = variables.get("MODEL_DEF")
        
if MODEL_CLASS is not None:
    exec(MODEL_CLASS)
if MODEL_DEF is not None:
    exec(MODEL_DEF)
else:
    raise Exception('CLASS MODEL not defined!')
  
#-------Main--------

timestamp = str(int(time.time()))
best_dev_acc = 0.0
best_tr_acc = 0.0

if USE_GPU:
    MODEL = MODEL.cuda()
    
print('Load word embeddings...')

text_field.vocab.load_vectors(vectors=GloVe(name=GLOVE, dim=EMBEDDING_DIM))
MODEL.embeddings.weight.data = text_field.vocab.vectors
if TRAINABLE=='False':
    MODEL.embeddings.weight.requires_grad=False
    
best_model = MODEL

#optimizer = optim.SGD(filter(lambda p: p.requires_grad, model.parameters()), lr=LEARNING_RATE)
OPTIM = """optimizer =  optim."""+OPTIMIZER+"""(filter(lambda p: p.requires_grad, MODEL.parameters()), lr="""+LEARNING_RATE+""")"""
exec(OPTIM)
LOSS ="""loss_function = nn."""+LOSS_FUNCTION+"""()"""
exec(LOSS)

print('Training...')
for epoch in range(EPOCHS):
    print(str(MODEL))
    avg_loss, tr_acc = train_epoch_progress(MODEL, train_iter, train, loss_function, optimizer, text_field, label_field, epoch)
    tqdm.write('Train: loss %.2f acc %.1f' % (avg_loss, tr_acc*100))
    if len(val)>0:
        dev_acc, results = evaluate(MODEL, val, val_iter, label_field, loss_function, 'test_labeled')
        if dev_acc > best_dev_acc:
            best_dev_acc = dev_acc
            BEST_MODEL = MODEL
    else:
        if tr_acc > best_tr_acc:
            best_tr_acc = tr_acc
            BEST_MODEL = MODEL
            
# Get an unique ID
file_id = str(uuid.uuid4())
MODEL_FOLDER = 'text_models/'
MODEL_FOLDER =  os.path.join(MODEL_FOLDER, file_id)
os.makedirs(MODEL_FOLDER, exist_ok=True)

# Save trained model
print('Saving trained model...')
MODEL_FILE= file_id + ".pt"
MODEL_PATH = os.path.join(MODEL_FOLDER, MODEL_FILE)
torch.save(BEST_MODEL, MODEL_PATH)

# Save labels
print('Saving labels to a text file...')
LABELS_FILENAME = file_id + "_label.pkl"
LABELS_PATH = os.path.join(MODEL_FOLDER, LABELS_FILENAME)
pickle.dump(label_field, open(LABELS_PATH,'wb'))

# Save text
print('Saving text vocab to a text file...')
TEXT_FILENAME = file_id + "_text.pkl"
print(TEXT_FILENAME)
TEXT_PATH = os.path.join(MODEL_FOLDER, TEXT_FILENAME)
pickle.dump(text_field, open(TEXT_PATH,'wb'))

# Save onnx trained model
if MODEL_ONNX_TYPE:
  MODEL_ONNX_PATH = None
  print('This network does not yet support the ONNX format!')

    
    
#----------variables to send----------------
# Forward model
try:
    variables.put("MODEL_PATH", MODEL_PATH)
    variables.put("MODEL_ONNX_PATH", MODEL_ONNX_PATH)
    variables.put("LABELS_PATH", LABELS_PATH)
    variables.put("TEXT_PATH", TEXT_PATH)
    variables.put("MODEL_FOLDER", MODEL_FOLDER)
    variables.put("ACCURACY", ACCURACY)
    variables.put("LOSS",LOSS)
    variables.put("DATASET_PATH",DATASET_PATH)
    variables.put("USE_GPU",USE_GPU)
    variables.put("DEVICE",DEVICE)
    variables.put("VOCAB_SIZE", VOCAB_SIZE)
    variables.put("LABEL_SIZE", LABEL_SIZE)
    if IS_LABELED_DATA=='True':
        variables.put("DATASET_ITERATOR",DATASET_ITERATOR)
    else:
        variables.put("DATASET_ITERATOR_UNL",DATASET_ITERATOR_UNL)
except NameError as err:
    print("{0}".format(err))
    print("Warning: this script is running outside from ProActive.")
    pass
  
print("END Train_Text_Classification_Model")