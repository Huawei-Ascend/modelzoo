# -*- coding:utf-8 -*-
"""Run benchmark."""
import os
import sys
import vega


def _append_env():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.insert(0, dir_path)
    if "PYTHONPATH" not in os.environ:
        os.environ["PYTHONPATH"] = dir_path
    else:
        os.environ["PYTHONPATH"] += ":{}".format(dir_path)


if __name__ == '__main__':
    if len(sys.argv) not in [3, 4] and not sys.argv[1].endswith(".yml"):
        print("Usage:")
        print("    python3 ./run_benchmark_roma.py <algorithm's config file> [pytorch]|[tensorflow] <zone>")
        print("for example:")
        print("    python3 ./run_benchmark_roma.py ./nas/cars/cars.yml hn1_y")
        print("    python3 ./run_benchmark_roma.py ./nas/cars/cars.yml tensorflow hn1_y")
    # set backend
    if len(sys.argv) == 4 and sys.argv[2] in ["pytorch", "p", "tensorflow", "t"]:
        if sys.argv[2] in ["pytorch", "p"]:
            vega.set_backend("pytorch")
        else:
            vega.set_backend("tensorflow")
    # init roma env
    from roma.env import init_env
    init_env(sys.argv[-1])
    # import class lazily
    cfg_file = sys.argv[1]
    if cfg_file.endswith("fmd.yml"):
        _append_env()
        from algs.fully_train.fmd import FmdNetwork
    elif cfg_file.endswith("spnas.yml"):
        _append_env()
        import vega.algorithms.nas.sp_nas
    # run vega
    vega.run(sys.argv[1])
