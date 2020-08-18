#!/bin/bash

python /path/to/modelzoo_densenet121/launch.py \
--nproc_per_node=8 --visible_devices=0,1,2,3,4,5,6,7 \
--mode=test \
--env_sh=/path/to/modelzoo_densenet121/scripts/env.sh \
--server_id=xx.xxx.xxx.xxx \
/path/to/modelzoo_densenet121/test.py  \
--data_dir /path/to/dataset/val/ \
--per_batch_size 32 --pretrained /path/to/ckpt
