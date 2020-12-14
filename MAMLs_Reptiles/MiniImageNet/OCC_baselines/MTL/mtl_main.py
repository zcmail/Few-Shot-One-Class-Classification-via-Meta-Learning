# -*- coding: utf-8 -*-
import tensorflow as tf
import numpy as np
import argparse
import os
import random 
import pickle
import json
from imblearn.over_sampling import RandomOverSampler
from mtl_class import MTL



class Bunch(object):
    def __init__(self, adict):
        self.__dict__.update(adict)


def extract_args_from_json(config_file, args_dict):
    with open(config_file) as f:
        summary_dict = json.load(fp=f)

    for key in summary_dict.keys():
        args_dict[key] = summary_dict[key]

    return args_dict


def load_MiniImageNet():

    """ load the MiniImageNet tasks.

        Returns
        -------
        mtl_train_tasks : dict
            meta-training tasks.
        val_tasks : list
            meta-validation task.
        test_tasks : list
            meta-testing tasks.

    """

    base_path = '/home/USER/Documents'
    if (not (os.path.exists(base_path))):
        base_path = '/home/ubuntu/Projects'
    if (not (os.path.exists(base_path))):
        base_path = '/home/USER/Projects'
    if (not (os.path.exists(base_path))):
        base_path = '/home/USER/Projects'
        
    data_path = base_path + '/MAML/input_data/miniImageNet/'
    train_tasks_file = open(data_path + 'miniImageNet_train_tasks.txt', 'rb')
    train_tasks = pickle.load(train_tasks_file)

    val_tasks_file = open(data_path + 'miniImageNet_val_tasks.txt', 'rb')
    val_tasks = pickle.load(val_tasks_file)

    test_tasks_file = open(data_path + 'miniImageNet_test_tasks.txt', 'rb')
    test_tasks = pickle.load(test_tasks_file)

    mtl_train_tasks = {}
    mtl_train_tasks['X'] = [np.concatenate((train_task['X_inner'], train_task['X_outer']), axis=0) for train_task in train_tasks]
    mtl_train_tasks['Y'] = [np.concatenate((train_task['Y_inner'], train_task['Y_outer']), axis=0) for train_task in train_tasks]

    return mtl_train_tasks, val_tasks, test_tasks


def sample_random_train_batch(train_tasks, train_normal_indexes_list, train_anomalous_indexes_list, batch_size):
    """sample a batch from each sampled training task.

    Parameters
    ----------
    train_tasks : dict
        contains features and labels of datapoints of all training tasks.
    train_normal_indexes_list: list
        contains the indices of the normal examples of each meta-training task.
    train_anomalous_indexes_list: list
        contains the indices of the anomalous examples of each meta-training task.
    batch_size : int
        batch size.

    Returns
    -------
    X_batch : numpy array
        features of the batch sampled from each training task.
    Y_batch : numpy array
        labels of the batch sampled from each training task.

    """

    X_train_sampled = []
    Y_train_sampled = []
    n_needed_normal = n_needed_anomalous = int(batch_size*0.5)

    for task_idx in range(len(train_tasks['Y'])):
        task_X_train = train_tasks['X'][task_idx]
        task_Y_train = train_tasks['Y'][task_idx]
        sampled_tr_normal_idxs = random.sample(train_normal_indexes_list[task_idx], n_needed_normal)
        sampled_tr_anomalous_idxs = random.sample(train_anomalous_indexes_list[task_idx], n_needed_anomalous)
        sampled_tr_idxs = []
        sampled_tr_idxs += sampled_tr_normal_idxs
        sampled_tr_idxs+=sampled_tr_anomalous_idxs        
        X_train_sampled.append(task_X_train[sampled_tr_idxs])
        Y_train_sampled.append(task_Y_train[sampled_tr_idxs])

    X_batch = np.array(X_train_sampled)
    Y_batch = np.array(Y_train_sampled)

    return X_batch, Y_batch


