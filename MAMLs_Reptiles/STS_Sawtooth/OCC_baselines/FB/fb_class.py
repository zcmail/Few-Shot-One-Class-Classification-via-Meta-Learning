# -*- coding: utf-8 -*-
import tensorflow as tf
import numpy as np
import random
import os
import random 


class FB:

    """
    
    A class for a neural network that is trained using only one task.
    
    """
    def __init__(self, sess, args, seed, input_shape, n_train_classes):

        random.seed(seed)
        np.random.seed(seed)
        tf.set_random_seed(seed)

        # get parsed args
        self.lr = args.lr
        # self.K = args.K
        self.batch_size = args.batch_size
        self.sess = sess
        self.summary = False
        self.summary_dir = args.summary_dir
        if(self.summary_dir):
            self.summary = True
            self.summary_interval = 200
            summaries_list_val = []
            summaries_list_train = []
        else:
            self.summary_dir = "no_summary"

        self.val_task_finetune_interval = 200
        self.val_task_finetune_epochs = 200
        self.early_stopping_val = 100

        self.finetune_data_percentage = 0.8
        self.early_stopping_test = 300

        # dataset specific variables
        self.n_classes_fb = n_train_classes
        self.n_classes_oc = 1

        self.dim_input = input_shape[0]
        self.flatten = tf.keras.layers.Flatten()
        self.filter_sizes = [int(i) for i in args.filters.split(' ')]
        self.kernel_sizes = [int(i) for i in args.kernel_sizes.split(' ')]

        # build model
        self.layers = []
        if(len(self.filter_sizes) == 1):
            self.layers.append(
                    tf.keras.layers.Conv1D(
                        filters=self.filter_sizes[0],
                        kernel_size=self.kernel_sizes[0], 
                        input_shape=(None, self.dim_input, 1),
                        strides=2,
                        padding='same',
                        activation='relu',
                        name='conv_last'))
                    
            # self.layers.append(tf.keras.layers.BatchNormalization(name='bn_c_last'))

        else:
            self.layers.append(
                tf.keras.layers.Conv1D(
                    filters=self.filter_sizes[0],
                    kernel_size=self.kernel_sizes[0], 
                    input_shape=(None, self.dim_input, 1),
                    strides=2,
                    padding='same',
                    activation='relu',
                    name='conv0'))
            # self.layers.append(tf.keras.layers.BatchNormalization(name='bn_c0'))

        for i in range(1, len(self.filter_sizes)):
            if(i != len(self.filter_sizes)-1):
                self.layers.append(
                tf.keras.layers.Conv1D(
                    filters=self.filter_sizes[i],
                    kernel_size=self.kernel_sizes[i],
                    strides=2,
                    padding='same',
                    activation='relu',
                    name='conv'+str(i)))
                
                # self.layers.append(tf.keras.layers.BatchNormalization(name='bn_c'+str(i)))
            else:
                self.layers.append(
                    tf.keras.layers.Conv1D(
                        filters=self.filter_sizes[i],
                        kernel_size=self.kernel_sizes[i],
                        strides=2,
                        padding='same',
                        activation='relu',
                        name='conv_last'))
                    
                # self.layers.append(tf.keras.layers.BatchNormalization(name='bn_c_last'))

        if(args.dense_layers == ""):
            self.dense_sizes=[]
        else:
            self.dense_sizes = [int(i) for i in args.dense_layers.split(' ')]
        
        for i in range(0, len(self.dense_sizes)):
            self.layers.append(tf.keras.layers.Dense(units=self.dense_sizes[i], activation='relu',name='dense'+str(i)))

        self.layers.append(tf.keras.layers.Dense(units=self.n_classes_fb, name='dense_last_fb'))
        self.layers.append(tf.keras.layers.Dense(units=self.n_classes_oc, name='dense_last_oc'))

        # loss function
        self.loss_fct_fb = tf.nn.sparse_softmax_cross_entropy_with_logits
        self.loss_fct_oc = tf.nn.sigmoid_cross_entropy_with_logits


        self.X = tf.placeholder(
            tf.float32, (None, self.dim_input), name='X')
        self.Y_fb = tf.placeholder(
            tf.int64, (None,), name='Y_fb')

        self.Y_oc = tf.placeholder(
            tf.float32, (None, self.n_classes_oc), name='Y_oc')



        self.train_output_fb = self.construct_forward_fb(self.X, True)

        self.train_loss_fb = tf.reduce_mean(self.loss_fct_fb(
                labels=self.Y_fb,
                logits=self.train_output_fb))



        self.train_update_op_fb = tf.train.AdamOptimizer(
                self.lr).minimize(self.train_loss_fb)       

        self.my_acc_fb = self.compute_metrics_fb(
            self.train_output_fb, self.Y_fb)




        self.train_output_oc = self.construct_forward_oc(self.X, True)

        self.train_loss_oc = tf.reduce_mean(self.loss_fct_oc(
                labels=self.Y_oc,
                logits=self.train_output_oc))




        self.train_update_op_oc = tf.train.AdamOptimizer(
                self.lr).minimize(self.train_loss_oc)       


        self.test_output = self.construct_forward_oc(self.X, False)
        self.test_loss = tf.reduce_mean(self.loss_fct_oc(
                labels=self.Y_oc,
                logits=self.test_output))

        self.my_acc, self.my_precision, self.my_recall, self.my_specificity, self.my_f1_score, self.my_auc_pr = self.compute_metrics_oc(
            self.test_output, self.Y_oc)




        if(self.summary):
            summaries_list_train.append(
                tf.summary.scalar('train_loss_fb', self.train_loss_fb))
            self.merged_train = tf.summary.merge(
                summaries_list_train)
            # summaries_list_val.append(
            #     tf.summary.scalar('val_loss', self.val_loss))        
            summaries_list_val.append(
                tf.summary.scalar('accuracy', self.my_acc))
            summaries_list_val.append(
                tf.summary.scalar(
                    'precision', self.my_precision))
            summaries_list_val.append(
                tf.summary.scalar('recall', self.my_recall))
            summaries_list_val.append(
                tf.summary.scalar('specificity', self.my_specificity))
            summaries_list_val.append(
                tf.summary.scalar('f1_score', self.my_f1_score))
            summaries_list_val.append(
                tf.summary.scalar('auc_pr', self.my_auc_pr))
            self.merged_val = tf.summary.merge(
                summaries_list_val)

        self.saver = tf.train.Saver(max_to_keep=250)

        base_path = '/home/USER/Documents'
        if (not (os.path.exists(base_path))):
            base_path = '/home/ubuntu/Projects' 


        self.checkpoint_path = base_path + '/MAML/checkpoints_FB/'
        if (not (os.path.exists(self.checkpoint_path))):
            os.mkdir(self.checkpoint_path)
        if (not (os.path.exists(os.path.join(self.checkpoint_path, self.summary_dir)))):
            os.mkdir(os.path.join(self.checkpoint_path, self.summary_dir))


    def compute_metrics_oc(self, logits, labels):
        """compute performance metrics.

        Parameters
        ----------
        logits : tensor
        labels : tensor
            

        Returns
        -------
        acc : tensor
            accuracy.
        precision : tensor
            precision.
        recall : tensor
            recall.
        specificity : tensor
            specificity.
        f1_score : tensor
            F1 score.
        auc_pr : tensor
            AUC-PR.

        """

        predictions = tf.cast(tf.greater(tf.nn.sigmoid(logits), 0.5), tf.float32)
        TP = tf.count_nonzero(predictions * labels)
        TN = tf.count_nonzero((predictions - 1) * (labels - 1))
        FP = tf.count_nonzero(predictions* (labels - 1))
        FN = tf.count_nonzero((predictions-1) *labels)
        acc = tf.reduce_mean(tf.to_float(tf.equal(predictions, labels)))

        precision = tf.cond(tf.math.equal((TP+FP), 0), true_fn=lambda:tf.cast(0.0, tf.float64), false_fn=lambda: TP/(TP + FP))
        recall = TP / (TP + FN)
        specificity = TN / (TN + FP)
        f1_score = tf.cond(tf.math.equal((precision + recall), 0), true_fn=lambda:tf.cast(0.0, tf.float64), false_fn=lambda: 2*precision*recall/(precision + recall))

        auc_pr = tf.metrics.auc(labels=labels, predictions=tf.nn.sigmoid(logits), curve='PR',
                        summation_method='careful_interpolation')[1]

        return [
            acc, tf.cast(
                precision, tf.float32), tf.cast(
                recall, tf.float32), tf.cast(
                specificity, tf.float32), tf.cast(
                f1_score, tf.float32), auc_pr]


    def compute_metrics_fb(self, logits, labels):
        """compute performance metrics.

        Parameters
        ----------
        logits : tensor
        labels : tensor
            

        Returns
        -------
        acc : tensor
            accuracy.
        precision : tensor
            precision.
        recall : tensor
            recall.
        specificity : tensor
            specificity.
        f1_score : tensor
            F1 score.
        auc_pr : tensor
            AUC-PR.

        """

        predictions = tf.nn.softmax(logits)
        acc = tf.reduce_mean(tf.to_float(tf.equal(tf.math.argmax(predictions, -1), labels)))

        
        return acc

    def construct_forward_fb(self, inp, training):
        """computes an output tensor by feeding the input through the network.

        Parameters
        ----------
        inp : tensor
            input tensor.
        training : bool
            argument for Batch normalization layers.

        Returns
        -------
        out : tensor
            output tensor.

        """
        h = tf.expand_dims(inp, -1)
        for i in range(len(self.layers)-2):
            if('conv' in self.layers[i].name):
                h = self.layers[i](h)
                h = tf.layers.max_pooling1d(h, pool_size=2, strides=2, padding='same')
            elif('dense' in self.layers[i].name):
                h = self.layers[i](h)
            elif('bn' in self.layers[i].name):
                h = self.layers[i](h, training=training)
            if('conv_last' in self.layers[i].name):
                h = self.flatten(h)
        out = self.layers[-2](h)
        return out


    def construct_forward_oc(self, inp, training):
        """computes an output tensor by feeding the input through the network.

        Parameters
        ----------
        inp : tensor
            input tensor.
        training : bool
            argument for Batch normalization layers.

        Returns
        -------
        out : tensor
            output tensor.

        """
        h = tf.expand_dims(inp, -1)
        for i in range(len(self.layers)-2):
            if('conv' in self.layers[i].name):
                h = self.layers[i](h)
                h = tf.layers.max_pooling1d(h, pool_size=2, strides=2, padding='same')
            elif('dense' in self.layers[i].name):
                h = self.layers[i](h)
            elif('bn' in self.layers[i].name):
                h = self.layers[i](h, training=training)
            if('conv_last' in self.layers[i].name):
                h = self.flatten(h)
        out = self.layers[-1](h)
        return out


    def train_op(self, X_train, Y_train, epoch):
        """update model parameters.

        Parameters
        ----------
        X_train : numpy array
            features of the training batch.
        Y_train : numpy array
            labels of the training batch.
        epoch : int
            number of the current epoch.

        Returns
        -------
        train_loss : float
            training loss.
        summaries : list
            training summaries.

        """

        feed_dict = {self.X: X_train, self.Y_fb: Y_train}
        train_loss, train_acc, _ = self.sess.run(
                [self.train_loss_fb, self.my_acc_fb, self.train_update_op_fb], feed_dict)

        if(self.summary and (epoch % self.summary_interval == 0)):
            summaries = self.sess.run(self.merged_train, feed_dict)
             
        else:
            summaries = None
            
        return train_loss, train_acc, summaries  

    def val_op(self, X_val_finetune, Y_val_finetune, val_task_test_X, val_task_test_Y, K, cir, train_epoch):

        # saving model parameters
        old_vars = []
        for layer_idx in range(0, len(self.layers)):
            layer_weights = self.layers[layer_idx].get_weights()
            old_vars.append(layer_weights)


        min_val_test_loss = 10000
        min_val_test_loss_epoch = -1
        early_stopping = 0
        val_test_acc_min_loss = 0
        
        feed_dict_val_task_test = {self.X : val_task_test_X, self.Y_oc : val_task_test_Y}

        feed_dict_val_task_finetune = {self.X : X_val_finetune, self.Y_oc : Y_val_finetune}
        #finetuning on the val task
        for epoch in range(1,self.val_task_finetune_epochs+1):
            self.sess.run(self.train_update_op_oc, feed_dict=feed_dict_val_task_finetune)
            val_test_loss, val_test_acc = self.sess.run([self.test_loss, self.my_acc], feed_dict=feed_dict_val_task_test)
            if(val_test_loss<min_val_test_loss):
                early_stopping = 0
                min_val_test_loss_epoch = epoch
                min_val_test_loss = val_test_loss
                val_test_acc_min_loss = val_test_acc
            else:
                early_stopping+=1

            if(early_stopping >= self.early_stopping_val):
                break

        # print('val episode - train_epoch : ', train_epoch, ' K: ', K, ' cir: ', cir, ' val_test_acc_min_loss : ', val_test_acc_min_loss)
        # resetting previous model parameters
        for layer_idx in range(0, len(self.layers)):
            self.layers[layer_idx].set_weights(old_vars[layer_idx])

        return min_val_test_loss_epoch, min_val_test_loss, val_test_acc_min_loss


    def finetune_op(self, X_finetune, Y_finetune):
        """finetune model parameters to adapt to the target task.

        Parameters
        ----------
        X_finetune : numpy array
            features of the finetuning set of the target task.
        Y_finetune : numpy array
            labels of the finetuning set of the target task.

        Returns
        -------
        finetune_loss : float
            finetuning loss.
        finetune_summaries : list
            finetuning summaries.

        """

        feed_dict_finetune = {self.X : X_finetune, self.Y_oc : Y_finetune}

        finetune_loss, _ = self.sess.run(
                [self.train_loss_oc, self.train_update_op_oc], feed_dict_finetune)

        # if (self.summary):
        #     finetune_summaries = self.sess.run(self.merged_finetune, feed_dict_finetune)
        # else:
        #     finetune_summaries = None
            
        return finetune_loss