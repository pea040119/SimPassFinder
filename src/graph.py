import os
import dgl
import json
import jellyfish
import torch
from torch.nn.utils.rnn import pad_sequence
from sklearn.model_selection import train_test_split
from sklearn.feature_selection import mutual_info_classif

from .utils import *



class CustomDataset():
    def __init__(self, args, device, logger):
        self.dataset_path = args.dataset_path
        self.edge_thv = args.edge_thv
        self.splitting_type = args.setting
        self.valid = args.valid
        self.test = args.test
        self.gnn_depth = args.gnn_depth
        self.device = device
        self.random_seed = args.random_seed
        self.batch_size = args.batch_size
        self.edge_type = args.edge_type
        self.logger = logger
        self.load_category()
        self.load_country()
        self.load_node()
        # self.encoding_node()
        
        
    def load_meta_data(self):
        self.logger.print(f"[*] Loading meta data")
        with open(os.path.join(self.dataset_path, "meta_data","meta_data.json"), "r") as f:
            self.meta_data = json.load(f)
        self.logger.print(f"[+] Done loading meta data")
        self.logger.print(f"[+] Number of sites: {len(self.meta_data)}\n")
    
    
    def load_edge(self):
        self.logger.print(f"[*] Loading edges")
        if self.edge_type == "reuse":
            edge_file = os.path.join(self.dataset_path, "graph", "edges_reuse.json")
        elif self.edge_type == "sim":
            edge_file = os.path.join(self.dataset_path, "graph", "edges.json")
        else:
            raise ValueError(f"Unknown edge type: {self.edge_type}. Use 'sim' or 'reuse'.")
        with open(edge_file, "r") as f:
            self.edges = json.load(f)
        self.logger.print(f"[+] Done loading edges")
        self.logger.print(f"[+] Number of edges: {len(self.edges)}\n")


    def load_node(self):
        self.logger.print(f"[*] Loading nodes")
        with open(os.path.join(self.dataset_path, "graph", f"nodes.json"), "r") as f:
            self.nodes = json.load(f)
        self.logger.print(f"[+] Done loading nodes")
        self.logger.print(f"[+] Number of nodes: {len(self.nodes)}\n")
        
    
    def load_country(self):
        self.logger.print(f"[*] Loading countries")
        with open(os.path.join(self.dataset_path, "graph", "countries.json"), "r") as f:
            self.countries = json.load(f)
        self.logger.print(f"[+] Done loading countries")
        self.logger.print(f"[+] Number of countries: {len(self.countries)}\n")
            
    
    def load_category(self):
        self.logger.print(f"[*] Loading categories")
        with open(os.path.join(self.dataset_path, "graph", "categories.json"), "r") as f:
            self.categories = json.load(f)
        self.logger.print(f"[+] Done loading categories")
        self.logger.print(f"[+] Number of categories: {len(self.categories)}\n")
    
    
    def set_node(self, save=True):
        self.nodes = []
        self.logger.print(f"[*] Start Setting nodes")
        
        for site in tqdm(list(self.meta_data.keys()), desc="[*] Setting nodes"):
            node = {}
            node["site"] = site
            node["category"] = self.meta_data[site]["category"]
            node["country"] = self.meta_data[site]["country"]
            node["security_level"] = self.meta_data[site]["security_level"]
            node["ip"] = self.meta_data[site]["ip"]
            self.nodes.append(node)
        self.logger.print(f"[+] Done setting nodes")
        self.logger.print(f"[+] Number of nodes: {len(self.nodes)}")
        
        if save:
            node_file = os.path.join(self.dataset_path, "graph", f"nodes.json")
            with open(node_file, "w", encoding="utf-8") as f:
                json.dump(self.nodes, f, indent=4, ensure_ascii=False)
            self.logger.print(f"[+] Saved nodes to {node_file}")
        
        
    def set_edge(self, save=True):
        self.edges = []
        self.logger.print(f"[*] Start Setting edges")
        
        for i in tqdm(range(len(self.nodes)), desc="[*] Setting edges"):
            for j in range(i + 1, len(self.nodes)):
                i_site = self.nodes[i]["site"]
                j_site = self.nodes[j]["site"]
                with open(os.path.join(self.dataset_path, "sites", f"{i_site}.json")) as f:
                    i_data = json.load(f)
                with open(os.path.join(self.dataset_path, "sites", f"{j_site}.json")) as f:
                    j_data = json.load(f)
                i_data_user_id = set(i_data.keys())
                j_data_user_id = set(j_data.keys())
                intersection = i_data_user_id & j_data_user_id
                if len(intersection) == 0:
                    continue
                pwd_sim = []
                for user_id in intersection:
                    pwd_sim.append(jellyfish.jaro_similarity(i_data[user_id], j_data[user_id]))
                weight = sum(pwd_sim) / len(pwd_sim)
    
                edge = {}
                edge["node_1"] = i
                edge["node_2"] = j
                edge["weight"] = weight
                self.edges.append(edge)
        
        if save:
            edge_file = os.path.join(self.dataset_path, "graph", f"edges.json")
            with open(edge_file, "w", encoding="utf-8") as f:
                json.dump(self.edges, f, indent=4, ensure_ascii=False)
            self.logger.print(f"[+] Saved edges to {edge_file}\n")
            
            
    def set_edge_reuse(self, save=True):
        self.edges = []
        self.logger.print(f"[*] Start Setting edges")
        
        for i in range(len(self.nodes)):
            self.logger.print(f"[*] Setting edges: {i:5} / {len(self.nodes):5}")
            for j in range(i + 1, len(self.nodes)):
                i_site = self.nodes[i]["site"]
                j_site = self.nodes[j]["site"]
                with open(os.path.join(self.dataset_path, "sites", f"{i_site}.json")) as f:
                    i_data = json.load(f)
                with open(os.path.join(self.dataset_path, "sites", f"{j_site}.json")) as f:
                    j_data = json.load(f)
                i_data_user_id = set(i_data.keys())
                j_data_user_id = set(j_data.keys())
                intersection = i_data_user_id & j_data_user_id
                if len(intersection) == 0:
                    continue
                check = False
                for user_id in intersection:
                    if i_data[user_id] == j_data[user_id]:
                        check = True
                        break
                if not check:
                    continue
                edge = {}
                edge["node_1"] = i
                edge["node_2"] = j
                edge["weight"] = 1
                self.edges.append(edge)
                
        if save:
            edge_file = os.path.join(self.dataset_path, "graph", f"edges_reuse.json")
            with open(edge_file, "w", encoding="utf-8") as f:
                json.dump(self.edges, f, indent=4, ensure_ascii=False)
            self.logger.print(f"[+] Saved edges to {edge_file}\n")
            
            
    def __encoding_node(self, node):
        encode_node = {}
        encode_node["site"] = [ord(c) for c in node["site"]]
        encode_node["category"] = self.categories.index(node["category"])
        encode_node["country"] = self.countries.index(node["country"])
        encode_node["security_level"] = node["security_level"]
        bit_strs = [f"{int(octet):08b}" for octet in node["ip"].split(".")]
        encode_node["ip"] = [float(bit)
                            for byte in bit_strs
                            for bit in byte]

        return encode_node
    
    
    def encoding_node(self):
        self.logger.print(f"[*] Start encoding node")
        for node in self.nodes:
            encode_node = self.__encoding_node(node)
            node["site"] = encode_node["site"]
            node["category"] = encode_node["category"]
            node["country"] = encode_node["country"]
            node["security_level"] = encode_node["security_level"]
            node["ip"] = encode_node["ip"]
        self.logger.print(f"[+] Done encoding nodes\n")
    
    def build_graph(self):
        self.logger.print(f"[*] Start building graph")
        
        node_1_list = [edge["node_1"] for edge in self.edges]
        node_2_list = [edge["node_2"] for edge in self.edges]
        label_list = [1 if edge["weight"] > self.edge_thv else 0 for edge in self.edges]
        
        data_dict = {
            ("site", "user", "site"): (node_1_list, node_2_list),
            ("site", "sim", "site"): (node_1_list, node_2_list),
        }
        self.graph = dgl.to_bidirected(dgl.heterograph(data_dict))
        
        site_list = [torch.tensor(node["site"], dtype=torch.long) for node in self.nodes]
        padded_site = pad_sequence(site_list, batch_first=True, padding_value=0)
        mask = padded_site.ne(0)
        
        self.graph.ndata["site"] = padded_site
        self.graph.ndata["site_mask"] = mask
        self.graph.ndata["category"] = torch.tensor([node["category"] for node in self.nodes])
        self.graph.ndata["country"] = torch.tensor([node["country"] for node in self.nodes])
        self.graph.ndata["security_level"] = torch.tensor([node["security_level"] for node in self.nodes])
        self.graph.ndata["ip"] = torch.tensor([node["ip"] for node in self.nodes])
        
        sim_etype = ("site", "sim", "site")
        num_sim_edges = self.graph.num_edges(etype=sim_etype)

        self.graph.edata["label"]  = {sim_etype: torch.zeros(num_sim_edges, dtype=torch.float)}

        eid_fwd = self.graph.edge_ids(node_1_list, node_2_list, etype=sim_etype)
        eid_rev = self.graph.edge_ids(node_2_list, node_1_list, etype=sim_etype)

        self.graph.edata["label"][sim_etype][eid_fwd] = torch.tensor(label_list, dtype=torch.float)
        self.graph.edata["label"][sim_etype][eid_rev] = torch.tensor(label_list, dtype=torch.float)
        
        self.logger.print(f"[+] Done building graph\n")
        
        
    def print_graph(self, print_type="all"):
        self.logger.print(f"[+] Graph information")
        if print_type == "all":
            self.logger.print(f"[+] Nodes: {self.graph.num_nodes()}")
            self.logger.print(f"[+] Edges: {self.graph.num_edges()}")
        elif print_type == "split": 
            if self.splitting_type == "inductive":
                self.logger.print(f"[+] Graph type: Inductive")
                self.logger.print(f"[+] Train| nodes: {self.graph_split['train'].num_nodes()}, edges: {self.graph_split['train'].num_edges()}")
                self.logger.print(f"[+] Valid| nodes: {self.graph_split['valid'].num_nodes()}, edges: {self.graph_split['valid'].num_edges()}")
                self.logger.print(f"[+] Test | nodes: {self.graph_split['test'].num_nodes()}, edges: {self.graph_split['test'].num_edges()}")
            else:
                self.logger.print(f"[+] Graph type: Transductive")
                self.logger.print(f"[+] All nodes: {self.graph.num_nodes()}")
                self.logger.print(f"[+] Train| edges: {len(self.edge_split['train'])}")
                self.logger.print(f"[+] Valid| edges: {len(self.edge_split['valid'])}")
                self.logger.print(f"[+] Test | edges: {len(self.edge_split['test'])}")
        self.logger.print("")
    
    
    def inductive_split(self):
        valid_portion, test_portion = self.valid, self.test

        p1 = valid_portion + test_portion
        p2 = test_portion / (valid_portion + test_portion)

        train_node, valid_node = train_test_split(self.graph.nodes(), test_size=p1, shuffle=True, random_state=self.random_seed)
        valid_node, test_node = train_test_split(valid_node, test_size=p2, shuffle=True, random_state=self.random_seed)

        train_g = self.graph.subgraph(train_node)
        valid_g = self.graph.subgraph(torch.cat([train_node, valid_node], 0))
        test_g = self.graph.subgraph(torch.cat([train_node, test_node], 0))

        return {'train': train_g, 'valid': valid_g, 'test': test_g}, {'train': train_node, 'valid': valid_node, 'test': test_node}


    def transductive_split(self):
        valid_portion, test_portion = self.valid, self.test

        p1 = valid_portion + test_portion
        p2 = test_portion / (valid_portion + test_portion)

        train_edge, valid_edge = train_test_split(self.graph.edges(etype='sim', form='eid'), test_size=p1, shuffle=True, random_state=self.random_seed)
        valid_edge, test_edge = train_test_split(valid_edge, test_size=p2, shuffle=True, random_state=self.random_seed)
        
        return {'train': train_edge, 'valid': valid_edge, 'test': test_edge}
    
    
    def split(self):
        self.logger.print(f"[*] Start splitting graph")
        self.logger.print(f"[*] Splitting type: {self.splitting_type}")
        if self.splitting_type == "inductive":
            self.graph_split, self.node_split = self.inductive_split()
        else:
            self.edge_split = self.transductive_split()
        self.logger.print(f"[+] Done splitting graph\n")
        
        self.print_graph(print_type="split")
        
        
    def get_dataset_loader(self, data_type):
        self.logger.print(f"[*] Start getting dataset loader for {data_type}")
        if self.splitting_type == "inductive":
            graph = self.graph_split[data_type]
        else:
            graph = self.graph
        
        reverse_eid = self.get_reverse_eid(data_type)
        target_eid = self.get_target_eid(data_type)
        
        sampler = dgl.dataloading.as_edge_prediction_sampler(dgl.dataloading.MultiLayerFullNeighborSampler(self.gnn_depth), exclude='reverse_id', reverse_eids=reverse_eid)
        
        data_loader = dgl.dataloading.DataLoader(
                graph,
                {'sim': target_eid},
                sampler,
                batch_size=self.batch_size,
                device=self.device,
                shuffle=False,
                drop_last=False,
                num_workers=0)

        return data_loader
    
    
    def get_reverse_eid(self, data_type):
        if self.splitting_type == 'transductive':
            graph = self.graph
        else:
            graph = self.graph_split[data_type]
        return {('site', 'sim', 'site'): graph.edge_ids(graph.edges(etype='sim')[1], graph.edges(etype='sim')[0], etype='sim')}
    
    
    def get_target_eid(self, data_type):
        if self.splitting_type == 'transductive':
            return self.edge_split[data_type]
        else:
            graph = self.graph_split[data_type]
            node = self.node_split[data_type]

            ori_id_to_id = dict(zip(graph.ndata['_ID'].tolist(), graph.nodes().tolist()))
            node_sub = [ori_id_to_id[n.item()] for n in node]

            return torch.unique(torch.cat([graph.in_edges(node_sub, etype='sim', form='eid'), graph.out_edges(node_sub, etype='sim', form='eid')]))
        
        
    def pop_node_feature(self, data_type):
        if self.splitting_type == 'transductive':
            graph = self.graph
        else:
            graph = self.graph_split[data_type]
            
        nfeat_s = graph.ndata.pop('site')
        nfeat_sm = graph.ndata.pop('site_mask')
        nfeat_c = graph.ndata.pop('category')
        nfeat_co = graph.ndata.pop('country')
        nfeat_sl = graph.ndata.pop('security_level')
        nfeat_ip = graph.ndata.pop('ip')
        
        return nfeat_s, nfeat_sm, nfeat_c, nfeat_co, nfeat_sl, nfeat_ip
    
    
    def compute_node_edge_correlations(self):
        self.logger.print(f"[*] Start computing node-edge correlations")
        edge_features = self.graph.edata['label'][('site', 'sim', 'site')]
        
        for feat_name in ['category', 'country', 'security_level']:
            node_feat = self.graph.ndata[feat_name]
            src, dst = self.graph.edges(etype='sim',order='eid')
            x = torch.stack([node_feat[src], node_feat[dst]], dim=1)
            
            mi = mutual_info_classif(x, edge_features, discrete_features=[True, True], random_state=0)

            self.logger.print(f"[+] MI({feat_name} → edge) = {mi[0]:.4f}")