def sample_random_val_finetune_data(val_tasks, K, cir, val_finetune_normal_indexes_list, val_finetune_anomalous_indexes_list):
    """sample finetuning sets from the validation tasks.

    Parameters
    ----------
    val_tasks : list
        contains the data of the validation tasks.
    K : int
        size of the finetuning set.
    cir : int
        class-imbalance rate (cir) of the target task (and therefore we sample the finetuning sets of the val tasks to have this same cir).
    val_finetune_normal_indexes_list : list
        indices of normal data samples of the validation tasks
    val_finetune_anomalous_indexes_list : list
        indices of anomalous data samples of the validation tasks

    Returns
    -------
    val_X_sampled_list : list
        features of the K datapoints sampled from the validation task 
        in the current multitask learning iteration.
    val_Y_sampled_list : list
        labels of the K datapoints sampled from the validation task 
        in the current multitask learning iteration.

    """

    n_needed_normal_val = int(K*cir)
    n_needed_anomalous_val = K - n_needed_normal_val
    val_X_sampled_list, val_Y_sampled_list = [], []

    for val_task_idx in range(len(val_tasks)):
        val_normal_idxs = random.sample(val_finetune_normal_indexes_list[val_task_idx], n_needed_normal_val)
        val_anomalous_idxs = random.sample(val_finetune_anomalous_indexes_list[val_task_idx], n_needed_anomalous_val)
        val_idxs = val_normal_idxs
        val_idxs+=val_anomalous_idxs
        val_X_sampled, val_Y_sampled = val_tasks[val_task_idx]["X_inner"][val_idxs], val_tasks[val_task_idx]["Y_inner"][val_idxs]
        val_X_sampled_list.append(val_X_sampled)
        val_Y_sampled_list.append(np.expand_dims(val_Y_sampled, -1))

    return val_X_sampled_list, val_Y_sampled_list


