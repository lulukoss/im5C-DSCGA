"""
@File: im5C-DSCGA.py
@Time: 2023/4/22 11:31
@Author:lulu9825@163.com
@desc:

"""
import pandas as pd
import numpy as np
from keras.utils.np_utils import to_categorical
from keras.callbacks import EarlyStopping

from keras.layers import Input, Conv1D, AveragePooling1D, GlobalAveragePooling1D, \
    Dropout, Dense, Activation, Concatenate, Multiply, GlobalMaxPooling1D, Add, GRU, \
    LSTM, Bidirectional, Conv2D, AveragePooling2D, BatchNormalization, Flatten, GlobalAveragePooling2D, \
    GlobalMaxPooling2D, Reshape, Permute, multiply, Lambda, add, subtract, MaxPooling2D, LeakyReLU, ELU
from keras.regularizers import l1, l2
from keras.optimizer_v2.adam import Adam
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, roc_curve, mean_absolute_error,  make_scorer
from keras.models import Model, load_model
import tensorflow as tf
from keras import backend as K
from sklearn import linear_model
from sklearn.model_selection import train_test_split
from sklearn.model_selection import KFold
from sklearn.model_selection import StratifiedKFold  
from sklearn.ensemble import VotingClassifier
from sklearn.ensemble import StackingClassifier
from sklearn.linear_model import LogisticRegression
from keras.layers import Layer
from keras import initializers

import warnings

warnings.filterwarnings("ignore")



def read_fasta(fasta_file_name):
    seqs = []
    seqs_num = 0
    file = open(fasta_file_name)

    for line in file.readlines():
        seq = line.strip()
        if seq.endswith('1'):
            seqs_num = seqs_num + 1
            seq = seq.replace('+1', '')
            seq = seq.replace('-1', '')
            seq = seq.rstrip()
            seqs.append(seq)
            continue
    return seqs


def to_one_hot(seqs):
    base_dict = {
        'a': 0, 'c': 1, 'g': 2, 'u': 3,
        'A': 0, 'C': 1, 'G': 2, 'U': 3
    }

    one_hot_4_seqs = []
    for seq in seqs:

        one_hot_matrix = np.zeros([4, len(seq)], dtype=float)
        index = 0
        for seq_base in seq:
            one_hot_matrix[base_dict[seq_base], index] = 1
            index = index + 1

        one_hot_4_seqs.append(one_hot_matrix)
    return one_hot_4_seqs


def to_properties_density_code(seqs):
    properties_code_dict = {
        'A': [1, 1, 1], 'C': [0, 1, 0], 'G': [1, 0, 0], 'U': [0, 0, 1],
        'a': [1, 1, 1], 'c': [0, 1, 0], 'g': [1, 0, 0], 'u': [0, 0, 1]
    }
    properties_code = []
    for seq in seqs:
        properties_matrix = np.zeros([4, len(seq)], dtype=float)
        A_num = 0
        C_num = 0
        G_num = 0
        T_num = 0
        All_num = 0
        for seq_base in seq:
            if seq_base == "A":
                All_num += 1
                A_num += 1
                Density = A_num / All_num
                properties_matrix[:, All_num - 1] = properties_code_dict[seq_base] + [Density]
            if seq_base == "C":
                All_num += 1
                C_num += 1
                Density = C_num / All_num
                properties_matrix[:, All_num - 1] = properties_code_dict[seq_base] + [Density]
            if seq_base == "G":
                All_num += 1
                G_num += 1
                Density = G_num / All_num
                properties_matrix[:, All_num - 1] = properties_code_dict[seq_base] + [Density]
            if seq_base == "T":
                All_num += 1
                T_num += 1
                Density = T_num / All_num
                properties_matrix[:, All_num - 1] = properties_code_dict[seq_base] + [Density]
        properties_code.append(properties_matrix)
    return properties_code


def show_performance(y_true, y_pred):
    
    TP, FP, FN, TN = 0, 0, 0, 0

    for i in range(len(y_true)):
        if y_true[i] == 1:
            if y_pred[i] > 0.5:
                TP += 1
            else:
                FN += 1
        if y_true[i] == 0:
            if y_pred[i] > 0.5:
                FP += 1
            else:
                TN += 1

    
    Sn = TP / (TP + FN + 1e-06)
    
    Sp = TN / (FP + TN + 1e-06)
    
    Acc = (TP + TN) / len(y_true)
    
    MCC = ((TP * TN) - (FP * FN)) / np.sqrt((TP + FP) * (TP + FN) * (TN + FP) * (TN + FN) + 1e-06)

    return Sn, Sp, Acc, MCC


