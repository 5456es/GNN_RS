import torch
import numpy as np
import random
import dgl
import argparse
import time
from utils import *
from train import train


def parse_arguments():
    parser = argparse.ArgumentParser("The main entry point for the GNN Academic Paper Link Prediction program")
    ### Data Loading and Saving
    parser.add_argument("--data_path", type=str,default="./data/", help="The path to the data folder")
    parser.add_argument("--save_path", type=str,default='./save/', help="The path to save the model")
    parser.add_argument("--load_path", type=str,default=None, help="The path to load the model")
    parser.add_argument('--predict_path', type=str, default='./predictions', help='The path to save the prediction')
    parser.add_argument("--save_log_path", type=str,default='./logs/', help="The path to save the log")
    parser.add_argument("--save_embed_path", type=str,default='./embedding', help="The path to save the embeddings")
    parser.add_argument("--load_embed_path", type=str,default='./embedding', help="The path to load the embeddings")


    ### Train Parameters
    parser.add_argument("--input_dim", type=int, default=512, help="The input dimension for the model")
    parser.add_argument("--hidden_dim", type=int, default=512, help="The hidden dimension for the model")
    parser.add_argument("--output_dim", type=int, default=64, help="The output dimension for the model")
    parser.add_argument("--batch_size", type=int, default=10000, help="The batch size for training")
    parser.add_argument("--num_epochs", type=int, default=100, help="The number of epochs to train for")
    parser.add_argument("--lr", type=float, default=0.0001, help="The learning rate for training")
    parser.add_argument("--lr_end", type=float, default=0.00001, help="The learning rate for training")
    parser.add_argument("--lr_decay", type=float, default=0.5, help="The learning rate decay for training")
    parser.add_argument('--lr_period', default=20, type=int, help='period for lr_scheduler')
    parser.add_argument("--weight_decay", type=float, default=0.00004, help="The weight decay for training")
    parser.add_argument("--k", type=int, default=4, help="The number of  samples to use")
    parser.add_argument("--heads", type=list, default=[16, 8, 8, 4], help="The number of heads for the GAT layers")
    parser.add_argument("--residual", type=bool, default=False, help="The residual connection for the GAT layers")

    ### Other Parameters
    parser.add_argument("--device", type=str, default="cuda:0" if torch.cuda.is_available() else "cpu", help="The device to run the model on, [cuda:x] or cpu")
    parser.add_argument("--seed", type=int, default=-1, help="The seed for the random number generator")
    parser.add_argument("--log_interval", type=int, default=100, help="The interval to log the training results")

    # unbiased_sampler
    parser.add_argument('--unbiased_sampler', default=False, type=bool, help='Use the unbiased sampler or not')
    parser.add_argument('--save_node_embeddings', default=False, type=bool, help='Save the node embeddings or not')
    parser.add_argument('--unbiased_sampler_guide_model_path', default=None, type=str, help='The path to the unbiased sampler guide model')
    return parser.parse_args()

def main(args):
    ### Set and Preprocess
    if args.seed!=-1:
        set_seed(args.seed)
    else:
        args.seed = random.randint(0, 1000000)
        set_seed(args.seed)

    train_refs, test_refs, refs_to_pred, cite_edges, coauthor_edges, paper_feature=process_data(args)
    hetero_graph, rel_list = build_env(args,train_refs, cite_edges, coauthor_edges, paper_feature)

    torch.cuda.empty_cache()
    time.sleep(5)
    
    best_embed, best_thresh, best_f1 = train(args, hetero_graph, test_refs, rel_list)
    gen_csv_prediction(args,best_embed, refs_to_pred, best_thresh, best_f1, args.seed)
    

if __name__ == "__main__":

    args = parse_arguments()
    print("Arguments: \n"+"-"*50)
    for arg in vars(args):
        print(f"{arg}: {getattr(args, arg)}")
    print("-" * 50)
    if args.residual and args.hidden_dim!=512:
        print("Warning: The residual connection is only available for hidden_dim=512")
        args.residual=False
    torch.cuda.empty_cache()
    
    main(args)
