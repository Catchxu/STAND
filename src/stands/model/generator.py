import os
import copy
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional

from .backbone import Extractor, ExtractorOnlyST, ExtractorOnlySC
from .backbone import MemoryBlock, StyleBlock
from ..configs import SCConfigs, STConfigs, FullConfigs, MBConfigs


class GeneratorAD(nn.Module):
    def __init__(self, gene_dim, patch_size=None, only_ST=False, only_SC=False):
        super().__init__()
        assert (only_ST and only_SC) == False

        if only_ST:
            configs = STConfigs(gene_dim)
            self.extract = ExtractorOnlyST(configs)

        elif only_SC:
            configs = SCConfigs(gene_dim)
            self.extract = ExtractorOnlySC(configs)
        
        else:
            configs = FullConfigs(gene_dim, patch_size)
            self.extract = Extractor(configs)
        
        self.Memory = MemoryBlock(**MBConfigs(configs.z_dim).MBBlock)
        self.z_dim = configs.z_dim

    def Fullforward(self, g_block, feat_g, feat_p):
        z_g, z_p = self.extract.encode(g_block, feat_g, feat_p)
        z_g, z_p = self.extract.fusion(z_g, z_p)
        z = torch.concat([z_g, z_p], dim=-1)
        mem_z = z# self.Memory(z)
        z_g, z_p = torch.chunk(mem_z, 2, dim = -1)
        feat_g, feat_p = self.extract.decode(z_g, z_p)
        return z, feat_g, feat_p

    def STforward(self, g_block, feat_g):
        z = self.extract.encode(g_block, feat_g)
        mem_z = self.Memory(z)
        feat_g = self.extract.decode(mem_z)
        return z, feat_g

    def SCforward(self, feat_g):
        z = self.extract.encode(feat_g)
        mem_z = self.Memory(z)
        feat_g = self.extract.decode(mem_z)
        return z, feat_g
    
    def load_weight(self, weight_dir: Optional[str]):
        if weight_dir:
            pre_weights = torch.load(weight_dir)
        else:
            pre_weights = torch.load(os.path.dirname(__file__) + '/generator.pth')
        
        # load the pre-trained weights for extractor
        model_dict = self.state_dict()
        pretrained_dict = {k: v for k, v in pre_weights.items()}
        model_dict.update(pretrained_dict)
        self.load_state_dict(model_dict)




class KinPair(nn.Module):
    def __init__(self, n_ref, n_tgt):
        super().__init__()
        self.mapping = nn.Parameter(torch.Tensor(n_tgt, n_ref))
        self.reset_parameters()

    def reset_parameters(self):
        stdv = 1. / math.sqrt(self.mapping.size(1))
        self.mapping.data.uniform_(-stdv, stdv)

    def forward(self, z_ref, z_tgt):
        # reconstruct z_tgt with z_ref
        fake_z_tgt = torch.mm(F.relu(self.mapping), z_ref)
        return fake_z_tgt, z_tgt, F.relu(self.mapping).detach().cpu().numpy()




class GeneratorBC(nn.Module):
    def __init__(self, extractor, n_batch, z_dim):
        super().__init__()
        self.extractor = extractor
        self.Style = StyleBlock(n_batch, z_dim)

    def STforward(self, g_block, feat_g, batchid):
        z = self.extractor.GeneEncoder(g_block, feat_g)
        z = self.Style(z, batchid)
        feat_g = self.extractor.GeneDecoder(z)
        return feat_g

    def SCforward(self, feat_g, batchid):
        z = self.extractor.GeneEncoder(feat_g)
        z = self.Style(z, batchid)
        feat_g = self.extractor.GeneDecoder(z)
        return feat_g
