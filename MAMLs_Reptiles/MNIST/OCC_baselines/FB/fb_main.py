# -*- coding: utf-8 -*-
import tensorflow as tf
import numpy as np
import argparse
import os
import random 
import pickle
import json
from imblearn.over_sampling import RandomOverSampler
from fb_class import FB



class Bunch(object):
    def __init__(self, adict):
        self.__dict__.update(adict)


def extract_args_from_json(config_file, args_dict):
    with open(config_file) as f:
        summary_dict = json.load(fp=f)

    for key in summary_dict.keys():
        args_dict[key] = summary_dict[key]

    return args_dict


def load_MNIST(test_task_idx, val_task_idx):

    """ load the required MT-MNIST dataset.

        Parameters
        ----------
        test_task_idx : int
            index of the meta-testing task.
        val_task_idx : int
            index of the meta-validation task.


        Returns
        -------
        mtl_train_tasks : dict
            meta-training tasks.
        val_task : dict
            meta-validation task.
        test_task_finetune_sets : dict
            list of different training sets sampled from the task considered.
        test_task_test_set : dict
            test set of the meta-testing task.

    """

    base_path = '/home/USER/Documents'
    if (not (os.path.exists(base_path))):
        base_path = '/home/ubuntu/Projects'
    data_path = base_path + '/MAML/input_data/FB_MNIST_val' + str(val_task_idx) + '_test' + str(test_task_idx)+'/'
    train_data_file = open(data_path + 'fb_train_data_val_' + str(val_task_idx) + '_test_' + str(test_task_idx) + '.txt', 'rb')
    train_data = pickle.load(train_data_file)

    data_path = base_path + '/MAML/input_data/MNIST_val' + str(val_task_idx) + '_test' + str(test_task_idx)+'/'


    val_task_file = open(data_path + 'val_task_val_'+ str(val_task_idx) + '_test_' + str(test_task_idx) + '.txt', 'rb')
    val_task = pickle.load(val_task_file)


    test_task_test_set_file = open(data_path + 'test_task_test_sets_val_'+ str(val_task_idx) + '_test_' + str(test_task_idx) + '.txt', 'rb')
    test_task_test_set = pickle.load(test_task_test_set_file)

    test_task_finetune_sets_file = open(data_path + 'test_task_finetune_sets_val_'+ str(val_task_idx) + '_test_' + str(test_task_idx) + '.txt', 'rb')
    test_task_finetune_sets = pickle.load(test_task_finetune_sets_file)

    return train_data, val_task, test_task_finetune_sets, test_task_test_set




# def sample_random_train_batch(train_data, batch_size):
#     """sample a batch from each sampled training task.

#     Parameters
#     ----------
#     train_tasks : dict
#         contains features and labels of datapoints of all training tasks.
#     batch_size : int
#         batch size.

#     Returns
#     -------
#     X_batch : numpy array
#         features of the batch sampled from each training task.
#     Y_batch : numpy array
#         labels of the batch sampled from each training task.

#     """

#     X_train_sampled = []
#     Y_train_sampled = []


#     sampled_tr_idxs = random.sample(range(0, len(train_data['X'])), batch_size)
#         X_train_sampled.append(task_X_train[sampled_tr_idxs])
#         Y_train_sampled.append(task_Y_train[sampled_tr_idxs])

#     X_batch = np.array(X_train_sampled)
#     Y_batch = np.array(Y_train_sampled)


#     return X_batch, Y_batch


def sample_random_val_finetune_data(val_task, K, cir, val_normal_indexes, val_anomalous_indexes):
    """samples K datapoints from the validation task.

    Parameters
    ----------
    val_task : dict
        contains the data of the validation task.
    K : int
        size of the finetuning set.
    cir : int
        class-imbalance rate (cir) of the target task (and therefore we sample the finetuning sets of the val tasks to have this same cir).
    val_normal_indexes : list
        indices of normal data samples of the validation task
    val_anomalous_indexes : list
        indices of anomalous data samples of the validation task

    Returns
    -------
    val_X_sampled : array
        features of the K datapoints sampled from the validation task 
        in the current multitask learning iteration.
    val_Y_sampled : array
        labels of the K datapoints sampled from the validation task 
        in the current multitask learning iteration.

    """

    n_needed_normal_val = int(K*cir)
    n_needed_anomalous_val = K - n_needed_normal_val
    val_normal_idxs = random.sample(val_normal_indexes, n_needed_normal_val)
    val_anomalous_idxs = random.sample(val_anomalous_indexes, n_needed_anomalous_val)
    val_idxs = val_normal_idxs
    val_idxs+=val_anomalous_idxs

    val_X_sampled, val_Y_sampled = val_task["finetune_X"][val_idxs], val_task["finetune_Y"][val_idxs]

    return val_X_sampled, val_Y_sampled


