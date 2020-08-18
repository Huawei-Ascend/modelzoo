import os
import cv2
import time
import random
import pyclipper
import numpy as np
from PIL import Image
import Polygon as plg
import mindspore.dataset.engine as de
import mindspore.dataset.transforms.vision.py_transforms as py_transforms

from src.config import config

__all__ = ['train_dataset_creator', 'test_dataset_creator']

def get_img(img_path):
    img = cv2.imread(img_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img

def get_imgs_names(root_dir):
    img_paths = [i for i in os.listdir(root_dir)
                 if os.path.splitext(i)[-1].lower() in ['.jpg', '.jpeg', '.png']]
    return img_paths

def get_bboxes(img, gt_path):
    h, w = img.shape[0:2]
    with open(gt_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    bboxes = []
    tags = []
    for line in lines:
        line = line.replace('\xef\xbb\xbf', '')
        line = line.replace('\ufeff', '')
        line = line.replace('\n', '')
        gt = line.split(",", 8)
        tag = False if gt[-1][0] == '#' else True
        box = [int(gt[i]) for i in range(8)]
        box = np.asarray(box) / ([w * 1.0, h * 1.0] * 4)
        bboxes.append(box)
        tags.append(tag)
    return np.array(bboxes), tags

def random_scale(img, min_size):
    h, w = img.shape[0:2]
    if max(h, w) > 1280:
        scale = 1280.0 / max(h, w)
        img = cv2.resize(img, dsize=None, fx=scale, fy=scale)

    h, w = img.shape[0:2]
    random_scale = np.array([0.5, 1.0, 2.0, 3.0])
    scale = np.random.choice(random_scale)
    if min(h, w) * scale <= min_size:
        scale = (min_size + 10) * 1.0 / min(h, w)
    img = cv2.resize(img, dsize=None, fx=scale, fy=scale)
    return img

def random_horizontal_flip(imgs):
    if random.random() < 0.5:
        for i in range(len(imgs)):
            imgs[i] = np.flip(imgs[i], axis=1).copy()
    return imgs

def random_rotate(imgs):
    max_angle = 10
    angle = random.random() * 2 * max_angle - max_angle
    for i in range(len(imgs)):
        img = imgs[i]
        w, h = img.shape[:2]
        rotation_matrix = cv2.getRotationMatrix2D((h / 2, w / 2), angle, 1)
        img_rotation = cv2.warpAffine(img, rotation_matrix, (h, w))
        imgs[i] = img_rotation
    return imgs

def random_crop(imgs, img_size):
    h, w = imgs[0].shape[0:2]
    th, tw = img_size
    if w == tw and h == th:
        return imgs

    if random.random() > 3.0 / 8.0 and np.max(imgs[1]) > 0:
        tl = np.min(np.where(imgs[1] > 0), axis=1) - img_size
        tl[tl < 0] = 0
        br = np.max(np.where(imgs[1] > 0), axis=1) - img_size
        br[br < 0] = 0
        br[0] = min(br[0], h - th)
        br[1] = min(br[1], w - tw)

        i = random.randint(tl[0], br[0])
        j = random.randint(tl[1], br[1])
    else:
        i = random.randint(0, h - th)
        j = random.randint(0, w - tw)

    for idx in range(len(imgs)):
        if len(imgs[idx].shape) == 3:
            imgs[idx] = imgs[idx][i:i + th, j:j + tw, :]
        else:
            imgs[idx] = imgs[idx][i:i + th, j:j + tw]
    return imgs

def scale(img, long_size=2240):
    h, w = img.shape[0:2]
    scale = long_size * 1.0 / max(h, w)
    img = cv2.resize(img, dsize=None, fx=scale, fy=scale)
    return img

def dist(a, b):
    return np.sqrt(np.sum((a - b) ** 2))

def perimeter(bbox):
    peri = 0.0
    for i in range(bbox.shape[0]):
        peri += dist(bbox[i], bbox[(i + 1) % bbox.shape[0]])
    return peri

def shrink(bboxes, rate, max_shr=20):
    rate = rate * rate
    shrinked_bboxes = []
    for bbox in bboxes:
        area = plg.Polygon(bbox).area()
        peri = perimeter(bbox)

        pco = pyclipper.PyclipperOffset()
        pco.AddPath(bbox, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        offset = min((int)(area * (1 - rate) / (peri + 0.001) + 0.5), max_shr)

        shrinked_bbox = pco.Execute(-offset)
        if len(shrinked_bbox) == 0:
            shrinked_bboxes.append(bbox)
            continue

        shrinked_bbox = np.array(shrinked_bbox)[0]
        if shrinked_bbox.shape[0] <= 2:
            shrinked_bboxes.append(bbox)
            continue

        shrinked_bboxes.append(shrinked_bbox)

    return np.array(shrinked_bboxes)

class TrainDataset:
    def __init__(self):
        self.is_transform = config.TRAIN_IS_TRANSFORM
        self.img_size = config.TRAIN_LONG_SIZE
        self.kernel_num = config.KERNEL_NUM
        self.min_scale = config.TRAIN_MIN_SCALE

        root_dir = os.path.join(os.path.join(os.path.dirname(__file__), '..'), config.TRAIN_ROOT_DIR)
        ic15_train_data_dir = root_dir + 'ch4_training_images/'
        ic15_train_gt_dir = root_dir + 'ch4_training_localization_transcription_gt/'

        self.img_size = self.img_size if (self.img_size is None or isinstance(self.img_size, tuple)) else (self.img_size, self.img_size)

        data_dirs = [ic15_train_data_dir]
        gt_dirs = [ic15_train_gt_dir]

        self.all_img_paths = []
        self.all_gt_paths = []

        for data_dir, gt_dir in zip(data_dirs, gt_dirs):
            img_names = [i for i in os.listdir(data_dir) if os.path.splitext(i)[-1].lower() in ['.jpg', '.jpeg', '.png']]

            img_paths = []
            gt_paths = []
            for idx, img_name in enumerate(img_names):
                img_path = os.path.join(data_dir, img_name)
                gt_name = 'gt_' + img_name.split('.')[0] + '.txt'
                gt_path = os.path.join(gt_dir, gt_name)
                img_paths.append(img_path)
                gt_paths.append(gt_path)

            self.all_img_paths.extend(img_paths)
            self.all_gt_paths.extend(gt_paths)

    def __getitem__(self, index):
        img_path = self.all_img_paths[index]
        gt_path = self.all_gt_paths[index]

        start0 = time.time()
        img = get_img(img_path)
        bboxes, tags = get_bboxes(img, gt_path)
        end0 = time.time()

        # multi-scale training
        if self.is_transform:
            img = random_scale(img, min_size=self.img_size[0])
        end1 = time.time()

        # get gt_text and training_mask
        img_h, img_w = img.shape[0: 2]
        gt_text = np.zeros((img_h, img_w), dtype=np.float32)
        training_mask = np.ones((img_h, img_w), dtype=np.float32)
        if bboxes.shape[0] > 0:
            bboxes = np.reshape(bboxes * ([img_w, img_h] * 4), (bboxes.shape[0], -1, 2)).astype('int32')
            for i in range(bboxes.shape[0]):
                cv2.drawContours(gt_text, [bboxes[i]], 0, i + 1, -1)
                if not tags[i]:
                    cv2.drawContours(training_mask, [bboxes[i]], 0, 0, -1)
        end2 = time.time()

        # get gt_kernels
        gt_kernels = []
        for i in range(1, self.kernel_num):
            rate = 1.0 - (1.0 - self.min_scale) / (self.kernel_num - 1) * i
            gt_kernel = np.zeros(img.shape[0:2], dtype=np.float32)
            kernel_bboxes = shrink(bboxes, rate)
            for i in range(kernel_bboxes.shape[0]):
                cv2.drawContours(gt_kernel, [kernel_bboxes[i]], 0, 1, -1)
            gt_kernels.append(gt_kernel)
        end3=time.time()

        # data augmentation
        if self.is_transform:
            imgs = [img, gt_text, training_mask]
            imgs.extend(gt_kernels)
            imgs = random_horizontal_flip(imgs)
            imgs = random_rotate(imgs)
            imgs = random_crop(imgs, self.img_size)
            img, gt_text, training_mask, gt_kernels = imgs[0], imgs[1], imgs[2], imgs[3:]
        end4=time.time()

        gt_text[gt_text > 0] = 1
        gt_kernels = np.array(gt_kernels)

        if self.is_transform:
            img = Image.fromarray(img)
            img = img.convert('RGB')
            img = py_transforms.RandomColorAdjust(brightness=32.0 / 255, saturation=0.5)(img)
        else:
            img = Image.fromarray(img)
            img = img.convert('RGB')

        img = py_transforms.ToTensor()(img)
        img = py_transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])(img)

        """Generator can only return np arrays"""
        gt_text = gt_text.astype(np.float32)
        gt_kernels = gt_kernels.astype(np.float32)
        training_mask = training_mask.astype(np.float32)

        return img, gt_text, gt_kernels, training_mask 

    def __len__(self):
        return len(self.all_img_paths)

def IC15_TEST_Generator():
    ic15_test_data_dir = config.TEST_ROOT_DIR + 'ch4_test_images/'
    img_size = config.INFER_LONG_SIZE

    img_size = img_size if (img_size is None or isinstance(img_size, tuple)) else (img_size, img_size)

    data_dirs = [ic15_test_data_dir]
    all_img_paths = []

    for data_dir in data_dirs:
        img_names = [i for i in os.listdir(data_dir) if os.path.splitext(i)[-1].lower() in ['.jpg', '.jpeg', '.png']]

        img_paths = []
        for idx, img_name in enumerate(img_names):
            img_path = data_dir + img_name
            img_paths.append(img_path)

        all_img_paths.extend(img_paths)

    dataset_length = len(all_img_paths)

    for index in range(dataset_length):
        img_path = all_img_paths[index]
        img_name = np.array(os.path.split(img_path)[-1])
        img = get_img(img_path)

        long_size = max(img.shape[:2])
        img_resized = np.zeros((long_size, long_size, 3), np.uint8)
        img_resized[:img.shape[0], :img.shape[1], :] = img
        img_resized = cv2.resize(img_resized, dsize=img_size)

        img_resized = Image.fromarray(img_resized)
        img_resized = img_resized.convert('RGB')
        img_resized = py_transforms.ToTensor()(img_resized)
        img_resized = py_transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])(img_resized)

        yield img, img_resized, img_name

def train_dataset_creator():
    cv2.setNumThreads(0)
    dataset = TrainDataset()
    ds = de.GeneratorDataset(dataset, ['img', 'gt_text', 'gt_kernels', 'training_mask'], num_parallel_workers=8)
    ds.set_dataset_size(config.TRAIN_DATASET_SIZE)
    #ds = ds.repeat(config.TRAIN_REPEAT_NUM)
    ds = ds.batch(config.TRAIN_BATCH_SIZE, drop_remainder=config.TRAIN_DROP_REMAINDER)
    ds = ds.shuffle(buffer_size=config.TRAIN_BUFFER_SIZE)
    return ds

def test_dataset_creator():
    ds = de.GeneratorDataset(IC15_TEST_Generator, ['img', 'img_resized', 'img_name'])
    ds.set_dataset_size(config.TEST_DATASET_SIZE)
    ds = ds.shuffle(config.TEST_BUFFER_SIZE)
    ds = ds.batch(1, drop_remainder=config.TEST_DROP_REMAINDER)
    return ds