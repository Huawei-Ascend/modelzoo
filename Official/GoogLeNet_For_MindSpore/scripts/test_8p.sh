python /path/to/modelzoo_googlenet/launch.py --nproc_per_node=8 --visible_device=0,1,2,3,4,5,6,7 --mode=test\
--env_sh=/path/to/modelzoo_googlenet/scripts/env.sh --server_id=xx.xxx.xxx.xxx /path/to/modelzoo_googlenet/test.py \
--per_batch_size=128 --data_dir=/path/to/dataset/val --is_distribute=1 --pretrained=/path/to/ckpt --backbone=googlenet \