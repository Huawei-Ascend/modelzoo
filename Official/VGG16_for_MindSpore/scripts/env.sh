#!/bin/bash
LOCAL_HIAI=/usr/local/HiAI
export PATH=${LOCAL_HIAI}/fwkacllib/ccec_compiler/bin:${PATH}
export TBE_IMPL_PATH=${LOCAL_HIAI}/opp/op_impl/built-in/ai_core/tbe
export PYTHONPATH=${TBE_IMPL_PATH}:${PYTHONPATH}
export LD_LIBRARY_PATH=${LOCAL_HIAI}/fwkacllib/lib64:${LOCAL_HIAI}/add-ons:${LD_LIBRARY_PATH}

# !!! ADD YOUR OWN PYTHONPATH
export PYTHONPATH=/path/to/modelzoo_vgg16:${PYTHONPATH}