import tensorflow as tf
from . import inception_v4
from tensorflow.contrib import slim as slim
from npu_bridge.estimator.npu.npu_estimator import NPUEstimatorSpec
import numpy as np
import os

class Model(object):
    def __init__(self, args, data, hyper_param, layers, logger):
        self.args = args
        self.data = data
        self.hyper_param = hyper_param
        self.layers = layers
        self.logger = logger  

    def get_estimator_model_func(self, features, labels, mode, params=None):
        labels = tf.reshape(labels, (-1,))
    
        inputs = features
        is_training = (mode == tf.estimator.ModeKeys.TRAIN)

        inputs = tf.cast(inputs, self.args.dtype)

        if is_training:
            with slim.arg_scope(inception_v4.inception_v4_arg_scope(weight_decay=self.args.weight_decay)):
                top_layer, end_points = inception_v4.inception_v4(inputs=features, num_classes=1000, dropout_keep_prob=0.8, is_training = True)
        else:
            with slim.arg_scope(inception_v4.inception_v4_arg_scope()):
                top_layer, end_points = inception_v4.inception_v4(inputs=features, num_classes=1000, dropout_keep_prob=1.0, is_training = False)

        logits = top_layer
        predicted_classes = tf.argmax(logits, axis=1, output_type=tf.int32)
        logits = tf.cast(logits, tf.float32)

        labels_one_hot = tf.one_hot(labels, depth=1000)
        
        loss = tf.losses.softmax_cross_entropy(
            logits=logits, onehot_labels=labels_one_hot, label_smoothing=self.args.label_smoothing)
        
        base_loss = tf.identity(loss, name='loss')
        
        total_loss = tf.losses.get_total_loss(add_regularization_losses = True)
        total_loss = tf.identity(total_loss, name = 'total_loss')
        

        if mode == tf.estimator.ModeKeys.EVAL:
            with tf.device(None):
                metrics = self.layers.get_accuracy( labels, predicted_classes, logits, self.args)

            return NPUEstimatorSpec(
                mode, loss=loss, eval_metric_ops=metrics)

        assert (mode == tf.estimator.ModeKeys.TRAIN)

        batch_size = tf.shape(inputs)[0]

        global_step = tf.train.get_global_step()
        learning_rate = self.hyper_param.get_learning_rate()

        opt = tf.train.RMSPropOptimizer(learning_rate, decay = 0.9, momentum = 0.9, epsilon = 1.0)

        from npu_bridge.estimator.npu.npu_optimizer import NPUDistributedOptimizer
        from npu_bridge.estimator.npu.npu_loss_scale_optimizer import NPULossScaleOptimizer
        from npu_bridge.estimator.npu.npu_loss_scale_manager import FixedLossScaleManager

        opt = NPUDistributedOptimizer(opt)
        
        loss_scale_manager = FixedLossScaleManager(loss_scale=1024)

        rank_size = int(os.getenv('RANK_SIZE'))

        if rank_size > 1:
            opt = NPULossScaleOptimizer(opt, loss_scale_manager, is_distributed=True)
        else:
            opt = NPULossScaleOptimizer(opt, loss_scale_manager, is_distributed=False)

        update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS) or []

        with tf.control_dependencies(update_ops):
            gate_gradients = tf.train.Optimizer.GATE_NONE
            grads_and_vars = opt.compute_gradients(total_loss, gate_gradients=gate_gradients)
            train_op = opt.apply_gradients(grads_and_vars, global_step=global_step)

        train_op = tf.group(train_op)
        
        return NPUEstimatorSpec(mode, loss=total_loss, train_op=train_op)  

