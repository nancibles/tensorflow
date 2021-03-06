# Lint as: python3
# Copyright 2019 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
# pylint: disable=redefined-outer-name
# pylint: disable=g-bad-import-order

"""Build and train neural networks."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import datetime
import os
from data_load import DataLoader
from LRF.lr_finder import LRFinder
from CLR.clr_callback import CyclicLR

import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt

logdir = os.path.join("logs\scalars", datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=logdir)

# in order to easily change architecture for number of outputs
num_output = 10 #number of output classes
second_dense_layer = 64

def reshape_function(data, label):
  reshaped_data = tf.reshape(data, [-1, 3, 1])
  return reshaped_data, label


def calculate_model_size(model):
  print(model.summary())
  var_sizes = [
      np.product(list(map(int, v.shape))) * v.dtype.size
      for v in model.trainable_variables
  ]
  print("Model size:", sum(var_sizes) / 1024, "KB")


def build_cnn(seq_length):
  """Builds a convolutional neural network in Keras."""
  model = tf.keras.Sequential([
      tf.keras.layers.Conv2D(
          8, (4, 3),
          padding="same",
          activation="relu",
          input_shape=(seq_length, 3, 1)),  # output_shape=(batch, 128, 3, 8)
      tf.keras.layers.MaxPool2D((3, 3)),  # (batch, 42, 1, 8)
      tf.keras.layers.Dropout(0.1),  # (batch, 42, 1, 8)
      tf.keras.layers.Conv2D(16, (4, 1), padding="same",
                             activation="relu"),  # (batch, 42, 1, 16)
      tf.keras.layers.MaxPool2D((3, 1), padding="same"),  # (batch, 14, 1, 16)
      tf.keras.layers.Dropout(0.1),  # (batch, 14, 1, 16)
      tf.keras.layers.Flatten(),  # (batch, 224)
      tf.keras.layers.Dense(second_dense_layer, activation="relu"),  # (batch, 16) ---> 64
      tf.keras.layers.Dropout(0.1),  # (batch, 16)
      tf.keras.layers.Dense(num_output, activation="softmax")  # (batch, 4) ---> 37
  ])
  model_path = os.path.join("./netmodels", "CNN")
  print("Built CNN.")
  if not os.path.exists(model_path):
    os.makedirs(model_path)
 # model.load_weights("./netmodels/CNN/weights.h5")
  return model, model_path


def build_lstm(seq_length):
  """Builds an LSTM in Keras."""
  model = tf.keras.Sequential([
          tf.keras.layers.Bidirectional(
          tf.keras.layers.LSTM(30),
            input_shape=(seq_length, 3)),  # output_shape=(batch, 44)
          tf.keras.layers.Dense(num_output, activation="sigmoid")  # (batch, 4)
  ])
  model_path = os.path.join("./netmodels", "LSTM")
  print("Built LSTM.")
  if not os.path.exists(model_path):
    os.makedirs(model_path)
  return model, model_path


def load_data(train_data_path, valid_data_path, test_data_path, seq_length):
  data_loader = DataLoader(
      train_data_path, valid_data_path, test_data_path, seq_length=seq_length)
  data_loader.format()
  return data_loader.train_len, data_loader.train_data, data_loader.valid_len, \
      data_loader.valid_data, data_loader.test_len, data_loader.test_data


def build_net(args, seq_length):
  if args.model == "CNN":
    model, model_path = build_cnn(seq_length)
  elif args.model == "LSTM":
    model, model_path = build_lstm(seq_length)
  else:
    print("Please input correct model name.(CNN  LSTM)")
  return model, model_path

def scheduler(epoch, lr):
  if epoch < 10:
    return lr
  else:
    print(lr)
    return lr * tf.math.exp(-0.01)

def train_net(
    model,
    model_path,  # pylint: disable=unused-argument
    train_len,  # pylint: disable=unused-argument
    train_data,
    valid_len,
    valid_data,  # pylint: disable=unused-argument
    test_len,
    test_data,
    kind,
    file_save_name):

  """Trains the model."""
  calculate_model_size(model)
  epochs = 75
  batch_size = 64

  # Cyclic Learning Rate
  clr_step_size = int(4 * (train_len) / batch_size)
  print(clr_step_size)
  base_lr = 1e-4
  max_lr = 1e-2
  mode = 'triangular2'

  # Learning Rate Finder (to find best learning rate)
  start_lr = 1e-3
  end_lr = 1e-1

  callback = tf.keras.callbacks.LearningRateScheduler(scheduler)
  clr_callback = CyclicLR(base_lr=base_lr, max_lr=max_lr, step_size=clr_step_size, mode=mode)
  lrf_callback = LRFinder(min_lr=start_lr, max_lr=end_lr)

  model.compile(
      optimizer="adam",
      loss="sparse_categorical_crossentropy",
      metrics=["accuracy"])
  if kind == "CNN":
    train_data = train_data.map(reshape_function)
    test_data = test_data.map(reshape_function)
    valid_data = valid_data.map(reshape_function)
  test_labels = np.zeros(test_len)
  idx = 0
  for data, label in test_data:  # pylint: disable=unused-variable
    test_labels[idx] = label.numpy()
    idx += 1
  train_data = train_data.batch(batch_size).repeat()
  valid_data = valid_data.batch(batch_size)
  test_data = test_data.batch(batch_size)
  history = model.fit(
      train_data,
      epochs=epochs,
      validation_data=valid_data,
      steps_per_epoch=1000, #1000
      validation_steps=int((valid_len - 1) / batch_size + 1),
      callbacks=[clr_callback, tensorboard_callback])

  loss, acc = model.evaluate(test_data)
  pred = np.argmax(model.predict(test_data), axis=1)

  confusion = tf.math.confusion_matrix(
      labels=tf.constant(test_labels),
      predictions=tf.constant(pred),
      num_classes=num_output)#37) #num_classes=4)
  print(confusion)

  # Plot the training and validation curves
  acc_train = history.history['accuracy']
  acc_val = history.history['val_accuracy']
  loss_train = history.history['loss']
  loss_val = history.history['val_loss']
  epochs = range(0, 75)
  plt.plot(epochs, acc_train, 'g', label='Training Accuracy')
  plt.plot(epochs, acc_val, 'b', label='Validation Accuracy')
  plt.plot(epochs, loss_train, 'g--', label='Training Loss')
  plt.plot(epochs, loss_val, 'b--', label='Validation Loss')
  plt.title('Training and Validation Loss and Accuracy')
  plt.xlabel('Epochs')
  plt.ylabel('Accuracy')
  plt.ylim(0, 1.2)
  plt.legend()
  plt.show()
  print("plotted")

  np.savetxt('confusion_%s.txt'%file_save_name, confusion, fmt='%5s')
  print("Loss {}, Accuracy {}".format(loss, acc))

  # Convert the model to the TensorFlow Lite format without quantization
  converter = tf.lite.TFLiteConverter.from_keras_model(model)
  tflite_model = converter.convert()

  # Save the model to disk
  open("model_%s.tflite"%file_save_name, "wb").write(tflite_model)

  # Convert the model to the TensorFlow Lite format with quantization
  converter = tf.lite.TFLiteConverter.from_keras_model(model)
  converter.optimizations = [tf.lite.Optimize.OPTIMIZE_FOR_SIZE]
  tflite_model = converter.convert()

  # Save the model to disk
  open("model_%s_quantized.tflite"%file_save_name, "wb").write(tflite_model)

  basic_model_size = os.path.getsize("model_%s.tflite"%file_save_name)
  print("Basic model is %d bytes" % basic_model_size)
  quantized_model_size = os.path.getsize("model_%s_quantized.tflite"%file_save_name)
  print("Quantized model is %d bytes" % quantized_model_size)
  difference = basic_model_size - quantized_model_size
  print("Difference is %d bytes" % difference)


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--model", "-m")
  # parser.add_argument("--person", "-p")
  parser.add_argument("--outfile", "-o")
  args = parser.parse_args()

  seq_length = 128

  print("Start to load data...")
  # if args.person == "true":
  #   train_len, train_data, valid_len, valid_data, test_len, test_data = \
  #       load_data("./person_split/train", "./person_split/valid",
  #                 "./person_split/test", seq_length)
  # else:
  train_len, train_data, valid_len, valid_data, test_len, test_data = \
        load_data("./data/train", "./data/valid", "./data/test", seq_length)

  print("Start to build net...")
  model, model_path = build_net(args, seq_length)

  print("Start training...")
  train_net(model, model_path, train_len, train_data, valid_len, valid_data,
            test_len, test_data, args.model, args.outfile)

  print("Training finished!")
