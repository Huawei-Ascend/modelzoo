## 1、原始模型
https://www.huaweicloud.com/ascend/resources/modelzoo/Models/d82f7cc28e64493cafe95187d6a2d7a9, 下载pb模型

## 2、转om模型
obs链接：obs://modelzoo-train-atc/003_Atc_Models/nkxiaolei/SqueezeNet/squeeze_tf.om

ATC转换命令：
```
/home/HwHiAiUser/Ascend/ascend-toolkit/20.10.0.B023/atc/bin/atc --output_type=FP32 --input_shape="ImageTensor:1,227,227,3" --check_report=/root/modelzoo/squeeze_tf/device/network_analysis.report --input_format=NHWC --output="/root/modelzoo/squeeze_tf/device/squeeze_tf" --soc_version=Ascend310 --framework=3 --model="/home/HwHiAiUser/Orignal_Model/squeeze_tf.pb" 
```

## 3、将下载的om文件放在model文件夹

## 4、编译msame推理工具
参考https://github.com/Huawei-Ascend/tools/tree/ccl/msame, 编译出msame推理工具

## 5、性能测试
使用msame推理工具，参考如下命令，发起推理性能测试： 

./msame --model model/squeeze_tf.om --output output/ --loop 100
```
[INFO] output data success
Inference average time: 0.931910 ms
Inference average time without first time: 0.928596 ms
[INFO] unload model success, model Id is 1
[INFO] Execute sample success.
```
1Batch，shape:1x227x227x3，不带AIPP，平均推理性能0.928ms

## 6、精度测试：

### 5.1 下载ImageNet 2012 val数据集

### 5.2 图片预处理
下载好的数据集JPEG图片放在任意其他目录(以originnal_pic为例)，执行预处理脚本生成bin文件：
```
python3.7.5 img_preprocess.py ./originnal_pic/ ./input
```
生成的bin文件至input目录，标签文件val_map.txt放至ground_truth目录

### 5.3 执行推理和精度计算的shell脚本
./start_inference.sh
```
ILSVRC2012_val_00049996.JPEG, inference label:283, gt_label:283
ILSVRC2012_val_00049997.JPEG, inference label:50, gt_label:26
ILSVRC2012_val_00049998.JPEG, inference label:223, gt_label:232
ILSVRC2012_val_00049999.JPEG, inference label:617, gt_label:982
ILSVRC2012_val_00050000.JPEG, inference label:105, gt_label:355
```
50000张Val数据集在NPU上推理的top1精度为：0.550， 论文参考精度值：0.575