def main(args):

    seed = 123

    random.seed(seed)
    np.random.seed(seed)
    tf.set_random_seed(seed)

    cir_inner_loop_list = [float(i) for i in args.cir_inner_loop_list.split(' ')]
    K_list = [int(i) for i in args.K_list.split(' ')]

    train_data, val_task, test_task_finetune_sets, test_task_test_sets = load_MNIST(args.test_task_idx, args.val_task_idx)

    val_normal_indexes = list(np.nonzero(val_task['finetune_Y'] == 0)[0])
    val_anomalous_indexes = list(np.nonzero(val_task['finetune_Y'] == 1)[0])

    sess = tf.InteractiveSession()
    model = FB(sess, args, seed)

    summary = False
    if(args.summary_dir):
        summary = True


    if(summary):
        loddir_path = './summaries_FB'
        if (not (os.path.exists(loddir_path))):
            os.mkdir(loddir_path)
        if (not (os.path.exists(os.path.join(loddir_path, model.summary_dir)))):
            os.mkdir(os.path.join(loddir_path, model.summary_dir))
        train_writer = tf.summary.FileWriter(
            os.path.join(loddir_path, model.summary_dir) + '/train')

        val_task_writers = {}

        for K in K_list:
            for cir in cir_inner_loop_list:
                val_task_writers[str(K)+'_'+str(cir)] = tf.summary.FileWriter(
                    os.path.join(loddir_path, model.summary_dir) + '/val_task_K_' +str(K)+'_cir_'+str(cir))


    sess.run(tf.global_variables_initializer())
    sess.run(tf.local_variables_initializer())


    min_val_task_test_loss = {}
    min_val_task_test_loss_mtl_epoch = {}
    min_val_task_test_loss_finetune_epoch= {}

    for K in K_list:
        for cir in cir_inner_loop_list:
            min_val_task_test_loss[str(K)+'_'+str(cir)] =10000
            min_val_task_test_loss_mtl_epoch[str(K)+'_'+str(cir)] = -1
            min_val_task_test_loss_finetune_epoch[str(K)+'_'+str(cir)] = -1
            

    # FB-training
    for epoch in range(args.train_epochs+1):
        sampled_tr_idxs = random.sample(range(0, len(train_data['X'])), args.batch_size)
        X_train, Y_train = train_data['X'][sampled_tr_idxs], train_data['Y'][sampled_tr_idxs]
        
        train_loss, train_acc, tr_summaries = model.train_op(X_train, Y_train, epoch)
        if(summary and (epoch % model.summary_interval == 0)):
            print('Train epoch: ', epoch, ' train_acc: ', train_acc)
            train_writer.add_summary(tr_summaries, epoch)
            train_writer.flush()

        if(epoch % model.val_task_finetune_interval == 0):
            for K in K_list:
                for cir in cir_inner_loop_list:

                    if((K==10 and cir ==0.99) or (K<10 and cir not in [0.5, 1.0])):
                        pass
                    else:

                        X_val_finetune, Y_val_finetune = sample_random_val_finetune_data(val_task, K, cir, val_normal_indexes, val_anomalous_indexes)
                        
                        # if(cir > 0.5 and cir < 1.0):
                        #     ros = RandomOverSampler(random_state=seed)
                        #     X_val_finetune_reshaped = np.reshape(X_val_finetune, (X_val_finetune.shape[0], -1))
                        #     X_val_finetune_reshaped, Y_val_finetune_reshaped = ros.fit_resample(X_val_finetune_reshaped, np.squeeze(Y_val_finetune))
                        #     X_val_finetune = np.reshape(X_val_finetune_reshaped, (-1, 28, 28))
                        #     Y_val_finetune = np.expand_dims(Y_val_finetune_reshaped, -1)

                        min_val_task_epoch, val_test_loss = model.val_op(X_val_finetune, Y_val_finetune, val_task['test_X'], val_task['test_Y'], K, cir, epoch)


                        if(val_test_loss < min_val_task_test_loss[str(K)+'_'+str(cir)]):
                            print('----- model saved for K=', K, ' and cir=', cir)
                            model.saver.save(
                                model.sess,
                                model.checkpoint_path +
                                model.summary_dir +
                                "_restore_val_task_test_loss_" + str(K) + '_' + str(cir) + "/model.ckpt")
                            min_val_task_test_loss[str(K)+'_'+str(cir)] = val_test_loss
                            min_val_task_test_loss_mtl_epoch[str(K)+'_'+str(cir)] = epoch
                            min_val_task_test_loss_finetune_epoch[str(K)+'_'+str(cir)] = min_val_task_epoch

                        # if(summary):
                        #     val_task_writer = val_task_writers[str(K)+'_'+str(cir)]
                        #     val_task_writer.add_summary(val_task_summaries, epoch)
                        #     val_task_writer.flush()

    if(summary):
        train_writer.close()
        for K in K_list:
            for cir in cir_inner_loop_list:
                val_task_writers[str(K)+'_'+str(cir)].close()

    
    # test_task_finetune_writers, test_task_test_writers = {}, {}

    test_set = test_task_test_sets
    feed_dict_test_task_test = {model.X: test_set["test_X"], model.Y_oc: test_set["test_Y"]}


    for K in K_list:
        for cir in cir_inner_loop_list:
            if((K==10 and cir ==0.99) or (K<10 and cir not in [0.5, 1.0])):
                pass
            else:
                finetune_sets = test_task_finetune_sets[str(K)][str(cir)]
                loss_list, acc_list, prec_list, rec_list, spec_list, f1_list, auc_pr_list, epoch_list = [], [], [], [], [], [], [], []

                if((K == 100) and (cir < 1.0)): 
                    for finetune_set_index, finetune_set in enumerate(finetune_sets):

                        # if(summary):
                        #     test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)] = tf.summary.FileWriter(
                        #         os.path.join(loddir_path, model.summary_dir) + '/test_task_finetune_K_' +str(K)+'_cir_'+str(cir) + '_fset_'+str(finetune_set_index))

                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)] = tf.summary.FileWriter(
                        #         os.path.join(loddir_path, model.summary_dir) + '/test_task_test_K_' +str(K)+'_cir_'+str(cir) + '_fset_'+str(finetune_set_index))

                        #     sess.run(tf.local_variables_initializer()) 
                        #     test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(test_summaries, 0)
                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
            
                        model.saver.restore(
                            model.sess,
                            model.checkpoint_path +
                            model.summary_dir +
                            "_restore_val_task_test_loss_" + str(K) + '_' + str(cir) + "/model.ckpt")
                        
                        finetune_X, finetune_Y = finetune_set["finetune_X"], finetune_set["finetune_Y"]

                        # splitting finetune data into finetune and val sets and perform early stopping
                        normal_indexes, anomalous_indexes = list(np.nonzero(finetune_Y == 0)[0]), list(np.nonzero(finetune_Y == 1)[0])
                        finetune_normal_idxs = random.sample(normal_indexes, int(len(normal_indexes)*model.finetune_data_percentage))
                        finetune_anomalous_idxs = random.sample(anomalous_indexes, np.maximum(1,int(len(anomalous_indexes)*model.finetune_data_percentage)))
                        finetune_indexes = []
                      
                        finetune_indexes += finetune_normal_idxs
                        finetune_indexes += finetune_anomalous_idxs

                        val_normal_idxs = [index for index in normal_indexes if index not in finetune_normal_idxs]
                        val_anomalous_idxs = [index for index in anomalous_indexes if index not in finetune_anomalous_idxs]
                        val_indexes = []
                        val_indexes += val_normal_idxs
                        val_indexes += val_anomalous_idxs

                        if(len(val_anomalous_idxs) < 1 and len(finetune_anomalous_idxs) > 0):
                            val_indexes += finetune_anomalous_idxs

                        val_X = finetune_X[val_indexes]
                        val_Y = finetune_Y[val_indexes]

                        finetune_X = finetune_X[finetune_indexes]
                        finetune_Y = finetune_Y[finetune_indexes]

                        if(cir > 0.5 and cir < 1.0):
                            ros = RandomOverSampler(random_state=seed)
                            finetune_X_reshaped = np.reshape(finetune_X, (finetune_X.shape[0], -1))
                            finetune_X_reshaped, finetune_Y_reshaped = ros.fit_resample(finetune_X_reshaped, np.squeeze(finetune_Y))
                            finetune_X = np.reshape(finetune_X_reshaped, (-1, 28, 28))
                            finetune_Y = np.expand_dims(finetune_Y_reshaped, -1)

                            ros = RandomOverSampler(random_state=seed)
                            val_X_reshaped = np.reshape(val_X, (val_X.shape[0], -1))
                            val_X_reshaped, val_Y_reshaped = ros.fit_resample(val_X_reshaped, np.squeeze(val_Y))
                            val_X = np.reshape(val_X_reshaped, (-1, 28, 28))
                            val_Y = np.expand_dims(val_Y_reshaped, -1)

                        val_feed_dict = {model.X: val_X, model.Y_oc: val_Y}


                        min_val_loss = 10000
                        min_val_loss_epoch = -1
                        early_stopping = 0

                        for finetune_epoch in range(1, args.finetune_epochs+1):
                            finetune_loss = model.finetune_op(finetune_X, finetune_Y)
                            val_loss = model.test_loss.eval(val_feed_dict) 
                            if(val_loss < min_val_loss):
                                early_stopping = 0
                                min_val_loss = val_loss
                                min_val_loss_epoch = finetune_epoch
                                model.saver.save(
                                    model.sess,
                                    model.checkpoint_path +
                                    model.summary_dir +
                                    "_restore_val_set_test_task_finetune_with_valset_" + str(finetune_set_index) +"/model.ckpt")


                            else:
                                early_stopping+=1

                            if(finetune_epoch%finetune_summary_interval == 1):

                                sess.run(tf.local_variables_initializer()) 
                                test_loss, test_acc, test_precision, test_recall, test_specificity, test_f1_score, test_auc_pr = model.sess.run([model.test_loss, model.my_acc, model.my_precision, model.my_recall, model.my_specificity, model.my_f1_score, model.my_auc_pr], feed_dict=feed_dict_test_task_test) 

                                # if(summary):
                                #     test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(finetune_summaries, finetune_epoch)
                                #     test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
                                #     sess.run(tf.local_variables_initializer()) 
                                #     test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                                #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(test_summaries, finetune_epoch)
                                #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
                            
                            if(early_stopping > model.early_stopping_val):
                                break


                        model.saver.restore(
                            model.sess,
                            model.checkpoint_path +
                            model.summary_dir +
                            "_restore_val_set_test_task_finetune_with_valset_" + str(finetune_set_index) +"/model.ckpt")

                        sess.run(tf.local_variables_initializer()) 
                        test_loss, test_acc, test_precision, test_recall, test_specificity, test_f1_score, test_auc_pr = model.sess.run([model.test_loss, model.my_acc, model.my_precision, model.my_recall, model.my_specificity, model.my_f1_score, model.my_auc_pr], feed_dict=feed_dict_test_task_test) 


                        loss_list.append(test_loss)
                        acc_list.append(test_acc)
                        prec_list.append(test_precision)
                        rec_list.append(test_recall)
                        spec_list.append(test_specificity)
                        f1_list.append(test_f1_score)
                        auc_pr_list.append(test_auc_pr)
                        epoch_list.append(min_val_loss_epoch)


                        # if(summary):
                        #     sess.run(tf.local_variables_initializer()) 
                        #     test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(test_summaries, min_val_task_test_loss_finetune_epoch[str(K)+'_'+str(cir)] + 500)
                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].close()
  
                else:

                    if(min_val_task_test_loss_finetune_epoch[str(K)+'_'+str(cir)] <= 50):
                        finetune_summary_interval = 1
                    else:
                        finetune_summary_interval = 50


                    for finetune_set_index, finetune_set in enumerate(finetune_sets):

                        # if(summary):
                        #     test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)] = tf.summary.FileWriter(
                        #         os.path.join(loddir_path, model.summary_dir) + '/test_task_finetune_K_' +str(K)+'_cir_'+str(cir) + '_fset_'+str(finetune_set_index))

                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)] = tf.summary.FileWriter(
                        #         os.path.join(loddir_path, model.summary_dir) + '/test_task_test_K_' +str(K)+'_cir_'+str(cir) + '_fset_'+str(finetune_set_index))

                            # sess.run(tf.local_variables_initializer()) 
                            # test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                            # test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(test_summaries, 0)
                            # test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
            
                        model.saver.restore(
                            model.sess,
                            model.checkpoint_path +
                            model.summary_dir +
                            "_restore_val_task_test_loss_" + str(K) + '_' + str(cir) + "/model.ckpt")


                        finetune_X, finetune_Y = finetune_set["finetune_X"], finetune_set["finetune_Y"]
                        if(cir > 0.5 and cir < 1.0):
                            ros = RandomOverSampler(random_state=seed)
                            finetune_X_reshaped = np.reshape(finetune_X, (finetune_X.shape[0], -1))
                            finetune_X_reshaped, finetune_Y_reshaped = ros.fit_resample(finetune_X_reshaped, np.squeeze(finetune_Y))
                            finetune_X = np.reshape(finetune_X_reshaped, (-1, 28, 28))
                            finetune_Y = np.expand_dims(finetune_Y_reshaped, -1)

                        if(model.batch_size < K):
                            batch_idxs = random.sample(range(0, finetune_X.shape[0]), model.batch_size)

                            for finetune_epoch in range(1,min_val_task_test_loss_finetune_epoch[str(K)+'_'+str(cir)]+1):
                                finetune_loss = model.finetune_op(finetune_X[batch_idxs], finetune_Y[batch_idxs])
                                if(finetune_epoch%finetune_summary_interval == 1):
                                    sess.run(tf.local_variables_initializer()) 
                                    test_loss, test_acc, test_precision, test_recall, test_specificity, test_f1_score, test_auc_pr = model.sess.run([model.test_loss, model.my_acc, model.my_precision, model.my_recall, model.my_specificity, model.my_f1_score, model.my_auc_pr], feed_dict=feed_dict_test_task_test) 

                                    # if(summary):
                                    #     test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(finetune_summaries, finetune_epoch)
                                    #     test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
                                    #     sess.run(tf.local_variables_initializer()) 
                                    #     test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                                    #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(test_summaries, finetune_epoch)
                                    #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
                                    
                        else:
                            for finetune_epoch in range(1,min_val_task_test_loss_finetune_epoch[str(K)+'_'+str(cir)]+1):
                                finetune_loss = model.finetune_op(finetune_X, finetune_Y)
                                if(finetune_epoch%finetune_summary_interval == 1):
                                    sess.run(tf.local_variables_initializer()) 
                                    test_loss, test_acc, test_precision, test_recall, test_specificity, test_f1_score, test_auc_pr = model.sess.run([model.test_loss, model.my_acc, model.my_precision, model.my_recall, model.my_specificity, model.my_f1_score, model.my_auc_pr], feed_dict=feed_dict_test_task_test) 

                                    # if(summary):
                                    #     test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(finetune_summaries, finetune_epoch)
                                    #     test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
                                    #     sess.run(tf.local_variables_initializer()) 
                                    #     test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                                    #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(test_summaries, finetune_epoch)
                                    #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
                                    

                        sess.run(tf.local_variables_initializer()) 
                        test_loss, test_acc, test_precision, test_recall, test_specificity, test_f1_score, test_auc_pr = model.sess.run([model.test_loss, model.my_acc, model.my_precision, model.my_recall, model.my_specificity, model.my_f1_score, model.my_auc_pr], feed_dict=feed_dict_test_task_test) 


                        loss_list.append(test_loss)
                        acc_list.append(test_acc)
                        prec_list.append(test_precision)
                        rec_list.append(test_recall)
                        spec_list.append(test_specificity)
                        f1_list.append(test_f1_score)
                        auc_pr_list.append(test_auc_pr)
                        epoch_list.append(min_val_task_test_loss_finetune_epoch[str(K)+'_'+str(cir)])


                        # if(summary):
                        #     sess.run(tf.local_variables_initializer()) 
                        #     test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].add_summary(test_summaries, min_val_task_test_loss_finetune_epoch[str(K)+'_'+str(cir)] + 500)
                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].flush()
                        #     test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(finetune_set_index)].close()



                test_results_dict = {}
                test_results_dict['test_loss'] = loss_list
                test_results_dict['acc'] = acc_list
                test_results_dict['prec'] = prec_list
                test_results_dict['rec'] = rec_list
                test_results_dict['spec'] = spec_list
                test_results_dict['f1'] = f1_list
                test_results_dict['auc_pr'] = auc_pr_list
                test_results_dict['epoch'] = epoch_list

                results_dir_path = './results/'
                if (not (os.path.exists(results_dir_path))):
                    os.mkdir(results_dir_path)
                filename = args.summary_dir + '_K_' + str(K) + '_cir_' + str(int(100*cir)) +'.txt'
                with open(results_dir_path+filename, 'wb') as file:
                    pickle.dump(test_results_dict, file)


                print('average metrics for K = ', K, ' cir = ', str(cir))

                print(
                    ' test_loss : ',
                    np.mean(loss_list),
                    ' acc : ',
                    np.mean(acc_list),
                    ' prec : ',
                    np.mean(prec_list),
                    ' recall : ',
                    np.mean(rec_list),
                    ' specificity : ',
                    np.mean(spec_list),
                    ' f1_score : ',
                    np.mean(f1_list),
                    ' auc_pr : ',
                    np.mean(auc_pr_list))

                print('min metrics')

                print(
                    ' acc : ',
                    np.amin(acc_list),
                    ' prec : ',
                    np.amin(prec_list),
                    ' recall : ',
                    np.amin(rec_list),
                    ' specificity : ',
                    np.amin(spec_list),
                    ' f1_score : ',
                    np.amin(f1_list),
                    ' auc_pr : ',
                    np.amin(auc_pr_list))

                print('max metrics')

                print(
                    ' acc : ',
                    np.amax(acc_list),
                    ' prec : ',
                    np.amax(prec_list),
                    ' recall : ',
                    np.amax(rec_list),
                    ' specificity : ',
                    np.amax(spec_list),
                    ' f1_score : ',
                    np.amax(f1_list),
                    ' auc_pr : ',
                    np.amax(auc_pr_list))

                n_test_tasks = len(acc_list)
                print('ci95 metrics - number of test tasks :', n_test_tasks)

                print(
                    ' acc : ',
                    1.96*np.std(acc_list)/np.sqrt(n_test_tasks),
                    ' prec : ',
                    1.96*np.std(prec_list)/np.sqrt(n_test_tasks),
                    ' recall : ',
                    1.96*np.std(rec_list)/np.sqrt(n_test_tasks),
                    ' specificity : ',
                    1.96*np.std(spec_list)/np.sqrt(n_test_tasks),
                    ' f1_score : ',
                    1.96*np.std(f1_list)/np.sqrt(n_test_tasks),
                    ' auc_pr : ',
                    1.96*np.std(auc_pr_list)/np.sqrt(n_test_tasks)
                    )



    sess.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Multi-task training on multiple tasks then transfer learning (finetuning) on a test task/ purpose: benchmark with Model-Agnostic Meta-Learning (MAML)')
    parser.add_argument(
        '-filters',
        type=str,
        metavar='',
        help='number of filters for each convolutional layer e.g. "32 32 32 32"')
    parser.add_argument(
        '-kernel_sizes',
        type=str,
        metavar='',
        help='kernel sizes for each convolutional layer e.g. "3 3 3 3"')
    parser.add_argument(
        '-dense_layers',
        type=str,
        metavar='',
        help='size of each dense layer of the model e.g. "256 128 64 64"')
    parser.add_argument(
        '-lr',
        type=float,
        metavar='',
        help='learning rate (for pretraining and finetuning')
    parser.add_argument(
        '-train_epochs',
        type=int,
        metavar='',
        help='number of training epochs for the training tasks')
    parser.add_argument(
        '-finetune_epochs',
        type=int,
        metavar='',
        help='number of finetuning epochs (only for test task)')
    parser.add_argument(
        '-batch_size',
        type=int,
        metavar='',
        help='number of data points sampled for training')
    parser.add_argument(
        '-K_list',
        type=str,
        metavar='',
        help='number of finetuning examples in the test task')
    parser.add_argument(
        '-cir_inner_loop_list',
        type=str,
        metavar='',
        help='percentage of positive examples in the test task')
    parser.add_argument(
        '-test_task_idx',
        type=int,
        metavar='',
        help='index of the test task') 
    parser.add_argument(
        '-val_task_idx',
        type=int,
        metavar='',
        help='index of the val task') 
    parser.add_argument(
        '-summary_dir',
        type=str,
        metavar='',
        help=('name of the doirectory where the summaries should be saved. '
              'set to False, if summaries are not needed '))
    parser.add_argument('-config_file', 
        type=str, 
        default="None")


    args = parser.parse_args()

    args_dict = vars(args)
    if args.config_file is not "None":
        args_dict = extract_args_from_json(args.config_file, args_dict)

    for key in list(args_dict.keys()):

        if str(args_dict[key]).lower() == "true":
            args_dict[key] = True
        elif str(args_dict[key]).lower() == "false":
            args_dict[key] = False


    args = Bunch(args_dict)

    main(args)