def performance_mean(performance):
    print('Sn = %.4f ± %.4f' % (np.mean(performance[:, 0]), np.std(performance[:, 0])))
    print('Sp = %.4f ± %.4f' % (np.mean(performance[:, 1]), np.std(performance[:, 1])))
    print('Acc = %.4f ± %.4f' % (np.mean(performance[:, 2]), np.std(performance[:, 2])))
    print('Mcc = %.4f ± %.4f' % (np.mean(performance[:, 3]), np.std(performance[:, 3])))
    print('Auc = %.4f ± %.4f' % (np.mean(performance[:, 4]), np.std(performance[:, 4])))


def conv_factory(x, filters, dropout_rate, weight_decay=1e-4):
    x = Activation('relu')(x)
    x = Conv2D(filters=filters,
               kernel_size=(3, 3),
               kernel_initializer="he_normal",
               padding="same",
               use_bias=False,
               kernel_regularizer=l2(weight_decay))(x)
    x = Dropout(dropout_rate)(x)
    return x


def transition(x, filters, dropout_rate, weight_decay=1e-4):
    # x = Activation('relu')(x)
    x = Conv2D(filters=filters,
               kernel_size=(1, 1),
               kernel_initializer="he_normal",
               padding="same",
               use_bias=False,
               kernel_regularizer=l2(weight_decay))(x)
    x = Dropout(dropout_rate)(x)
    x = AveragePooling2D(pool_size=(2, 2), strides=(2, 2))(x)
    x = BatchNormalization(axis=-1)(x)
    return x


def denseblock(x, layers, filters, growth_rate, dropout_rate=None, weight_decay=1e-4):
    list_feature_map = [x]
    
    for i in range(layers):
        x = conv_factory(x, growth_rate,
                         dropout_rate, weight_decay)
        list_feature_map.append(x)
        x = Concatenate(axis=-1)(list_feature_map)
        filters = filters + growth_rate
    return x, filters


# 通道注意力机制
def channel_attention(input_feature, ratio=8):
    channel = input_feature.shape[-1]

    shared_layer_one = Dense(channel // ratio,
                             activation='relu',
                             kernel_initializer='he_normal',
                             use_bias=True,
                             bias_initializer='zeros')
    shared_layer_two = Dense(channel,
                             kernel_initializer='he_normal',
                             use_bias=True,
                             bias_initializer='zeros')

    avg_pool = GlobalAveragePooling2D()(
        input_feature)  # GlobalAveragePooling2D 全局平均池化  只剩下batchsize与channel两个维度。从形状上看：[B,H,W,C] → [B,C]
    avg_pool = Reshape((1, 1, channel))(avg_pool)  # 改变shape：宽度，高度，深度（拉成一个向量，这样才能喂到MLP）
    # assert avg_pool._keras_shape[1:] == (1,1,channel)
    avg_pool = shared_layer_one(avg_pool)
    # assert avg_pool._keras_shape[1:] == (1,1,channel//ratio)
    avg_pool = shared_layer_two(avg_pool)
    # assert avg_pool._keras_shape[1:] == (1,1,channel)

    max_pool = GlobalMaxPooling2D()(
        input_feature)  # GlobalMaxPooling2D 全局最大池化  只剩下batchsize与channel两个维度。从形状上看：[B,H,W,C] → [B,C]
    max_pool = Reshape((1, 1, channel))(max_pool)
    # assert max_pool._keras_shape[1:] == (1,1,channel)
    max_pool = shared_layer_one(max_pool)
    # assert max_pool._keras_shape[1:] == (1,1,channel//ratio)
    max_pool = shared_layer_two(max_pool)
    # assert max_pool._keras_shape[1:] == (1,1,channel)

    cbam_feature = Add()([avg_pool, max_pool])  # 处理后的结果相加
    cbam_feature = Activation('sigmoid')(cbam_feature)  # 获得各通道的权重图

    return multiply([input_feature, cbam_feature])


# 空间注意力机制
def spatial_attention(input_feature):
    kernel_size = 7

    channel = input_feature.shape[-1]
    cbam_feature = input_feature

    avg_pool = Lambda(lambda x: K.mean(x, axis=3, keepdims=True))(cbam_feature)  # 对张量求平均值，改变第三维坐标，并保持原本维度
    # assert avg_pool._keras_shape[-1] == 1
    max_pool = Lambda(lambda x: K.max(x, axis=3, keepdims=True))(cbam_feature)
    # assert max_pool._keras_shape[-1] == 1
    concat = Concatenate(axis=3)([avg_pool, max_pool])  # 拼接
    # assert concat._keras_shape[-1] == 2
    cbam_feature = Conv2D(filters=1,
                          kernel_size=kernel_size,
                          strides=1,
                          padding='same',
                          activation='sigmoid',
                          kernel_initializer='he_normal',
                          use_bias=False)(concat)

    return multiply([input_feature, cbam_feature])


