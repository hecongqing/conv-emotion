import tensorflow as tf
import numpy as np
import pandas as pd
from utils import *
from config import *
from model import *
import os
from sklearn import cross_validation, metrics
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix


os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"   # see issue #152
os.environ["CUDA_VISIBLE_DEVICES"]="1"


session_conf = tf.ConfigProto(
      allow_soft_placement=True,
      log_device_placement=False,
      gpu_options=tf.GPUOptions(per_process_gpu_memory_fraction=0.7))


def main(FLAGS):

	## Loading the train and test data
	trainQueries, trainOwnHistory, trainOtherHistory, trainOwnHistoryMask, trainOtherHistoryMask, trainLabels, \
			valQueries, valOwnHistory, valOtherHistory, valOwnHistoryMask, valOtherHistoryMask, valLabels, \
	        testQueries, testOwnHistory, testOtherHistory, testOwnHistoryMask, testOtherHistoryMask, testLabels = loadData(FLAGS)

	## Update FLAG parameters
	FLAGS.class_size = trainLabels.shape[1]
	FLAGS.input_dims = trainQueries.shape[1]


	## Splitting train into train/val
	# trainQueries, valQueries, trainOwnHistory, valOwnHistory, trainOtherHistory, valOtherHistory, \
	# 	trainOwnHistoryMask, valOwnHistoryMask, trainOtherHistoryMask, valOtherHistoryMask, trainLabels, valLabels = \
	# 	cross_validation.train_test_split(trainQueries, trainOwnHistory, trainOtherHistory, trainOwnHistoryMask, trainOtherHistoryMask, \
	# 	trainLabels, test_size=.2, random_state=1227)

	## Total instances
	n_train = trainQueries.shape[0]  
	n_test = testQueries.shape[0]
	n_val = valQueries.shape[0]
	print("Training/Validation/Testing Size: ", n_train, n_val, n_test)

	## Calculating training batch sizes
	batches = zip(range(0, n_train-FLAGS.batch_size, FLAGS.batch_size), range(FLAGS.batch_size, n_train, FLAGS.batch_size))
	batches = [(start, end) for start, end in batches]
	batches.append( (batches[-1][1], n_train) )
	evalTrainBatches = batches[:]

	## Training of the model

	with tf.Graph().as_default():
		tf.set_random_seed(1234) # Graph level random seed

		sess = tf.Session(config=session_conf) # Defining the session of the Graph
		with sess.as_default():

			model = uniGRUModel(FLAGS, sess)


			max_val_accuracy = 0
			max_test_acc= 0
			min_val_loss = 100000
			tmax_val_test_accuracy = 0
			max_val_test_preds = None


			for t in range(1, FLAGS.epochs+1):


				# Annealing of the learning rate
				if t - 1 <= FLAGS.anneal_stop_epoch:
					anneal = 2.0 ** ((t - 1) // FLAGS.anneal_rate)
				else:
					anneal = 2.0 ** (FLAGS.anneal_stop_epoch // FLAGS.anneal_rate)
				lr = FLAGS.learning_rate / anneal
				# lr = FLAGS.learning_rate

				# Shuffling the batches in each epoch
				# np.random.shuffle(batches)

				total_cost = 0.0
				for start, end in evalTrainBatches:
					histOwn = trainOwnHistory[start:end]
					histOther = trainOtherHistory[start:end]
					histOwnMask = trainOwnHistoryMask[start:end]
					histOtherMask = trainOtherHistoryMask[start:end]
					mask = (histOwnMask + histOtherMask).astype(np.bool)
					query = trainQueries[start:end]
					answers = trainLabels[start:end]
					
					if answers.shape[0] < FLAGS.batch_size:
						histOwn = np.concatenate( (histOwn, np.zeros( (FLAGS.batch_size-histOwn.shape[0],histOwn.shape[1], histOwn.shape[2]) , dtype=np.float32))  , axis=0)
						histOther = np.concatenate( (histOther, np.zeros( (FLAGS.batch_size-histOther.shape[0],histOther.shape[1], histOther.shape[2]) , dtype=np.float32))  , axis=0)
						histOwnMask = np.concatenate( (histOwnMask, np.zeros( (FLAGS.batch_size-histOwnMask.shape[0],histOwn.shape[1]) , dtype=np.float32))  , axis=0)
						histOtherMask = np.concatenate( (histOtherMask, np.zeros( (FLAGS.batch_size-histOtherMask.shape[0],histOwn.shape[1]) , dtype=np.float32))  , axis=0)
						mask = np.concatenate( (mask, np.zeros((FLAGS.batch_size-mask.shape[0],histOwn.shape[1]) , dtype=np.bool))  , axis=0)
						query = np.concatenate( (query, np.zeros( (FLAGS.batch_size-query.shape[0],query.shape[1]) , dtype=np.float32))  , axis=0)
						answers = np.concatenate( (answers, np.zeros( (FLAGS.batch_size-answers.shape[0],answers.shape[1]) , dtype=np.float32))  , axis=0)

					cost_t = model.batch_fit(histOwn, histOther, histOwnMask, histOtherMask, mask, query, answers, lr, FLAGS.dropout_keep_prob, training_mode=True)
					total_cost += cost_t

				# print(total_cost)

				if t % FLAGS.evaluation_interval == 0:

					## Training evaluation

					train_preds = []
					for start, end in batches:
						histOwn = trainOwnHistory[start:end]
						histOther = trainOtherHistory[start:end]
						histOwnMask = trainOwnHistoryMask[start:end]
						histOtherMask = trainOtherHistoryMask[start:end]
						mask = (histOwnMask + histOtherMask).astype(np.bool)
						query = trainQueries[start:end]
						answers = trainLabels[start:end]
						
						if answers.shape[0] < FLAGS.batch_size:
							histOwn = np.concatenate( (histOwn, np.zeros( (FLAGS.batch_size-histOwn.shape[0],histOwn.shape[1], histOwn.shape[2]) , dtype=np.float32))  , axis=0)
							histOther = np.concatenate( (histOther, np.zeros( (FLAGS.batch_size-histOther.shape[0],histOther.shape[1], histOther.shape[2]) , dtype=np.float32))  , axis=0)
							histOwnMask = np.concatenate( (histOwnMask, np.zeros( (FLAGS.batch_size-histOwnMask.shape[0],histOwn.shape[1]) , dtype=np.float32))  , axis=0)
							histOtherMask = np.concatenate( (histOtherMask, np.zeros( (FLAGS.batch_size-histOtherMask.shape[0],histOwn.shape[1]) , dtype=np.float32))  , axis=0)
							mask = np.concatenate( (mask, np.zeros((FLAGS.batch_size-mask.shape[0],histOwn.shape[1]) , dtype=np.bool))  , axis=0)
							query = np.concatenate( (query, np.zeros( (FLAGS.batch_size-query.shape[0],query.shape[1]) , dtype=np.float32))  , axis=0)
							answers = np.concatenate( (answers, np.zeros( (FLAGS.batch_size-answers.shape[0],answers.shape[1]) , dtype=np.float32))  , axis=0)
						loss, pred= model.predict(histOwn, histOther, histOwnMask, histOtherMask, mask, query, FLAGS.dropout_keep_prob, answers, training_mode=False)
						train_preds += list(pred)
						
					
					train_preds = train_preds[:n_train]
					train_acc = metrics.accuracy_score(np.argmax(trainLabels, axis=1), np.array(train_preds))

					print total_cost, train_acc

					
					## Validation evaluation

					# Creating batches for validation
					val_batches = zip(range(0, n_val, FLAGS.batch_size), range(FLAGS.batch_size, n_val+FLAGS.batch_size, FLAGS.batch_size))
					val_batches = [(start, end) for start, end in val_batches]
					val_preds=[]
					val_loss = 0.0

					for start, end in val_batches:
						histOwn = valOwnHistory[start:end]
						histOther = valOtherHistory[start:end]
						histOwnMask = valOwnHistoryMask[start:end]
						histOtherMask = valOtherHistoryMask[start:end]
						mask = (histOwnMask + histOtherMask).astype(np.bool)
						query = valQueries[start:end]
						answers = valLabels[start:end]
						
						if histOwn.shape[0] < FLAGS.batch_size:
							histOwn = np.concatenate( (histOwn, np.zeros( (FLAGS.batch_size-histOwn.shape[0],histOwn.shape[1], histOwn.shape[2]) , dtype=np.float32))  , axis=0)
							histOther = np.concatenate( (histOther, np.zeros( (FLAGS.batch_size-histOther.shape[0],histOther.shape[1], histOther.shape[2]) , dtype=np.float32))  , axis=0)
							histOwnMask = np.concatenate( (histOwnMask, np.zeros( (FLAGS.batch_size-histOwnMask.shape[0],histOwn.shape[1]) , dtype=np.float32))  , axis=0)
							histOtherMask = np.concatenate( (histOtherMask, np.zeros( (FLAGS.batch_size-histOtherMask.shape[0],histOwn.shape[1]) , dtype=np.float32))  , axis=0)
							mask = np.concatenate( (mask, np.zeros((FLAGS.batch_size-mask.shape[0],histOwn.shape[1]) , dtype=np.bool))  , axis=0)
							query = np.concatenate( (query, np.zeros( (FLAGS.batch_size-query.shape[0],query.shape[1]) , dtype=np.float32))  , axis=0)
							answers = np.concatenate( (answers, np.zeros( (FLAGS.batch_size-answers.shape[0],answers.shape[1]) , dtype=np.float32))  , axis=0)
						loss, pred = model.predict(histOwn, histOther, histOwnMask, histOtherMask, mask, query, 1.0, answers, training_mode=False)
						val_preds += list(pred)
						val_loss += loss

					val_preds = val_preds[:n_val]
					val_acc = metrics.accuracy_score(np.argmax(valLabels, axis=1), val_preds)

					## Testing evaluation

					# Creating batches for testing
					test_batches = zip(range(0, n_test, FLAGS.batch_size), range(FLAGS.batch_size, n_test+FLAGS.batch_size, FLAGS.batch_size))
					test_batches = [(start, end) for start, end in test_batches]
					test_preds=[]
					for start, end in test_batches:
						histOwn = testOwnHistory[start:end]
						histOther = testOtherHistory[start:end]
						histOwnMask = testOwnHistoryMask[start:end]
						histOtherMask = testOtherHistoryMask[start:end]
						mask = (histOwnMask + histOtherMask).astype(np.bool)
						query = testQueries[start:end]
						answers = testLabels[start:end]
						
						if histOwn.shape[0] < FLAGS.batch_size:
							histOwn = np.concatenate( (histOwn, np.zeros( (FLAGS.batch_size-histOwn.shape[0],histOwn.shape[1], histOwn.shape[2]) , dtype=np.float32))  , axis=0)
							histOther = np.concatenate( (histOther, np.zeros( (FLAGS.batch_size-histOther.shape[0],histOther.shape[1], histOther.shape[2]) , dtype=np.float32))  , axis=0)
							histOwnMask = np.concatenate( (histOwnMask, np.zeros( (FLAGS.batch_size-histOwnMask.shape[0],histOwn.shape[1]) , dtype=np.float32))  , axis=0)
							histOtherMask = np.concatenate( (histOtherMask, np.zeros( (FLAGS.batch_size-histOtherMask.shape[0],histOwn.shape[1]) , dtype=np.float32))  , axis=0)
							mask = np.concatenate( (mask, np.zeros((FLAGS.batch_size-mask.shape[0],histOwn.shape[1]) , dtype=np.bool))  , axis=0)
							query = np.concatenate( (query, np.zeros( (FLAGS.batch_size-query.shape[0],query.shape[1]) , dtype=np.float32))  , axis=0)
							answers = np.concatenate( (answers, np.zeros( (FLAGS.batch_size-answers.shape[0],answers.shape[1]) , dtype=np.float32))  , axis=0)
						loss, pred = model.predict(histOwn, histOther, histOwnMask, histOtherMask, mask, query, 1.0, answers, training_mode=False)
						test_preds += list(pred)

					test_preds = test_preds[:n_test]
					test_acc = metrics.accuracy_score(np.argmax(testLabels, axis=1), test_preds)
					
					test_cmat = confusion_matrix(np.argmax(testLabels, axis=1), test_preds)
					test_fscore = metrics.classification_report(np.argmax(testLabels, axis=1), test_preds, digits=3)



					print('-----------------------')
					print('Epoch', t)
					print('Total Cost:', total_cost, ', Training Accuracy:', train_acc, ', Validation Accuracy:', val_acc,\
					'Validation Loss:', val_loss, ", Testing Accuracy:", test_acc)

					print('-----------------------')
					if val_loss < min_val_loss:
						max_val_acc = val_acc
						max_test_acc = test_acc
						max_test_preds = test_preds
						max_fscore = test_fscore
						max_test_cmat = test_cmat
						min_val_loss = val_loss

	print("Final metrics:")
	
	print("confusion_matrix (test): ")
	print(max_test_cmat)
	print(max_test_cmat.diagonal()*1.0/max_test_cmat.sum(axis=1))
	print("val accuracy: ", max_val_acc, " test accuracy: ", max_test_acc)
	print("classification report: ")
	print(max_fscore)
	return max_test_acc


if __name__ == "__main__":
	# Select appropriate config from the file config.py
	tf.flags.DEFINE_string("mode", "all", "which modality")
	tf.flags.DEFINE_boolean("context", True, "which kind of features to choose")
	tf.flags.DEFINE_string("nonlin_func", "tf.nn.tanh", "type of nonlinearity")
	tf.flags.DEFINE_float("learning_rate", 0.001, "Learning rate for SGD.")
	tf.flags.DEFINE_float("anneal_rate", 60, "Number of epochs between halving the learnign rate.")
	tf.flags.DEFINE_float("anneal_stop_epoch", 100, "Epoch number to end annealed lr schedule.")
	tf.flags.DEFINE_float("max_grad_norm", 40.0, "Clip gradients to this norm.")
	tf.flags.DEFINE_integer("evaluation_interval", 1, "Evaluate and print results every x epochs")
	tf.flags.DEFINE_integer("batch_size", 512, "Batch size for training.")
	tf.flags.DEFINE_integer("hops", 3, "Number of hops in the Memory Network.")
	tf.flags.DEFINE_integer("epochs", 30, "Number of epochs to train for.")
	tf.flags.DEFINE_integer("embedding_size", 100, "Embedding size for embedding matrices.")
	tf.flags.DEFINE_integer("input_dims", None, "Number of timesteps of the RNN")
	tf.flags.DEFINE_integer("timesteps", 40, "Number of timesteps of the RNN")
	tf.flags.DEFINE_integer("class_size", None, "No. of output classes")
	tf.flags.DEFINE_boolean("nonlin", True, "Use non linearity")
	tf.flags.DEFINE_float("dropout_keep_prob", 0.3, "Percentage of input to keep in dropout")

	# Misc Parameters
	tf.flags.DEFINE_integer("checkpoint_every", 10, "Save model after this many steps (default: 100)")
	tf.flags.DEFINE_integer("num_checkpoints", 10, "Number of checkpoints to store (default: 5)")
	tf.flags.DEFINE_boolean("allow_soft_placement", True, "Allow device soft device placement")
	tf.flags.DEFINE_boolean("log_device_placement", False, "Log placement of ops on devices")
	FLAGS = tf.flags.FLAGS

	main(FLAGS)
	# max_score = 0
	# best_params = []


	# for timesteps in [10, 20, 40]:
	# 	FLAGS.timesteps = timesteps
	# 	for learning_rate in [0.1, 0.01, 0.001]:
	# 		FLAGS.learning_rate = learning_rate
	# 		for nhops in [1,3,5,10,40]:
	# 			FLAGS.hops = nhops
	# 			for emb_dim in [128,512,1024]:
	# 				FLAGS.embedding_size = emb_dim
	# 				for dropout in [0.3, 0.5, 0.8]:
	# 					FLAGS.dropout_keep_prob = dropout
	# 					print "Current params: "
	# 					print FLAGS.timesteps, FLAGS.learning_rate, FLAGS.hops, FLAGS.embedding_size, FLAGS.dropout_keep_prob
	# 					print "Best params:", best_params, "Max Score:", max_score
	# 					score = main(FLAGS)
	# 					if score >= max_score:
	# 						max_score = score
	# 						best_params = [FLAGS.timesteps, FLAGS.learning_rate, FLAGS.hops, FLAGS.embedding_size, FLAGS.dropout_keep_prob]
							








