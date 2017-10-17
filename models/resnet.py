'''
Functional definition for resnet inspired by
https://github.com/szagoruyko/functional-zoo

Unlike the original code, we're going to access the variables in the model in
the orthodox tensorflow way with variable_scopes. It wouldn't be hard to write
an iterator that accesses variables defined in the same scope and modifies
them, so we could load from pytorch the same way illustrated in the zoo.
'''

import tensorflow as tf

def convert_params(params):
    '''Convert the channel order of parameters between PyTorch and
    Tensorflow.'''
    def tr(v):
        if v.ndim == 4:
            return v.transpose(2,3,1,0)
        elif v.ndim == 2:
            return v.transpose()
        return v
    params = {k: tr(v) for k, v in params.iteritems()}
    return params

def conv2d(x, phase, n_filters, kernel_size, strides=[1,1,1,1],
        activation_fn=tf.nn.relu,
        initializer=tf.contrib.layers.xavier_initializer_conv2d,
        padding='SAME', scope=None, bias=True):
    with tf.variable_scope(scope):
        n_input_channels = int(x.shape[3])
        # define parameters
        conv_param_shape = kernel_size+[n_input_channels, n_filters]
        w = tf.get_variable("w", conv_param_shape,
                initializer=initializer())
        if bias:
            b = tf.get_variable("b", [n_filters],
                    initializer=tf.constant_initializer())

        activations = tf.nn.conv2d(x, w, strides=strides, padding=padding)
        if bias:
            return activation_fn(activations + b)
        else:
            return activation_fn(activations)


def resnet50(inputs, phase, conv2d=conv2d):
    '''Using bottleneck that matches those used in the PyTorch model
    definition: https://github.com/kuangliu/pytorch-cifar/blob/master/models/resnet.py#L41-L66
    '''
    expansion = 4
    def group(input, base, in_planes, planes, num_blocks, stride):
        strides = [stride]+[1]*(num_blocks-1)
        o = input
        for i,stride in enumerate(strides):
            b_base = ('%s.block%d.conv') % (base, i)
            x = o
            o = bottleneck(x, b_base, in_planes, planes, stride)
            in_planes = planes*expansion
        return o

    def bottleneck(input, base, in_planes, planes, stride=1):
        o = conv2d(input, phase, planes, [1,1], scope=base+'0',
                activation_fn=lambda x: x, bias=False)
        o = tf.nn.relu(batch_norm(o, is_training=phase, scope=base+'0'))
        o = conv2d(o, phase, planes, [3,3], activation_fn=lambda x: x,
                scope=base+'1', strides=[1,stride,stride,1], padding='SAME',
                bias=False)
        o = tf.nn.relu(batch_norm(o, is_training=phase, scope=base+'1'))
        o = conv2d(o, phase, planes*expansion, [1,1], activation_fn=lambda x:
                x, scope=base+'2', bias=False)
        o = batch_norm(o, is_training=phase, scope=base+'1')

        if stride != 1 or in_planes != expansion*planes:
            # shortcut 
            s = conv2d(input, phase, expansion*planes, [1,1],
                    strides=[1,stride,stride,1], activation_fn=lambda x:x,
                    bias=False, scope=base+'short')
            s = batch_norm(s, is_training=phase, scope=base+'short')
            o = o+s
        else:
            o = o+input

        return tf.nn.relu(o)

    # determine network size by parameters
    blocks = [sum([re.match('group%d.block\d+.conv0.weight'%j, k) is not None
                   for k in params.keys()]) for j in range(4)]

    assert False # does not match resnet50
    o = conv2d(inputs, scope='conv0', strides=[1,2,2,1], padding='SAME')
    o = tf.nn.relu(o)
    o = tf.pad(o, [[0,0], [1,1], [1,1], [0,0]])
    o = tf.nn.max_pool(o, ksize=[1,3,3,1], strides=[1,2,2,1], padding='VALID')
    o_g0 = group(o, params, 'group0', 1, blocks[0])
    o_g1 = group(o_g0, params, 'group1', 2, blocks[1])
    o_g2 = group(o_g1, params, 'group2', 2, blocks[2])
    o_g3 = group(o_g2, params, 'group3', 2, blocks[3])
    o = tf.nn.avg_pool(o_g3, ksize=[1,7,7,1], strides=[1,1,1,1], padding='VALID')
    o = tf.reshape(o, [-1,512])
    o = tf.matmul(o, params['fc.weight']) + params['fc.bias']
    return o