# cbam
def cbam_block(cbam_feature, ratio=8):
    channel_feature = channel_attention(cbam_feature, ratio)
    spatial_feature = spatial_attention(cbam_feature)
    return channel_feature, spatial_feature


class AttLayer(Layer):
    def __init__(self, attention_dim, **kwargs):
        # self.init = initializers.get('normal')
        self.init = initializers.RandomNormal(seed=10)
        self.supports_masking = True
        self.attention_dim = attention_dim
        super(AttLayer, self).__init__(**kwargs)

    def get_config(self):
        config = super().get_config()
        config.update({
            "attention_dim": self.attention_dim
        })
        return config

    def build(self, input_shape):
        assert len(input_shape) == 3
        self.W = K.variable(self.init((input_shape[-1], self.attention_dim)), name='W')
        self.b = K.variable(self.init((self.attention_dim,)), name='b')
        self.u = K.variable(self.init((self.attention_dim, 1)), name='u')
        self._trainable_weights = [self.W, self.b, self.u]
        super(AttLayer, self).build(input_shape)

    def compute_mask(self, inputs, mask=None):
        return mask

    def call(self, x, mask=None):
        # size of x :[batch_size, sel_len, attention_dim]
        # size of u :[batch_size, attention_dim]
        # uit = tanh(xW+b)
        uit = K.tanh(K.bias_add(K.dot(x, self.W), self.b))
        ait = K.dot(uit, self.u)
        ait = K.squeeze(ait, -1)

        ait = K.exp(ait)

        if mask is not None:
            # Cast the mask to floatX to avoid float64 upcasting in theano
            ait *= K.cast(mask, K.floatx())
        ait /= K.cast(K.sum(ait, axis=1, keepdims=True) +
                      K.epsilon(), K.floatx())
        ait = K.expand_dims(ait)
        weighted_input = x * ait
        output = K.sum(weighted_input, axis=1)

        return output

    def compute_output_shape(self, input_shape):
        return (input_shape[0], input_shape[-1])


def build_model(windows=8, denseblocks=5, layers=4, filters=96,
                growth_rate=32, dropout_rate=0.2, weight_decay=1e-4):
    input_1 = Input(shape=(windows, 41, 1))

    for i in range(denseblocks - 1):
        # Add denseblock
        x_1, filters_1 = denseblock(input_1, layers=layers,
                                    filters=filters, growth_rate=growth_rate,
                                    dropout_rate=dropout_rate, weight_decay=weight_decay)

        x_1 = BatchNormalization(axis=-1)(x_1)


        # Add transition
        x_1 = transition(x_1, filters=filters_1,
                         dropout_rate=dropout_rate, weight_decay=weight_decay)
    # The last denseblock
    # Add denseblock
    x_1, filters_1 = denseblock(x_1, layers=layers,
                                filters=filters, growth_rate=growth_rate,
                                dropout_rate=dropout_rate, weight_decay=weight_decay)


    x_1 = BatchNormalization(axis=-1)(x_1)
    print(x_1)

    # 添加注意力机制层
    channel_feature, spatial_feature = cbam_block(x_1)

    # 点积
    x_multiply = multiply([channel_feature, spatial_feature])

    x_2 = AveragePooling2D(pool_size=(4, 1), strides=1, padding='valid')(x_multiply)

    x_2 = K.squeeze(x_2, 1)

    x_2 = Bidirectional(GRU(500, return_sequences=True))(x_2)
    x_2 = Dropout(0.5)(x_2)

    x_2 = Bidirectional(GRU(500, return_sequences=True))(x_2)
    x_2 = Dropout(0.5)(x_2)

    x_2 = AttLayer(500)(x_2)

    x = Flatten()(x_2)

    x = Dense(units=240, activation="sigmoid", use_bias=False,
              kernel_initializer='he_normal',
              kernel_regularizer=l2(weight_decay))(x)

    x = Dropout(0.5)(x)

    x = Dense(units=40, activation="sigmoid", use_bias=False,
              kernel_initializer='he_normal',
              kernel_regularizer=l2(weight_decay))(x)

    x = Dropout(0.2)(x)

    x = Dense(units=2, activation="softmax", use_bias=False,
              kernel_initializer='he_normal',
              kernel_regularizer=l2(weight_decay))(x)


    inputs = [input_1]
    outputs = [x]

    model = Model(inputs=inputs, outputs=outputs, name="DSCm5C")

    # optimizer = SGD(lr=1e-4, decay=1e-5, momentum=0.9, nesterov=True)

    optimizer = Adam(lr=1e-4, epsilon=1e-8)


    model.compile(loss='categorical_crossentropy', optimizer=optimizer, metrics=['accuracy'])

    return model



