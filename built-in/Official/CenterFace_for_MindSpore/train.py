# Copyright 2020 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""
######################## train centerface example ########################
train centerface and get network model files(.ckpt) :
you'd better donot use this file directly, use the training script in folder 'script'
"""

import os
from mindspore import context

devid = int(os.getenv('DEVICE_ID'))

# sigmoid need to be fp32, thus should not use enable_auto_mixed_precision=True
context.set_context(mode=context.GRAPH_MODE, enable_auto_mixed_precision=False,
                    device_target="Davinci", save_graphs=True, device_id=devid, reserve_class_name_in_scope=False)
#context.set_context(variable_memory_max_size="3GB") # belongs to users hardware

import time
import argparse
import datetime
import numpy as np

try:
    from mindspore.train import ParallelMode
except:
    from mindspore.context import ParallelMode

from mindspore.nn.optim.adam import Adam
from mindspore.nn.optim.momentum import Momentum
from mindspore.nn.optim.sgd import SGD
from mindspore import Tensor
import mindspore.nn as nn
from mindspore.common import dtype as mstype
from mindspore.communication.management import init, get_rank, get_group_size
from mindspore.train.callback import ModelCheckpoint, RunContext
from mindspore.train.callback import _InternalCallbackParam, CheckpointConfig, Callback
import mindspore as ms
from mindspore.train.serialization import load_checkpoint, load_param_into_net


from src.utils import get_logger
from src.utils import AverageMeter

from src.lr_scheduler import warmup_step_lr
from src.lr_scheduler import warmup_cosine_annealing_lr, \
    warmup_cosine_annealing_lr_V2, warmup_cosine_annealing_lr_sample
from src.lr_scheduler import MultiStepLR
from src.var_init import default_recurisive_init

from src.centerface import centerface_mobilev2
from src.utils import load_backbone, get_param_groups
from src.config import Config_centerface

from src.centerface import CenterFaceWithLossCell, TrainingWrapper
try:
    from src.dataset import get_dataLoader
except:
    from src.dependency.train.dataset import get_dataLoader

def parse_args(cloud_args={}):
    parser = argparse.ArgumentParser('mindspore coco training')

    # dataset related
    parser.add_argument('--data_dir', type=str, default='', help='train data dir')
    parser.add_argument('--annot_path', type=str, default='', help='train data annotation path')
    parser.add_argument('--img_dir', type=str, default='', help='train data img dir')
    parser.add_argument('--per_batch_size', default=32, type=int, help='batch size for per gpu')

    # network related
    parser.add_argument('--pretrained_backbone', default='', type=str, help='model_path, local pretrained backbone'
                                                                            ' model to load')
    parser.add_argument('--resume', default='', type=str, help='path of pretrained centerface_model')

    # optimizer and lr related
    parser.add_argument('--lr_scheduler', default='multistep', type=str,
                        help='lr-scheduler, option type: exponential, cosine_annealing')
    parser.add_argument('--lr', default=0.001, type=float, help='learning rate of the training')
    parser.add_argument('--lr_epochs', type=str, default='220,250', help='epoch of lr changing')
    parser.add_argument('--lr_gamma', type=float, default=0.1,
                        help='decrease lr by a factor of exponential lr_scheduler')
    parser.add_argument('--eta_min', type=float, default=0., help='eta_min in cosine_annealing scheduler')
    parser.add_argument('--T_max', type=int, default=280, help='T-max in cosine_annealing scheduler')
    parser.add_argument('--max_epoch', type=int, default=280, help='max epoch num to train the model')
    parser.add_argument('--warmup_epochs', default=0, type=float, help='warmup epoch')
    parser.add_argument('--weight_decay', type=float, default=0.0005, help='weight decay')
    parser.add_argument('--momentum', type=float, default=0.9, help='momentum')
    parser.add_argument('--optimizer', default='adam', type=str,
                        help='optimizer type, default: adam')

    # loss related
    parser.add_argument('--loss_scale', type=int, default=1024, help='static loss scale')
    parser.add_argument('--label_smooth', type=int, default=0, help='whether to use label smooth in CE')
    parser.add_argument('--label_smooth_factor', type=float, default=0.1, help='smooth strength of original one-hot')

    # logging related
    parser.add_argument('--log_interval', type=int, default=100, help='logging interval')
    parser.add_argument('--ckpt_path', type=str, default='outputs/', help='checkpoint save location')
    parser.add_argument('--ckpt_interval', type=int, default=None, help='ckpt_interval')

    parser.add_argument('--is_save_on_master', type=int, default=1, help='save ckpt on master or all rank')

    # distributed related
    parser.add_argument('--is_distributed', type=int, default=1, help='if multi device')
    parser.add_argument('--rank', type=int, default=0, help='local rank of distributed')
    parser.add_argument('--group_size', type=int, default=1, help='world size of distributed')

    # roma obs
    parser.add_argument('--train_url', type=str, default="", help='train url')

    # profiler init, can open when you debug. if train, donot open, since it cost memory and disk space
    parser.add_argument('--need_profiler', type=int, default=0, help='whether use profiler')

    # reset default config
    parser.add_argument('--training_shape', type=str, default="", help='fix training shape')
    parser.add_argument('--resize_rate', type=int, default=None, help='resize rate for multi-scale training')

    args, _ = parser.parse_known_args()
    args = merge_args(args, cloud_args)

    if args.lr_scheduler == 'cosine_annealing' and args.max_epoch > args.T_max:
        args.T_max = args.max_epoch

    args.lr_epochs = list(map(int, args.lr_epochs.split(',')))

    return args


def merge_args(args, cloud_args):
    args_dict = vars(args)
    if isinstance(cloud_args, dict):
        for key in cloud_args.keys():
            val = cloud_args[key]
            if key in args_dict and val:
                arg_type = type(args_dict[key])
                if arg_type is not type(None):
                    val = arg_type(val)
                args_dict[key] = val
    return args


def conver_training_shape(args):
    training_shape = [int(args.training_shape), int(args.training_shape)]
    return training_shape


def train(cloud_args={}):
    args = parse_args(cloud_args)

    # init distributed
    if args.is_distributed:
        init()
        args.rank = get_rank()
        args.group_size = get_group_size()

    # select for master rank save ckpt or all rank save, compatiable for model parallel
    args.rank_save_ckpt_flag = 0
    if args.is_save_on_master:
        if args.rank == 0:
            args.rank_save_ckpt_flag = 1
    else:
        args.rank_save_ckpt_flag = 1

    # logger
    args.outputs_dir = os.path.join(args.ckpt_path,
                                    datetime.datetime.now().strftime('%Y-%m-%d_time_%H_%M_%S'))
    args.logger = get_logger(args.outputs_dir, args.rank)
    args.logger.save_args(args)

    if args.need_profiler:
        from mindspore.profiler.profiling import Profiler
        profiler = Profiler(output_path=args.outputs_dir, is_detail=True, is_show_op_path=True)

    loss_meter = AverageMeter('loss')

    context.reset_auto_parallel_context()
    if args.is_distributed:
        parallel_mode = ParallelMode.DATA_PARALLEL
        degree = get_group_size()
    else:
        parallel_mode = ParallelMode.STAND_ALONE
        degree = 1

    # context.set_auto_parallel_context(parallel_mode=parallel_mode, device_num=degree, parameter_broadcast=True, gradients_mean=True)
    # Notice: parameter_broadcast should be supported, but current version has bugs, thus been disabled.
    # To make sure the init weight on all npu is the same, we need to set a static seed in default_recurisive_init when weight initialization
    context.set_auto_parallel_context(parallel_mode=parallel_mode, gradients_mean=True, device_num=degree)
    network = centerface_mobilev2()
    # init, to avoid overflow, some std of weight should be enough small
    default_recurisive_init(network)

    if args.pretrained_backbone:
        network = load_backbone(network, args.pretrained_backbone, args)
        args.logger.info('load pre-trained backbone {} into network'.format(args.pretrained_backbone))
    else:
        args.logger.info('Not load pre-trained backbone, please be careful')

    if os.path.isfile(args.resume):
        param_dict = load_checkpoint(args.resume)
        param_dict_new = {}
        for key, values in param_dict.items():
            if key.startswith('moments.') or key.startswith('moment1.') or key.startswith('moment2.'):
                continue
            elif key.startswith('centerface_network.'):
                param_dict_new[key[19:]] = values
            else:
                param_dict_new[key] = values

        load_param_into_net(network, param_dict_new)
        args.logger.info('load_model {} success'.format(args.resume))
    else:
        args.logger.info('{} not set/exists or not a pre-trained file'.format(args.resume))

    network = CenterFaceWithLossCell(network)
    args.logger.info('finish get network')

    config = Config_centerface()
    config.data_dir = args.data_dir
    config.annot_path = args.annot_path
    config.img_dir = args.img_dir

    config.label_smooth = args.label_smooth
    config.label_smooth_factor = args.label_smooth_factor
    # -------------reset config-----------------
    if args.training_shape:
        config.multi_scale = [conver_training_shape(args)]

    if args.resize_rate:
        config.resize_rate = args.resize_rate

    # data loader
    data_loader, train_sampler = get_dataLoader(config, args)
    args.steps_per_epoch = len(data_loader)#data_size
    args.logger.info('Finish loading dataset')

    if not args.ckpt_interval:
        args.ckpt_interval = args.steps_per_epoch

    # lr scheduler
    if args.lr_scheduler == 'multistep':
        lr_fun = MultiStepLR(args.lr, args.lr_epochs, args.lr_gamma, args.steps_per_epoch, args.max_epoch, args.warmup_epochs)
        lr = lr_fun.get_lr()
    elif args.lr_scheduler == 'exponential':
        lr = warmup_step_lr(args.lr,
                            args.lr_epochs,
                            args.steps_per_epoch,
                            args.warmup_epochs,
                            args.max_epoch,
                            gamma=args.lr_gamma
                            )
    elif args.lr_scheduler == 'cosine_annealing':
        lr = warmup_cosine_annealing_lr(args.lr,
                                        args.steps_per_epoch,
                                        args.warmup_epochs,
                                        args.max_epoch,
                                        args.T_max,
                                        args.eta_min)
    elif args.lr_scheduler == 'cosine_annealing_V2':
        lr = warmup_cosine_annealing_lr_V2(args.lr,
                                           args.steps_per_epoch,
                                           args.warmup_epochs,
                                           args.max_epoch,
                                           args.T_max,
                                           args.eta_min)
    elif args.lr_scheduler == 'cosine_annealing_sample':
        lr = warmup_cosine_annealing_lr_sample(args.lr,
                                               args.steps_per_epoch,
                                               args.warmup_epochs,
                                               args.max_epoch,
                                               args.T_max,
                                               args.eta_min)
    else:
        raise NotImplementedError(args.lr_scheduler)

    if args.optimizer == "adam":
        opt = Adam(params=get_param_groups(network),
                   learning_rate=Tensor(lr),
                   weight_decay=args.weight_decay,
                   loss_scale=args.loss_scale)
        args.logger.info("use adam optimizer")
    elif args.optimizer == "sgd":
        opt = SGD(params=get_param_groups(network),
                   learning_rate=Tensor(lr),
                   momentum=args.momentum,
                   weight_decay=args.weight_decay,
                   loss_scale=args.loss_scale)
    else:
        opt = Momentum(params=get_param_groups(network),
                   learning_rate=Tensor(lr),
                   momentum=args.momentum,
                   weight_decay=args.weight_decay,
                   loss_scale=args.loss_scale)

    network = TrainingWrapper(network, opt, sens=args.loss_scale)
    network.set_train()

    ckpt_history = []
    if args.rank_save_ckpt_flag:
        # checkpoint save
        ckpt_max_num = args.max_epoch * args.steps_per_epoch // args.ckpt_interval
        ckpt_config = CheckpointConfig(save_checkpoint_steps=args.ckpt_interval,
                                       keep_checkpoint_max=ckpt_max_num)
        ckpt_cb = ModelCheckpoint(config=ckpt_config,
                                  directory=args.outputs_dir,
                                  prefix='{}'.format(args.rank))
        cb_params = _InternalCallbackParam()
        cb_params.train_network = network
        cb_params.epoch_num = ckpt_max_num
        cb_params.cur_epoch_num = 1
        run_context = RunContext(cb_params)
        ckpt_cb.begin(run_context)

        args.logger.info('args.steps_per_epoch = {} args.ckpt_interval ={}'.format(args.steps_per_epoch, args.ckpt_interval))

    old_progress = -1
    t_end = time.time()

    #feed_mode + pytorch dataloader
    start_epoch = 0
    for epoch in range(start_epoch + 1, args.max_epoch + 1):
        for i, batch_load in enumerate(data_loader):
            batch ={}
            batch['input'] = batch_load['input'].detach().cpu().numpy()
            batch['hm'] = batch_load['hm'].detach().cpu().numpy()
            batch['reg_mask'] = batch_load['reg_mask'].detach().cpu().numpy()
            batch['ind'] = batch_load['ind'].detach().cpu().numpy()
            batch['wh'] = batch_load['wh'].detach().cpu().numpy()
            batch['landmarks'] = batch_load['landmarks'].detach().cpu().numpy()
            batch['hps_mask'] = batch_load['hps_mask'].detach().cpu().numpy()
            batch['wight_mask'] = batch_load['wight_mask'].detach().cpu().numpy()
            batch['hm_offset'] = batch_load['hm_offset'].detach().cpu().numpy()

            images = batch['input']
            hm = batch['hm']
            reg_mask = batch['reg_mask']
            ind_origin = batch['ind']
            wh_origin = batch['wh']
            wight_mask_origin = batch['wight_mask']
            hm_offset_origin = batch['hm_offset']
            hps_mask_origin = batch['hps_mask']
            landmarks_origin = batch['landmarks']

            batch_size = args.per_batch_size #8

            output_res = config.output_res
            wh = np.zeros((batch_size, output_res, output_res, 2), dtype=np.float32)
            hm_offset = np.zeros((batch_size, output_res, output_res, 2), dtype=np.float32) # reg
            ind = np.zeros((batch_size, output_res, output_res), dtype=np.float32)
            landmarks = np.zeros((batch_size, output_res, output_res, config.num_joints * 2), dtype=np.float32) # kps
            hps_mask = np.zeros((batch_size, output_res, output_res, config.num_joints * 2), dtype=np.float32) # kps_mask
            wight_mask = np.zeros((batch_size, output_res, output_res, 2), dtype=np.float32)

            for i_1 in range(batch_size):
                batch_ind_origin = ind_origin[i_1]
                for k in range(len(batch_ind_origin)):
                    if batch_ind_origin[k] > 0:
                        ct_int = [0, 0]
                        ct_int[0] = batch_ind_origin[k] % output_res
                        ct_int[1] = batch_ind_origin[k] // output_res
                        wh[i_1, ct_int[1], ct_int[0], :] = wh_origin[i_1, k, : ]
                        hm_offset[i_1, ct_int[1], ct_int[0], :] = hm_offset_origin[i_1, k, : ]
                        ind[i_1, ct_int[1], ct_int[0]] = 1.0

                        landmarks[i_1, ct_int[1], ct_int[0], : ] = landmarks_origin[i_1, k, : ]
                        hps_mask[i_1, ct_int[1], ct_int[0], : ] = hps_mask_origin[i_1, k, : ]

                        wight_mask[i_1, ct_int[1], ct_int[0], 0] = wight_mask_origin[i_1, k]
                        wight_mask[i_1, ct_int[1], ct_int[0], 1] = wight_mask_origin[i_1, k]

            images = Tensor(images)
            hm = Tensor(hm)
            reg_mask = Tensor(reg_mask)
            ind = Tensor(ind)
            wh = Tensor(wh)
            wight_mask = Tensor(wight_mask)
            hm_offset = Tensor(hm_offset)
            hps_mask = Tensor(hps_mask)
            landmarks = Tensor(landmarks)

            loss, overflow, scaling = network(images, hm, reg_mask, ind, wh, wight_mask, hm_offset, hps_mask, landmarks)
            # Tensor to numpy
            overflow = np.all(overflow.asnumpy())
            loss = loss.asnumpy()
            loss_meter.update(loss)
            args.logger.info('epoch:{}, iter:{}, average_loss:{}, loss:{}, overflow:{}, loss_scale:{}'.format(epoch, i, loss_meter, loss, overflow, scaling.asnumpy()))

            end = time.time()

            if args.rank_save_ckpt_flag:
                # ckpt progress
                cb_params.cur_epoch_num = epoch
                cb_params.cur_step_num = i + 1 + (epoch-1)*args.steps_per_epoch
                cb_params.batch_num = i + 2 + (epoch-1)*args.steps_per_epoch
                ckpt_cb.step_end(run_context)

        time_used = time.time() - t_end
        fps = args.per_batch_size * args.steps_per_epoch * args.group_size / time_used
        if args.rank == 0:
            args.logger.info('epoch[{}], {}, {:.2f} imgs/sec, lr:{}'.format(epoch, loss_meter, fps, lr[i + (epoch-1)*args.steps_per_epoch]))
        t_end = time.time()
        loss_meter.reset()
        args.logger.info('==========end epoch===============')

        # reset shuffle seed, important for impove performance
        train_sampler.set_epoch(epoch)

    if args.need_profiler:
        profiler.analyse()

    args.logger.info('==========end training===============')


if __name__ == "__main__":
    train()



