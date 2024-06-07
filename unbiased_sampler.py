import torch
import dgl
import numpy as np
from utils import cos_sim
import torch
from utils import sampler_fixed_build_env, process_data, cos_sim
from model import Model


node_embeddings = None


def cos_sim_2nd_sampler(author_idx_tensor, paper_idx_tensor, sample_num):
    _author_idx = author_idx_tensor.cpu()
    _paper_idx = paper_idx_tensor.cpu()
    res = cos_sim(np.array(node_embeddings['author'][_author_idx]), 
                  np.array(node_embeddings['paper'][_paper_idx]))
    _prob = np.ones(res.shape)

    # 几乎调成为 0.
    _prob[res > 0.55] = 0.01
    _prob = _prob / _prob.sum()
    _sample_idx = np.random.choice(np.arange(len(res)), size=sample_num, replace=False, p=_prob)
    return _sample_idx
     

    

def load_model_get_node_embeddings(args):
    device = torch.device('cuda:0')
    _path = args.unbiased_sampler_guide_model_path
    # model = torch.load('unbiased_sampler/node_embedding/512/2024-06-07 14:04:44_0.9417910995340646_model.pth', 
                    #    map_location=device)
    model = torch.load(_path, map_location=device)
    print('success to load the model')
    train_refs, test_refs, refs_to_pred, cite_edges, coauthor_edges, paper_feature = process_data(args)
    hetero_graph, rel_list = sampler_fixed_build_env(args, train_refs, cite_edges, coauthor_edges, paper_feature, device)
    model.eval()
    with torch.no_grad():
        blocks = [dgl.to_block(hetero_graph) for _ in range(4)]
        node_embeddings = model.rgcn(blocks, hetero_graph.ndata['features'])
    return node_embeddings


def load_model_get_sampler(args):
    device = torch.device('cuda:0')

    class NewSamplerModelArgs:
        """
        The args for the original model used for sampler
        """
        def __init__(self) -> None:

            self.data_path = "./data/"
            self.save_path = './save/'
            self.load_path = None
            self.predict_path = './predictions'
            self.save_log_path = './logs/'
            self.save_embed_path = './embedding'
            self.load_embed_path = None

            self.input_dim = 512
            self.hidden_dim = 256
            self.output_dim = 64
            self.batch_size = 10000
            self.num_epochs = 100
            self.lr = 0.001
            self.lr_end = 0.0001
            self.lr_decay = 0.5
            self.lr_period = 20
            self.weight_decay = 0.00004
            self.k = 4
            self.heads = [16, 8, 8, 4]

            self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
            self.seed = -1
            self.log_interval = 100

            self.unbiased_sampler = False
            self.save_node_embeddings = False
    
    tmpNewSamplerModelArgs = NewSamplerModelArgs()
    rel_list = [('author', 'ref', 'paper'), ('paper', 'cite', 'paper'), ('author', 'coauthor', 'author'), ('paper', 'beref', 'author')]
    model = Model(tmpNewSamplerModelArgs.input_dim,
                    tmpNewSamplerModelArgs.hidden_dim,
                    tmpNewSamplerModelArgs.output_dim,
                    rel_list,
                    tmpNewSamplerModelArgs).to(device)
    

    model_state_dict = torch.load('unbiased_sampler/node_embedding/512/2024-06-07 14:04:44_0.9417910995340646_model.pth', 
                       map_location=device)
    model.load_state_dict(model_state_dict)

    print('This is the type of the model:', type(model))
    print('success to load the model')
    train_refs, test_refs, refs_to_pred, cite_edges, coauthor_edges, paper_feature = process_data(args)
    hetero_graph, rel_list = sampler_fixed_build_env(tmpNewSamplerModelArgs, train_refs, cite_edges, coauthor_edges, paper_feature)
    model.eval()
    global node_embeddings
    with torch.no_grad():
        blocks = [dgl.to_block(hetero_graph) for _ in range(4)]
        node_embeddings = model.rgcn(blocks, hetero_graph.ndata['features'])
    node_embeddings = {k: v.to('cpu') for k, v in node_embeddings.items()}
    
    class NewSampler(dgl.dataloading.negative_sampler._BaseNegativeSampler):
        def __init__(self, k, exclude_self_loops=True, replace=False):
            self.k = k
            self.exclude_self_loops = exclude_self_loops
            self.replace = replace

        def _generate(self, g, eids, canonical_etype):
            if canonical_etype == ('author', 'ref', 'paper') or canonical_etype == ('paper', 'beref', 'author'):
                _first_sample_res =  g.global_uniform_negative_sampling(
                    2 * len(eids) * self.k,
                    self.exclude_self_loops,
                    self.replace,
                    canonical_etype,
                )
                if canonical_etype == ('author', 'ref', 'paper'):
                    _sample_idx = cos_sim_2nd_sampler(_first_sample_res[0], _first_sample_res[1], len(eids) * self.k)
                elif canonical_etype == ('paper', 'beref', 'author'):
                    _sample_idx = cos_sim_2nd_sampler(_first_sample_res[1], _first_sample_res[0], len(eids) * self.k)
                return _first_sample_res[0][_sample_idx], _first_sample_res[1][_sample_idx]
            else:
                return g.global_uniform_negative_sampling(
                    len(eids) * self.k,
                    self.exclude_self_loops,
                    self.replace,
                    canonical_etype,
                )
    return NewSampler