if __name__ == '__main__':

    np.random.seed(0)
    tf.random.set_seed(1)  # for reproducibility


    train_pos_seqs = np.array(read_fasta('../lulu/Dataset/train_positive_data.fasta'))
    train_neg_seqs = np.array(read_fasta('../lulu/Dataset/train_negative_data.fasta'))

    train_seqs = np.concatenate((train_pos_seqs, train_neg_seqs), axis=0)


    train_onehot = np.array(to_one_hot(train_seqs)).astype(np.float32)
    train_properties_code = np.array(to_properties_density_code(train_seqs)).astype(np.float32)

    train = np.concatenate((train_onehot, train_properties_code), axis=1)



    train_label = np.array([1] * 46529 + [0] * 46529).astype(np.float32)
    train_label = to_categorical(train_label, num_classes=2)


    test_pos_seqs = np.array(read_fasta('../lulu/Dataset/test_positive_data.fasta'))
    test_neg_seqs = np.array(read_fasta('../lulu/Dataset/test_negative_data.fasta'))

    test_seqs = np.concatenate((test_pos_seqs, test_neg_seqs), axis=0)


    test_onehot = np.array(to_one_hot(test_seqs)).astype(np.float32)
    test_properties_code = np.array(to_properties_density_code(test_seqs)).astype(np.float32)

    test = np.concatenate((test_onehot, test_properties_code), axis=1)


    test_label = np.array([1] * 11630 + [0] * 11630).astype(np.float32)
    test_label = to_categorical(test_label, num_classes=2)

    BATCH_SIZE = 1024
    EPOCHS = 300
    weights = {0: 1, 1: 1}
    n = 5
    k_fold = KFold(n_splits=n, shuffle=True, random_state=42)


    tprs = []
    mean_fpr = np.linspace(0, 1, 100)
    all_performance = []
    for fold_count, (train_index, val_index) in enumerate(k_fold.split(train)):
        print('*' * 30 + ' fold ' + str(fold_count+1) + ' ' + '*' * 30)
        tra, val = train[train_index], train[val_index]
        tra_label, val_label = train_label[train_index], train_label[val_index]

        model1 = build_model()
        model1.fit(x=tra, y=tra_label, validation_data=(val, val_label), epochs=EPOCHS,
                   batch_size=BATCH_SIZE, shuffle=True, class_weight=weights,
                   callbacks=[EarlyStopping(monitor='val_loss', patience=20, mode='auto')],
                   verbose=1)

        model1.save('../lulu/DSCGAModel/DSCGAm5C_model1_train' + str(fold_count + 1) + '_1.h5')
        del model1

        model2 = build_model()
        model2.fit(x=tra, y=tra_label, validation_data=(val, val_label), epochs=EPOCHS,
                   batch_size=BATCH_SIZE, shuffle=True, class_weight=weights,
                   callbacks=[EarlyStopping(monitor='val_loss', patience=20, mode='auto')],
                   verbose=1)

        model2.save('../lulu/DSCGAModel/DSCGAm5C_model2_train' + str(fold_count + 1) + '_2.h5')
        del model2

        model3 = build_model()
        model3.fit(x=tra, y=tra_label, validation_data=(val, val_label), epochs=EPOCHS,
                   batch_size=BATCH_SIZE, shuffle=True, class_weight=weights,
                   callbacks=[EarlyStopping(monitor='val_loss', patience=20, mode='auto')],
                   verbose=1)

        model3.save('../lulu/DSCGAModel/DSCGAm5C_model3_train' + str(fold_count + 1) + '_3.h5')
        del model3

        model1 = load_model('../lulu/DSCGAModel/DSCGAm5C_model1_train' + str(fold_count + 1) + '_1.h5',
                            custom_objects={'AttLayer': AttLayer})

        model2 = load_model('../lulu/DSCGAModel/DSCGAm5C_model2_train' + str(fold_count + 1) + '_2.h5',
                            custom_objects={'AttLayer': AttLayer})

        model3 = load_model('../lulu/DSCGAModel/DSCGAm5C_model3_train' + str(fold_count + 1) + '_3.h5',
                            custom_objects={'AttLayer': AttLayer})

        val_score1 = model1.predict(val)
        val_score2 = model2.predict(val)
        val_score3 = model3.predict(val)
        all_score = val_score1 + val_score2 + val_score3
        val_score = all_score / 3


        Sn, Sp, Acc, MCC = show_performance(val_label[:, 1], val_score[:, 1])
        AUC = roc_auc_score(val_label[:, 1], val_score[:, 1])
        print('Sn = %f, Sp = %f, Acc = %f, MCC = %f, AUC = %f' % (Sn, Sp, Acc, MCC, AUC))

        performance = [Sn, Sp, Acc, MCC, AUC]
        all_performance.append(performance)

        '''Mapping the ROC'''
        fpr, tpr, thresholds = roc_curve(val_label[:, 1], val_score[:, 1], pos_label=1)

        tprs.append(np.interp(mean_fpr, fpr, tpr))
        tprs[-1][0] = 0.0
        plt.plot(fpr, tpr, label='ROC fold {} (AUC={:.4f})'.format(str(fold_count + 1), AUC))

    fold_count += 1
    all_performance = np.array(all_performance)
    print('5 fold result:', all_performance)
    performance_mean = performance_mean(all_performance)


    '''Mapping the ROC'''
    plt.plot([0, 1], [0, 1], '--', color='red')
    mean_tpr = np.mean(tprs, axis=0)
    mean_tpr[-1] = 1.0

    mean_auc = np.mean(np.array(all_performance)[:, 4])

    plt.plot(mean_fpr, mean_tpr, color='b', label=r'Mean ROC (AUC=%0.4f)' % (mean_auc), lw=2, alpha=.8)

    plt.title('ROC Curve')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.savefig('../lulu/images/DSCGAm5C/train_ROC_Curve.jpg', dpi=1200, bbox_inches='tight')
    plt.legend(loc='lower right')
    plt.show()


    model1 = build_model()
    model1.fit(x=train, y=train_label, validation_data=(test, test_label), epochs=EPOCHS,
               batch_size=BATCH_SIZE, shuffle=True, class_weight=weights,
               callbacks=[EarlyStopping(monitor='val_loss', patience=20, mode='auto')],
               verbose=1)

    model1.save('../lulu/DSCGAModel/DSCGAm5C_model1_test.h5')

    del model1

    model2 = build_model()
    model2.fit(x=train, y=train_label, validation_data=(test, test_label), epochs=EPOCHS,
               batch_size=BATCH_SIZE, shuffle=True, class_weight=weights,
               callbacks=[EarlyStopping(monitor='val_loss', patience=20, mode='auto')],
               verbose=1)

    model2.save('../lulu/DSCGAModel/DSCGAm5C_model2_test.h5')

    del model2

    model3 = build_model()
    model3.fit(x=train, y=train_label, validation_data=(test, test_label), epochs=EPOCHS,
               batch_size=BATCH_SIZE, shuffle=True, class_weight=weights,
               callbacks=[EarlyStopping(monitor='val_loss', patience=20, mode='auto')],
               verbose=1)

    model3.save('../lulu/DSCGAModel/DSCGAm5C_model3_test.h5')


    del model3


    model1 = load_model('../lulu/DSCGAModel/DSCGAm5C_model1_test.h5', custom_objects={'AttLayer': AttLayer})
    model2 = load_model('../lulu/DSCGAModel/DSCGAm5C_model2_test.h5', custom_objects={'AttLayer': AttLayer})
    model3 = load_model('../lulu/DSCGAModel/DSCGAm5C_model3_test.h5', custom_objects={'AttLayer': AttLayer})

    test_score1 = model1.predict(test)
    test_score2 = model2.predict(test)
    test_score3 = model3.predict(test)
    all_score = test_score1 + test_score2 + test_score3
    test_score = all_score / 3

    Sn, Sp, Acc, MCC = show_performance(test_label[:, 1], test_score[:, 1])
    AUC = roc_auc_score(test_label[:, 1], test_score[:, 1])

    print('-----------------------------------------------test---------------------------------------')
    print('Sn = %f, Sp = %f, Acc = %f, MCC = %f, AUC = %f' % (Sn, Sp, Acc, MCC, AUC))

    '''Mapping the test ROC'''
    plt.plot([0, 1], [0, 1], '--', color='red')
    test_fpr, test_tpr, thresholds = roc_curve(test_label[:, 1], test_score[:, 1], pos_label=1)

    plt.plot(test_fpr, test_tpr, color='b', label=r'DSCGAm5C (AUC=%0.4f)' % (AUC), lw=2, alpha=.8)

    plt.title('ROC Curve')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.savefig('../lulu/images/DSCGAm5C/test_ROC_Curve.jpg', dpi=1200, bbox_inches='tight')
    plt.legend(loc='lower right')
    plt.show()