def main(args):

    seed = 123

    random.seed(seed)
    np.random.seed(seed)
    tf.set_random_seed(seed)

    cir_inner_loop_list = [float(i) for i in args.cir_inner_loop_list.split(' ')]
    K_list = [int(i) for i in args.K_list.split(' ')]

    train_tasks, val_tasks, test_tasks = load_MiniImageNet()

    train_normal_indexes_list, train_anomalous_indexes_list = [], []
    for i in range (len(train_tasks['Y'])):
        train_normal_indexes_list.append(list(np.where(train_tasks['Y'][i] == 0)[0]))
        train_anomalous_indexes_list.append(list(np.where(train_tasks['Y'][i] == 1)[0]))
    
    val_finetune_normal_indexes_list, val_finetune_anomalous_indexes_list = [], []
    for i in range (len(val_tasks)):
        val_finetune_normal_indexes_list.append(list(np.where(val_tasks[i]['Y_inner'] == 0)[0]))
        val_finetune_anomalous_indexes_list.append(list(np.where(val_tasks[i]['Y_inner'] == 1)[0]))
    
    test_finetune_normal_indexes_list, test_finetune_anomalous_indexes_list = [], []
    for i in range (len(test_tasks)):
        test_finetune_normal_indexes_list.append(list(np.where(test_tasks[i]['Y_inner'] == 0)[0]))
        test_finetune_anomalous_indexes_list.append(list(np.where(test_tasks[i]['Y_inner'] == 1)[0]))
    

    sess = tf.InteractiveSession()
    input_shape = train_tasks['X'][0][0].shape
    n_train_tasks = len(train_tasks['X'])
    model = MTL(sess, args, seed, input_shape, n_train_tasks)

    summary = False
    if(args.summary_dir):
        summary = True

    if(summary):
        loddir_path = './summaries_MTL'
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

    min_val_tasks_avg_test_loss = {}
    min_val_tasks_avg_test_loss_mtl_epoch = {}
    min_val_tasks_avg_test_loss_finetune_epoch= {}

    for K in K_list:
        for cir in cir_inner_loop_list:
            min_val_tasks_avg_test_loss[str(K)+'_'+str(cir)] =10000
            min_val_tasks_avg_test_loss_mtl_epoch[str(K)+'_'+str(cir)] = -1
            min_val_tasks_avg_test_loss_finetune_epoch[str(K)+'_'+str(cir)] = -1
            


    # MTL-training
    for epoch in range(args.train_epochs+1):
        X_train, Y_train = sample_random_train_batch(train_tasks, train_normal_indexes_list, train_anomalous_indexes_list, args.batch_size)
        train_loss, tr_summaries = model.train_op(X_train, np.expand_dims(Y_train,-1), epoch)
        if(summary and (epoch % model.summary_interval == 0)):
            train_writer.add_summary(tr_summaries, epoch)
            train_writer.flush()
        if(epoch % model.val_task_finetune_interval == 0):
            for K in K_list:
                for cir in cir_inner_loop_list:
                    if((K==100 and cir ==0.90) or (K<100 and cir not in [0.5, 1.0])):
                        pass
                    else:
                        X_val_finetune_list, Y_val_finetune_list = sample_random_val_finetune_data(val_tasks, K, cir, val_finetune_normal_indexes_list, val_finetune_anomalous_indexes_list)
                        val_metrics_list = []
                        for val_task_idx, (X_val_finetune, Y_val_finetune) in enumerate(zip(X_val_finetune_list, Y_val_finetune_list)):
                            if(cir > 0.5 and cir < 1.0):
                                ros = RandomOverSampler(random_state=seed)
                                X_val_finetune_reshaped = np.reshape(X_val_finetune, (X_val_finetune.shape[0], -1))
                                X_val_finetune_reshaped, Y_val_finetune_reshaped = ros.fit_resample(X_val_finetune_reshaped, np.squeeze(Y_val_finetune))
                                X_val_finetune = np.reshape(X_val_finetune_reshaped, (-1, 84, 84, 3))
                                Y_val_finetune = np.expand_dims(Y_val_finetune_reshaped, -1)

                            val_task_summaries, min_val_task_epoch, val_test_loss = model.val_op(X_val_finetune, Y_val_finetune, val_tasks[val_task_idx]['X_outer'], np.expand_dims(val_tasks[val_task_idx]['Y_outer'],-1), K, cir, epoch)
                            val_metrics_list.append([min_val_task_epoch, val_test_loss])

                        avg_val_metrics = np.mean(val_metrics_list, axis=0)

                        if(avg_val_metrics[1] < min_val_tasks_avg_test_loss[str(K)+'_'+str(cir)]):
                            model.saver.save(
                                model.sess,
                                model.checkpoint_path +
                                model.summary_dir +
                                "_restore_val_task_test_loss_" + str(K) + '_' + str(cir) + "/model.ckpt")
                            min_val_tasks_avg_test_loss[str(K)+'_'+str(cir)] = avg_val_metrics[1]
                            min_val_tasks_avg_test_loss_mtl_epoch[str(K)+'_'+str(cir)] = epoch
                            min_val_tasks_avg_test_loss_finetune_epoch[str(K)+'_'+str(cir)] = int(avg_val_metrics[0])

                        if(summary):
                            val_task_writer = val_tasks_writers[str(K)+'_'+str(cir)]
                            val_task_writer.add_summary(val_task_summaries, epoch)
                            val_task_writer.flush()


    if(summary):
        train_writer.close()
        for K in K_list:
            for cir in cir_inner_loop_list:
                val_tasks_writers[str(K)+'_'+str(cir)].close()

    
    test_task_finetune_writers, test_task_test_writers = {}, {}
    n_finetune_sets = 20
    for K in K_list:
        for cir in cir_inner_loop_list:
            if((K==100 and cir ==0.90) or (K<100 and cir not in [0.5, 1.0])):
                pass
            else:
                loss_list, acc_list, prec_list, rec_list, spec_list, f1_list, auc_pr_list, epoch_list = [], [], [], [], [], [], [], []
                n_needed_normal_finetune = int(K*cir)
                n_needed_anomalous_finetune = K - n_needed_normal_finetune 
                if((K in [100, 1000]) and (cir < 1.0)): 
                    for test_task_idx, test_task in enumerate(test_tasks):
                        test_feed_dict = {model.X_finetune: test_task["X_outer"], model.Y_finetune: np.expand_dims(test_task["Y_outer"], -1)}
                        normal_indexes = test_finetune_normal_indexes_list[test_task_idx]
                        anomalous_indexes = test_finetune_normal_indexes_list[test_task_idx]
                        for fset_idx in range(n_finetune_sets):
                            if(summary):
                                test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)] = tf.summary.FileWriter(
                                    os.path.join(loddir_path, model.summary_dir) + '/test_task_finetune_K_' +str(K)+'_cir_'+str(cir) + '_test_task_idx_'+str(test_task_idx)+'_fset_'+str(fset_idx))
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)] = tf.summary.FileWriter(
                                    os.path.join(loddir_path, model.summary_dir) + '/test_task_test_K_' +str(K)+'_cir_'+str(cir) + '_test_task_idx_'+str(test_task_idx)+'_fset_'+str(fset_idx))
                                sess.run(tf.local_variables_initializer()) 
                                test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(test_summaries, 0)
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()

                            model.saver.restore(
                                model.sess,
                                model.checkpoint_path +
                                model.summary_dir +
                                "_restore_val_task_test_loss_" + str(K) + '_' + str(cir) + "/model.ckpt")
                            
                            finetune_X, finetune_Y = test_task["X_inner"], np.expand_dims(test_task["Y_inner"], -1)

                            # sampled for the present finetune set
                            available_normal_idxs = random.sample(normal_indexes, n_needed_normal_finetune) 
                            available_anomalous_idxs = random.sample(anomalous_indexes, n_needed_anomalous_finetune) 

                            finetune_normal_idxs = random.sample(available_normal_idxs, int(len(available_normal_idxs)*model.finetune_data_percentage))
                            finetune_anomalous_idxs = random.sample(available_anomalous_idxs, np.maximum(1,int(len(available_anomalous_idxs)*model.finetune_data_percentage)))
                            finetune_indexes = []
                          
                            finetune_indexes += finetune_normal_idxs
                            finetune_indexes += finetune_anomalous_idxs

                            val_normal_idxs = [index for index in available_normal_idxs if index not in finetune_normal_idxs]
                            val_anomalous_idxs = [index for index in available_anomalous_idxs if index not in finetune_anomalous_idxs]
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
                                finetune_X = np.reshape(finetune_X_reshaped, (-1, 84,84,3))
                                finetune_Y = np.expand_dims(finetune_Y_reshaped, -1)

                                ros = RandomOverSampler(random_state=seed)
                                val_X_reshaped = np.reshape(val_X, (val_X.shape[0], -1))
                                val_X_reshaped, val_Y_reshaped = ros.fit_resample(val_X_reshaped, np.squeeze(val_Y))
                                val_X = np.reshape(val_X_reshaped, (-1, 84,84,3))
                                val_Y = np.expand_dims(val_Y_reshaped, -1)

                            val_feed_dict = {model.X_finetune: val_X, model.Y_finetune: val_Y}

                            min_val_loss = 10000
                            min_val_loss_epoch = -1
                            early_stopping = 0

                            for finetune_epoch in range(1, args.finetune_epochs+1):
                                if(model.batch_size < finetune_X.shape[0]):
                                    batch_idxs = random.sample(range(0, finetune_X.shape[0]), model.batch_size)
                                    finetune_loss, finetune_summaries = model.finetune_op(finetune_X[batch_idxs], finetune_Y[batch_idxs])
                                else:
                                    finetune_loss, finetune_summaries = model.finetune_op(finetune_X, finetune_Y)
                                val_loss = model.test_loss.eval(val_feed_dict) 
                                if(val_loss < min_val_loss):
                                    early_stopping = 0
                                    min_val_loss = val_loss
                                    min_val_loss_epoch = finetune_epoch
                                    model.saver.save(
                                        model.sess,
                                        model.checkpoint_path +
                                        model.summary_dir +
                                        "_restore_val_set_test_task_finetune_with_valset_test_task_idx_"+str(test_task_idx)+'_fset_'+ str(fset_idx) +"/model.ckpt")
                                else:
                                    early_stopping+=1

                                if(summary and finetune_epoch%finetune_summary_interval == 1): 
                                    test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(finetune_summaries, finetune_epoch)
                                    test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()
                                    sess.run(tf.local_variables_initializer()) 
                                    test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                                    test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(test_summaries, finetune_epoch)
                                    test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()
                            
                                if(early_stopping > model.early_stopping_val):
                                    break     

                            model.saver.restore(
                                model.sess,
                                model.checkpoint_path +
                                model.summary_dir +
                                "_restore_val_set_test_task_finetune_with_valset_test_task_idx_"+str(test_task_idx)+'_fset_'+ str(fset_idx) +"/model.ckpt")

                            sess.run(tf.local_variables_initializer()) 
                            test_loss, test_acc, test_precision, test_recall, test_specificity, test_f1_score, test_auc_pr = model.sess.run([model.test_loss, model.test_acc, model.test_precision, model.test_recall, model.test_specificity, model.test_f1_score, model.test_auc_pr], feed_dict=feed_dict_test_task_test) 
                            loss_list.append(test_loss)
                            acc_list.append(test_acc)
                            prec_list.append(test_precision)
                            rec_list.append(test_recall)
                            spec_list.append(test_specificity)
                            f1_list.append(test_f1_score)
                            auc_pr_list.append(test_auc_pr)
                            epoch_list.append(min_val_loss_epoch)
                            if(summary):
                                sess.run(tf.local_variables_initializer()) 
                                test_summaries = model.sess.run(model.merged_test, feed_dict_test_task_test)
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(test_summaries, min_val_task_test_loss_finetune_epoch[str(K)+'_'+str(cir)] + 500)
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].close()

                            os.remove(model.checkpoint_path +
                                        model.summary_dir +
                                        "_restore_val_set_test_task_finetune_with_valset_test_task_idx_"+str(test_task_idx)+'_fset_'+ str(fset_idx) +"/model.ckpt")

                else:
                    for test_task_idx, test_task in enumerate(test_tasks):
                        test_feed_dict = {model.X_finetune: test_task["X_outer"], model.Y_finetune: np.expand_dims(test_task["Y_outer"], -1)}

                        if(min_val_tasks_avg_test_loss_finetune_epoch[str(K)+'_'+str(cir)] <= 500):
                            finetune_summary_interval = 100
                        else:
                            finetune_summary_interval = 500

                        for fset_idx in range(n_finetune_sets):
                            if(summary):
                                test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)] = tf.summary.FileWriter(
                                    os.path.join(loddir_path, model.summary_dir) + '/test_task_finetune_K_' +str(K)+'_cir_'+str(cir) + '_test_task_idx_'+str(test_task_idx)+'_fset_idx_'+str(fset_idx))

                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)] = tf.summary.FileWriter(
                                    os.path.join(loddir_path, model.summary_dir) + '/test_task_test_K_' +str(K)+'_cir_'+str(cir) + '_test_task_idx_'+str(test_task_idx)+'_fset_idx_'+str(fset_idx))

                                sess.run(tf.local_variables_initializer()) 
                                test_summaries = model.sess.run(model.merged_test, test_feed_dict)
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(test_summaries, 0)
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()
                
                            model.saver.restore(
                                model.sess,
                                model.checkpoint_path +
                                model.summary_dir +
                                "_restore_val_task_test_loss_" + str(K) + '_' + str(cir) + "/model.ckpt")

                            K_normal_finetune = random.sample(test_finetune_normal_indexes_list[test_task_idx], n_needed_normal_finetune)
                            K_anomalous_finetune = random.sample(test_finetune_anomalous_indexes_list[test_task_idx], n_needed_anomalous_finetune)
                            K_finetune = []
                            K_finetune += K_normal_finetune
                            K_finetune += K_anomalous_finetune
                            
                            finetune_X, finetune_Y = test_task["X_inner"][K_finetune], np.expand_dims(test_task["Y_inner"][K_finetune], -1)
                            if(cir > 0.5 and cir < 1.0):
                                ros = RandomOverSampler(random_state=seed)
                                finetune_X_reshaped = np.reshape(finetune_X, (finetune_X.shape[0], -1))
                                finetune_X_reshaped, finetune_Y_reshaped = ros.fit_resample(finetune_X_reshaped, np.squeeze(finetune_Y))
                                finetune_X = np.reshape(finetune_X_reshaped, (-1, 84, 84, 3))
                                finetune_Y = np.expand_dims(finetune_Y_reshaped, -1)

                            if(model.batch_size < K):
                                batch_idxs = random.sample(range(0, finetune_X.shape[0]), model.batch_size)
                                for finetune_epoch in range(1,min_val_tasks_avg_test_loss_finetune_epoch[str(K)+'_'+str(cir)]+1):
                                    finetune_loss, finetune_summaries = model.finetune_op(finetune_X[batch_idxs], finetune_Y[batch_idxs])
                                    if(summary and finetune_epoch%finetune_summary_interval == 1):
                                        test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(finetune_summaries, finetune_epoch)
                                        test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()
                                        sess.run(tf.local_variables_initializer()) 
                                        test_summaries = model.sess.run(model.merged_test, test_feed_dict)
                                        test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(test_summaries, finetune_epoch)
                                        test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()
                                        
                            else:
                                for finetune_epoch in range(1,min_val_tasks_avg_test_loss_finetune_epoch[str(K)+'_'+str(cir)]+1):
                                    finetune_loss, finetune_summaries = model.finetune_op(finetune_X, finetune_Y)
                                    if(summary and finetune_epoch%finetune_summary_interval == 1):
                                        test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(finetune_summaries, finetune_epoch)
                                        test_task_finetune_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()
                                        sess.run(tf.local_variables_initializer()) 
                                        test_summaries = model.sess.run(model.merged_test, test_feed_dict)
                                        test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(test_summaries, finetune_epoch)
                                        test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()
                                        
                            sess.run(tf.local_variables_initializer()) 
                            test_loss, test_acc, test_precision, test_recall, test_specificity, test_f1_score, test_auc_pr = model.sess.run([model.test_loss, model.test_acc, model.test_precision, model.test_recall, model.test_specificity, model.test_f1_score, model.test_auc_pr], feed_dict=test_feed_dict) 

                            loss_list.append(test_loss)
                            acc_list.append(test_acc)
                            prec_list.append(test_precision)
                            rec_list.append(test_recall)
                            spec_list.append(test_specificity)
                            f1_list.append(test_f1_score)
                            auc_pr_list.append(test_auc_pr)
                            epoch_list.append(min_val_tasks_avg_test_loss_finetune_epoch[str(K)+'_'+str(cir)])

                            if(summary):
                                sess.run(tf.local_variables_initializer()) 
                                test_summaries = model.sess.run(model.merged_test, test_feed_dict)
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].add_summary(test_summaries, min_val_tasks_avg_test_loss_finetune_epoch[str(K)+'_'+str(cir)] + 500)
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].flush()
                                test_task_test_writers[str(K)+'_'+str(cir)+'_'+str(test_task_idx)+'_'+str(fset_idx)].close()

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
