# Deeplabv3 for Tensorflow 

This repository provides a script and recipe to train the Deeplabv3 model. The code is based on tensorflow/models/research/deeplab,
modifications are made to run on NPU 

## Table Of Contents

* [Model overview](#model-overview)
  * [Model Architecture](#model-architecture)  
  * [Default configuration](#default-configuration)
* [Data augmentation](#data-augmentation)
* [Setup](#setup)
  * [Requirements](#requirements)
* [Quick start guide](#quick-start-guide)
* [Advanced](#advanced)
  * [Command line arguments](#command-line-arguments)
  * [Training process](#training-process)
* [Performance](#performance)
  * [Results](#results)
    * [Training accuracy results](#training-accuracy-results)
    * [Training performance results](#training-performance-results)


    

## Model overview

Deeplabv3 model from
`Liang-Chieh Chen et al. "Rethinking Atrous Convolution for Semantic Image Segmentation". <https://arxiv.org/abs/1706.05587>.`
reference implementation:  <https://github.com/tensorflow/models/tree/master/research/deeplab>
### Model architecture



### Default configuration

The following sections introduce the default configurations and hyperparameters for Deeplabv3 model. We reproduce two training setups 
on VOC_trainaug datasets, evaluate on four setups. See [Results](#results) for setups details.

For detailed hpyerparameters,, please refer to corresponding scripts under directory `scripts/`
#### Optimizer

This model uses Momentum optimizer from Tensorflow with the following hyperparameters:

- Momentum : 0.9
- LR schedule: cosine_annealing
- Batch size : 8 * 8   
- Weight decay :  0.0001. 

#### Data augmentation

This model uses the following data augmentation:

- For training:
  - RandomResizeCrop, scale=(0.08, 1.0), ratio=(0.75, 1.333)
  - RandomHorizontalFlip, prob=0.5
  - Normalize, mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)
- For inference:
  - Resize to (256, 256)
  - CenterCrop to (224, 224)
  - Normalize, mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)



## Setup
The following section lists the requirements to start training the Deeplabv3 model.
### Requirements

Tensorflow
NPU environmemnt
Pillow

## Quick Start Guide

### 1. Clone the respository

```shell
git clone xxx
cd  Model_zoo_deeplabv3_HARD
```

### 2. Download and preprocess the dataset

You can use any datasets as you wish. Here, we only use voc2012_trainaug dataset as an example to illustrate the data generation. 

1. download the voc2012 datasets. 
2. check if `SegmentationClassAug.zip` exists under `datasets/`,if not, you can download from <https://www.dropbox.com/s/oeu149j8qtbs1x0/SegmentationClassAug.zip?dl=0>
3. txt file named trainaug.txt containing all the seg_image filenames
4. put all three files under `datasets/` directory
5. go the datasets directory and run the script to create tfrecord file. tfrecord file will be saved under `dataset/pascal_voc_seg/tfrecord`
```
cd datasets
convert_voc2012_aug.sh
``` 

For other datasets, you need following three files.  Create a script similar to `convert_voc2012_aug.sh` and 
execute the script when you get all three file ready. 

 - original images
 - voc-style segmentation annotation file
 - txt file for all the seg_image filenames

### check json
Check whether there is a JSON configuration file "8p.json" for 8 Card IP in the scripts/ directory.
The content of the 8p configuration file:
```
{"group_count": "1","group_list":
                    [{"group_name": "worker","device_count": "8","instance_count": "1", "instance_list":
                    [{"devices":
                                   [{"device_id":"0","device_ip":"192.168.100.101"},
                                    {"device_id":"1","device_ip":"192.168.101.101"},
                                    {"device_id":"2","device_ip":"192.168.102.101"},
                                    {"device_id":"3","device_ip":"192.168.103.101"},
                                    {"device_id":"4","device_ip":"192.168.100.100"},
                                    {"device_id":"5","device_ip":"192.168.101.100"},
                                    {"device_id":"6","device_ip":"192.168.102.100"},
                                    {"device_id":"7","device_ip":"192.168.103.100"}],
                                    "pod_name":"npu8p",        "server_id":"127.0.0.1"}]}],"status": "completed"}
```

### 3. Train

Before starting the training, first configure the environment variables related to the program running. For environment variable configuration information, see:
- [Ascend 910训练平台环境变量设置](https://github.com/Huawei-Ascend/modelzoo/wikis/Ascend%20910%E8%AE%AD%E7%BB%83%E5%B9%B3%E5%8F%B0%E7%8E%AF%E5%A2%83%E5%8F%98%E9%87%8F%E8%AE%BE%E7%BD%AE?sort_id=3148819)


All the scripts to tick off the training are located under `scripts/`.  As there are two types of resnet_101 checkpoints exist, original version 
and a so-called beta version available, there are two sets of scripts one for each checkpoint. All the scripts that end with `beta` are meant for 
resnet_v1_101_beta checkpoint. All the scripts that start with `train` are configuration files for the training. You are free to choose either of them as initial checkpoint since they can achieve comparable performance.  


- For resnet_v1_101_beta, you can download from <http://download.tensorflow.org/models/resnet_v1_101_2018_05_04.tar.gz>

- For resnet_v1_101, you can download from <http://download.tensorflow.org/models/resnet_v1_101_2016_08_28.tar.gz>

After you download either checkpoint or both, un-compress the tarball file and put them under `pretrained/` directory.


For instance, to train the model with beta version checkpoints

- with OS=16
    - train on single NPU 
    
        ```
         cd scripts
         ./run_1p_s16_beta.sh
        ```
    - train on 8 NPUs
        ```
         cd scripts
         ./run_s16_beta.sh
        ```
- with OS=8
    - train on single NPU 
    
        ```
         cd scripts
         ./run_1p_s8_beta.sh
        ```
    - train on 8 NPUs
        ```
         cd scripts
         ./run_s8_beta.sh
        ```

***Note***: As the time consumption of the training for single NPU is much higher than that of 8 NPUs, we mainly experiment training using 8 NPUs.


### 4. Test
Test results will be saved as log file under `eval/${DEVICE_ID}/resnet_101/training.log`. The value for DEVICE_ID is 
specified in the scripts

- for the model trained with OS=16
```
cd scripts
./test_1p_s16_beta.sh

```
- for the model trained with OS=8
```
cd scripts
./test_1p_s8_beta.sh

```
- for the model trained with OS=8, multi_scale inputs
```
cd scripts
./test_ms_beta.sh

```
- for the model trained with OS=8,multi_scale inputs, random horizontal flip 
```
cd scripts
./test_ms_flip_beta.sh

```


## Advanced
### Commmand-line options


```
  --tf_initial_checkpoint           path to checkpoint of pretrained resnet_v1_101, default None
  --model_variant                   the backbone of model, default mobilenet_v2
  --atrous_rate                     the rate for atrous conv, default [1]
  --train_split                     the split for the data, default train
  --dataset                         name of dataset, default pascal_voc_seg
  --dataset_dir                     train dataset directory, default None
  --train_batch_size                mini-batch size per npu, default 8 
  --base_learning_rate              initial learning rate
  --weight_decay                    weight decay factor, default: 4e-5
  --momentum                        momentum factor, default: 0.9
  --training_number_of_steps        the number of training steps , default 30000
  --learning_policy                 the lr scheduling policy, default poly
  --bias_multiplier                 the gradient scale factor for bias , default 2.0
  --mode                            the mode to run the program , default train
  --fine_tune_batch_norm            flag indicates whether to fine-tune Batch-norm parameters, default True
  --output_stride                   the ratio of input to output spatial resolution, default 16
  --iterations_per_loop             the number of training step done in device before parameter sent back to host, default 10
  --log_name                        the name of training log file, default training.log
```
for a complete list of options, please refer to `train_npu.py` and `common.py`

### Training process

All the results of the training will be stored in the directory `results`.
Script will store:
 - checkpoints
 - log
 
## Performance

### Result

Our result were obtained by running the applicable training script. To achieve the same results, follow the steps in the Quick Start Guide.

#### Training 
For training, two-round training procedure is used. OS denotes output_stride.


| **iterations** | batch_szie    | OS             |
| :--------:     | :-----------: |:-----------:   |
|    15000+7000  | 8 * 8         | 16             |
|    15000+10000 | 8 * 8         | 8              |

#### Evaluation results 
The model is evaluated on VOC2012 val set. OS denotes output_stride, MS denotes multi_scale.

| **training OS**   | evaluation OS | MS inputs  | input flip | mIoU       |
| :----------------:| :----------:  | :------:   |:------:    |:--------:  | 
|    16             |     16        | N          |  N         | 77.50%     |
|    8              |     8         | N          |  N         | 78.87%     |
|    8              |     8         | Y          |  N         | 80.36%     |
|    8              |     8         | Y          |  Y         | 80.63%     |


#### Training performance 

| **NPUs** | output_stride     | batch size        | train performance |
| :------: | :---------------: | :---------------: |:---------------:  |
|    1     |     16            | 32*1              |  37+  FPS         |
|    8     |     16            | 8*8               |  275+ FPS         |
|    1     |     8             | 16*1              |  17+  FPS         |
|    8     |     8             | 8*8               |  137+ FPS         |










