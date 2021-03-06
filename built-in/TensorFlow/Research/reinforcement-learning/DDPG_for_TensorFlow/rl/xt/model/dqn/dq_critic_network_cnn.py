"""
@Author: Huaqiang Wang, Jack Qian
@license : Copyright(C), Huawei
"""
from __future__ import division, print_function
import tensorflow as tf
from xt.model.tf_compat import Conv2D, Dense, Flatten, Input, Model, Adam, Lambda, K
from xt.model.dqn.default_config import LR
from xt.model import XTModel
from xt.util.common import import_config

from xt.framework.register import Registers


@Registers.model.register
class DqCriticNetworkCnn(XTModel):
    """docstring for ."""
    def __init__(self, model_info):
        model_config = model_info.get('model_config', None)
        import_config(globals(), model_config)

        self.state_dim = model_info['state_dim']
        self.action_dim = model_info['action_dim']
        self.learning_rate = LR
        super(DqCriticNetworkCnn, self).__init__(model_info)

    def create_model(self, model_info):
        """method for creating DQN CNN network"""
        state = Input(shape=self.state_dim, dtype="uint8")
        state1 = Lambda(lambda x: K.cast(x, dtype='float32') / 255.)(state)
        convlayer = Conv2D(32, (8, 8), strides=(4, 4), activation='relu', padding='valid')(state1)
        convlayer = Conv2D(64, (4, 4), strides=(2, 2), activation='relu', padding='valid')(convlayer)
        convlayer = Conv2D(64, (3, 3), strides=(1, 1), activation='relu', padding='valid')(convlayer)
        flattenlayer = Flatten()(convlayer)
        denselayer = Dense(256, activation='relu')(flattenlayer)
        value = Dense(self.action_dim, activation='linear')(denselayer)
        model = Model(inputs=state, outputs=value)
        adam = Adam(lr=self.learning_rate, clipnorm=10.)
        model.compile(loss='mse', optimizer=adam)
        if model_info.get("summary"):
            model.summary()

        self.infer_state = tf.placeholder(tf.uint8, name="infer_input",
                                          shape=(None, ) + tuple(self.state_dim))
        self.infer_v = model(self.infer_state)
        self.sess.run(tf.initialize_all_variables())
        return model

    def predict(self, state):
        """
        Do predict use the newest model.
        :param state:
        :return:
        """
        with self.graph.as_default():
            K.set_session(self.sess)
            feed_dict = {self.infer_state: state}
            return self.sess.run(self.infer_v, feed_dict)
