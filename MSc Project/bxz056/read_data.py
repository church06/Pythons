import os
import os.path
from itertools import product

import bdpy
import h5py
import numpy as np
import tensorflow
from bdpy.ml import add_bias
from bdpy.preproc import select_top
from bdpy.stats import corrcoef
from matplotlib import pyplot as plt
from tensorflow.keras.layers import Conv2D, MaxPooling2D
from tensorflow.keras.layers import LeakyReLU
from tensorflow.keras.models import Sequential
from tensorflow.keras.optimizers import Adam


def main():
    subjects = {'s1': os.path.abspath('bxz056/data/Subject1.h5'),
                's2': os.path.abspath('bxz056/data/Subject2.h5'),
                's3': os.path.abspath('bxz056/data/Subject3.h5'),
                's4': os.path.abspath('bxz056/data/Subject4.h5'),
                's5': os.path.abspath('bxz056/data/Subject5.h5'),
                'imageFeature': os.path.abspath('bxz056/data/ImageFeatures.h5')}

    regine_of_interest = {'VC': 'ROI_VC = 1',
                          'LVC': 'ROI_LVC = 1',
                          'HVC': 'ROI_HVC = 1',
                          'V1': 'ROI_V1 = 1',
                          'V2': 'ROI_V2 = 1',
                          'V3': 'ROI_V3 = 1',
                          'V4': 'ROI_V4 = 1',
                          'LOC': 'ROI_LOC = 1',
                          'FFA': 'ROI_FFA = 1',
                          'PPA': 'ROI_PPA = 1'}

    voxel = {'VC': 1000,
             'LVC': 1000,
             'HVC': 1000,
             'V1': 500,
             'V2': 500,
             'V3': 500,
             'V4': 500,
             'LOC': 500,
             'FFA': 500,
             'PPA': 500}

    layers = ['cnn1', 'cnn2', 'cnn3', 'cnn4', 'cnn5', 'cnn6', 'cnn7', 'cnn8',
              'hmax1', 'hmax2', 'hmax3',
              'gist', 'sift']

    print('=======================================')
    print('Data loading...')

    dataset = {}
    image_feature = {}

    for person in subjects:

        file = h5py.File(subjects[person], 'r')

        if person != 'imageFeature':
            # Subject 1 ~ 5

            print(person, '---------------------')
            print('data: ', file.keys())

            dataset[person] = bdpy.BData(subjects[person])

        else:
            image_feature = bdpy.BData(subjects[person])

    # dataset & metadata collected

    print('\n=======================================')
    print('Analyzing...\n')

    data_prepare(dataset, regine_of_interest, image_feature, layers, voxel)


def data_prepare(subject, rois, img_feature, layers, voxel):
    print('Start learning:')
    print('-----------------')

    for sbj, roi, layer in product(subject, rois, layers):
        print('--------------------')
        print('Subject:    %s' % sbj)
        print('ROI:        %s' % roi)
        print('Num voxels: %d' % voxel[roi])
        print('Layers:    %s' % layer)

        # ---------------------------------------------

        # Subject {'s1': [...],
        #          's2': [...],
        #               ...
        #          's5': [...]}

        data = subject[sbj]  # data = 's1': [...]
        # ---------------------------------------------

        # rois: {'VC': 'ROI_VC = 1',
        #        'LVC': 'ROI_LVC = 1',
        #           ...
        #        'PPA': 'ROI_PPA = 1'}

        x = data.select(rois[roi])  # x = 'ROI_VC = 1' if roi = 'VC
        # --------------------------------------------

        # get data type in subject fMRI
        data_type = data.select('DataType')  # Mark the training data, seen data and imagine data
        labels = data.select('stimulus_id')  # Use Stimulus ID as the order to sort images

        y = img_feature.select(layer)  # select the image feature which be marked layers[layer]
        y_label = img_feature.select('ImageID')  # get image id

        # sort through the y in y_label of labels, correspond with brain data
        y_sort = bdpy.get_refdata(y, y_label, labels)  # labels -> y_label -> y

        # Flatten(): transfer the shape from vertical to horizontal
        i_train = (data_type == 1).flatten()  # mark of training data
        i_test_seen = (data_type == 2).flatten()  # Index for subject see an image
        i_test_img = (data_type == 3).flatten()  # Index for subject imagine an image

        # test data, overlap seen and imagined value
        i_test = i_test_img + i_test_seen

        # get training & test data in x
        x_train = x[i_train, :]
        x_test = x[i_test, :]

        # get training & test data in y
        y_train = y_sort[i_train, :]
        y_test = y_sort[i_test, :]

        print('Predicting...')

        predict_y, real_y = algorithm_predict_feature(x_train=x_train, y_train=y_train,
                                                      x_test=x_test, y_test=y_test,
                                                      num_voxel=voxel[roi])

        print('Predicted:    %s' % predict_y)
        print('Real:         %s' % real_y)


def algorithm_predict_feature(x_train, y_train, x_test, y_test, num_voxel):
    print('--------------------- Start predicting')

    n_unit = y_train.shape[1]

    # Normalize brian data (x)
    norm_mean_x = np.mean(x_train, axis=0)
    norm_scale_x = np.std(x_train, axis=0, ddof=1)

    x_train = (x_train - norm_mean_x) / norm_scale_x
    x_test = (x_test - norm_mean_x) / norm_scale_x

    y_true_list = []
    y_predict_list = []

    print('Loop start...')

    for i in range(n_unit):
        # Get unit
        y_train_unit = y_train[:, i]
        y_test_unit = y_test[:, i]

        # Normalize image features for training (y_train_unit)
        norm_mean_y = np.mean(y_train_unit, axis=0)
        std_y = np.std(y_train_unit, axis=0, ddof=1)
        norm_scale_y = 1 if std_y == 0 else std_y

        y_train_unit = (y_train_unit - norm_mean_y) / norm_scale_y

        # select the voxel in column
        correlation = corrcoef(y_train_unit, x_train, var='col')

        x_train_unit, voxel_index = select_top(x_train, np.abs(correlation), num_voxel, axis=1, verbose=False)
        x_test_unit = x_test[:, voxel_index]

        # Add bias terms
        x_train_unit = add_bias(x_train_unit, axis=1)
        x_test_unit = add_bias(x_test_unit, axis=1)

        print('x_train: ', x_train_unit.shape)
        print('x_test: ', x_test_unit.shape)
        print('y_train: ', y_train_unit.shape)
        print('y_test: ', y_test_unit.shape)

        # define the neural network architecture (convolutional net)
        model = Sequential()

        model.add(
            Conv2D(filters=10,
                   kernel_size=(3, 3),
                   activation='linear',
                   input_shape=(1200, 1001, 0, 0),
                   padding='same'))

        model.add(LeakyReLU(alpha=0.1))
        model.add(MaxPooling2D((4, 4), padding='same'))

        optimizer = Adam(learning_rate=0.0001)
        loss = tensorflow.keras.losses.categorical_crossentropy

        model.compile(optimizer, loss)

        # Training and test
        model.fit(x_train_unit, y_train_unit)  # Training
        model.summary()
        y_pred = model.predict(x_test_unit)  # Test

        # Denormalize predicted features
        y_pred = y_pred * norm_scale_y + norm_mean_y

        y_true_list.append(y_test_unit)
        y_predict_list.append(y_pred)

        print('Loop %03d   Loss:    %s' % ((i + 1), loss))

    # Create numpy arrays for return values
    y_predicted = np.vstack(y_predict_list).T
    y_true = np.vstack(y_true_list).T

    return y_predicted, y_true


# =========================================================================

# run Project
# ========================
main()
