import tensorflow as tf
import math
import numpy as np


def warmup_cosine_annealing_lr(lr, steps_per_epoch, warmup_epochs, max_epoch, T_max, eta_min=0):
    base_lr = lr
    warmup_init_lr = 0
    total_steps = int(max_epoch * steps_per_epoch)
    warmup_steps = int(warmup_epochs * steps_per_epoch)

    lr_each_step = []
    for i in range(total_steps):
        last_epoch = i // steps_per_epoch
        if i < warmup_steps:
            lr = linear_warmup_lr(i + 1, warmup_steps, base_lr, warmup_init_lr)
        else:
            lr = eta_min + (base_lr - eta_min) * (1. + math.cos(math.pi*last_epoch / T_max)) / 2
        lr_each_step.append(lr)

    return np.array(lr_each_step).astype(np.float32)


class HyperParams:
    def __init__(self, config):
        self.config=config
        nsteps_per_epoch = self.config['num_training_samples'] // self.config['global_batch_size']
        self.config['nsteps_per_epoch'] = nsteps_per_epoch
        if self.config['num_epochs']:
            nstep = nsteps_per_epoch * self.config['num_epochs']
        else:
            nstep = self.config['max_train_steps']
        self.config['nstep'] = nstep
        
        self.config['save_summary_steps'] = nsteps_per_epoch
        self.config['save_checkpoints_steps'] = nsteps_per_epoch

        self.cos_lr = warmup_cosine_annealing_lr(self.config['lr'], nsteps_per_epoch, 0, self.config['max_epoch'], self.config['max_epoch'], 0.0)

    def get_hyper_params(self):
        hyper_params = {}
        hyper_params['learning_rate'] = self.get_learning_rate()

        return hyper_params

    def get_learning_rate(self): 
        global_step = tf.train.get_global_step()
    
        learning_rate = tf.gather(tf.convert_to_tensor(self.cos_lr), global_step)

        learning_rate = tf.identity(learning_rate, 'learning_rate')

        return learning_rate

