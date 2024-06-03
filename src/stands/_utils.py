import dgl
import random
import warnings
import numpy as np
import torch
import torch.autograd as autograd
from torch.autograd import Variable
from typing import Union


def seed_everything(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True
    dgl.random.seed(seed)


def clear_warnings(func, category=FutureWarning):
    def warp(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=category)
            temp = func(*args, **kwargs)
            return temp
    return warp


def interpolate(real_data, fake_data, cuda):
    shapes = [1 if i != 0 else real_data.size(i) for i in range(real_data.dim())]
    eta = torch.FloatTensor(*shapes).uniform_(0, 1)
    if cuda:
        eta = eta.cuda()
    else:
        eta = eta

    interpolated = eta * real_data + ((1 - eta) * fake_data)

    if cuda:
        interpolated = interpolated.cuda()
    else:
        interpolated = interpolated

    # define it to calculate gradient
    interpolated = Variable(interpolated, requires_grad=True)

    return interpolated


def calculate_gradient_penalty(D, real_g, fake_g, real_p=None, fake_p=None, Zforward=False):
    '''Calculate gradient penalty for training discriminator'''
    cuda = True if torch.cuda.is_available() else False

    inter_g = interpolate(real_g, fake_g, cuda)
    if real_p is None or fake_p is None:
        inputs = (inter_g) 
        # calculate probability of interpolated examples
        if Zforward:
            prob_interpolated = D.Zforward(inter_g)
        else:
            prob_interpolated = D.SCforward(inter_g)            
    else:
        inter_p = interpolate(real_p, fake_p, cuda)
        inputs = (inter_g, inter_p)
        # calculate probability of interpolated examples
        if Zforward:
            prob_interpolated = D.Zforward(inter_g)
        else:
            prob_interpolated = D.Fullforward(inter_g, inter_p)

    # calculate gradients of probabilities with respect to examples
    gradients = autograd.grad(outputs=prob_interpolated, inputs=inputs,
                              grad_outputs=torch.ones(prob_interpolated.size()).cuda()
                              if cuda else torch.ones(prob_interpolated.size()),
                              create_graph=True, retain_graph=True)[0]

    grad_penalty = ((gradients.norm(2, dim=1) - 1) ** 2).mean()
    return grad_penalty


def select_device(GPU: Union[bool, str] = True,):
    if GPU:
        if torch.cuda.is_available():
            if isinstance(GPU, str):
                device = torch.device(GPU)
            else:
                device = torch.device('cuda:0')
        else:
            print("GPU isn't available, and use CPU to train Docs.")
            device = torch.device("cpu")
    else:
        device = torch.device("cpu")

    return device