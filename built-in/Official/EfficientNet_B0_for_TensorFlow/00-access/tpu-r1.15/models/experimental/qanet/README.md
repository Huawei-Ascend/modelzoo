# QANet

This code is a TPU friendly variant of the model presented in
the QANet paper for the DAWNBench competition: https://arxiv.org/abs/1804.09541

The model is stripped down from the original and will be improved to match the
full performance over time.  It achieves 75 F1 in less than 10 minutes on a TPU.


## Prerequisites

### Setup a Google Cloud project

Follow the instructions at the [Quickstart Guide](https://cloud.google.com/tpu/docs/quickstart)
to get a GCE VM with access to Cloud TPU.

To run this model, you will need:

* A GCE VM instance with an associated Cloud TPU resource
* A GCS bucket to store your data and training checkpoints

### Formatting the data

The data is expected to be formatted in TFRecord format, as generated by the preprocess.py script. Note that we do not yet support SQuAD-V2 at this time.

We also need the fasttext embeddings, which we filter down to just the subset of words present in the train and dev set to speed up start time.  This filters the file
from 2gb to about 100mb.

```
DATA_DIR=gs://qanet-data/squad_data
LOCAL_SQUAD_DATA=/home/$USER/squad_data
mkdir $LOCAL_SQUAD_DATA
curl https://rajpurkar.github.io/SQuAD-explorer/dataset/train-v1.1.json > $LOCAL_SQUAD_DATA/train-v1.1.json
curl https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json > $LOCAL_SQUAD_DATA/dev-v1.1.json
curl https://s3-us-west-1.amazonaws.com/fasttext-vectors/crawl-300d-2M.vec.zip > $LOCAL_SQUAD_DATA/crawl-300d-2M.vec.zip
unzip $LOCAL_SQUAD_DATA/crawl-300d-2M.vec.zip -d $LOCAL_SQUAD_DATA
python preprocess.py \
  --input_path $LOCAL_SQUAD_DATA/train-v1.1.json,$LOCAL_SQUAD_DATA/dev-v1.1.json \
  --embedding_path $LOCAL_SQUAD_DATA/crawl-300d-2M.vec \
  --output_path $DATA_DIR
gsutil cp $LOCAL_SQUAD_DATA/dev-v1.1.json $LOCAL_SQUAD_DATA/train-v1.1.json $DATA_DIR
```


## Training the model

Train the model by executing the following command (substituting the appropriate
values):

```
MODEL_DIR=gs://qanet-data/model
python run.py \
  --tpu=$TPU_NAME \
  --data_path=$DATA_DIR \
  --model_dir=$MODEL_DIR \
  --config=dataset.train_batch_size=32,steps_per_epoch=20000,num_epochs=5
```

The config flags fills out the standard model config specified in `model.py`.
You may also provide a path to a json config as the --config_file argument.


If you are not running this script on a GCE VM in the same project and zone as
your Cloud TPU, you will need to add the `--project` and `--zone` flags
specifying the corresponding values for the Cloud TPU you'd like to use.


This will train a QANet model on SQuAD with 32 batch size on a
single Cloud TPU. With the default flags, the model should train to 75+ F1 in
under 10 minutes.  The SQuAD training set contains about 90,000 examples, so
each round trip on the TPU completes several epochs over the data to save time
in checkpointing.

## Evaluating the model

Our evaluation makes use of py_funcs, which unfortunately do not work on TPU.
As a results, we run evaluation in a separate VM.  Each evaluation takes about
5 minutes on this CPU machine:

```
gcloud compute instances create\
  qanet-eval-vm\
  --machine-type=n1-highcpu-64\
  --image-project=ml-images\
  --image-family=tf-1-9\
  --scopes=cloud-platform
```

ssh to the machine, clone the repo, go to this directory, and run:

```
python run.py  --data_path=$DATA_DIR   --model_dir=$MODEL_DIR --mode eval
```


You can launch TensorBoard (e.g. `tensorboard --logdir=$MODEL_DIR`) to view loss
curves and other metadata regarding your training run. (Note: if you launch
on your VM, be sure to configure ssh port forwarding or the GCE firewall rules
appropriately.)

## Questions?

Please contact ddohan@google.com with any questions related to this model.