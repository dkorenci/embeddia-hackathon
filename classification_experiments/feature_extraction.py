from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.pipeline import FeatureUnion

import numpy as np
from pathlib import Path
from project_settings import BERT_FOLDER
from classification_experiments.bert_features_predictions import predict_fn, features_finetuned_model

# Bert folders/ids
BERT_CRO_V0 = 'crosloengual-bert-42-toxicity-2e-5-256'
BERT_CRO_V1 = 'crosloengual-bert_42_toxicity_allENdata_2e-05_128'
BERT_EST_V1 = 'finest-bert_42_toxicity_allENdata_2e-05_128'
BERT_CRO_FINETUNE = 'crosloengual-bert_42_noblock_large_crotian_2e-05_128'

def tfidf_features(max_feats=None, bigrams=False):
    fextr = TfidfVectorizer(max_features=max_feats, sublinear_tf=True)
    if not bigrams: return fextr
    fextr_2g = TfidfVectorizer(max_features=25000, sublinear_tf=True, ngram_range=(2, 2))
    union = FeatureUnion([("words", fextr),
                          ("bigrams", fextr_2g)])
    return union

def wcount_features(max_feats=None, binary=True, bigrams=False):
    fextr = CountVectorizer(max_features=max_feats, binary=binary)
    if not bigrams: return fextr
    fextr_2g = CountVectorizer(max_features=max_feats, binary=binary, ngram_range=(2, 2))
    union = FeatureUnion([("words", fextr),
                          ("bigrams", fextr_2g)])
    return union

def bert_features(bert_folder, texts, features, max_len=128, torch_device='cpu'):
    '''
    :param bert_folder: folder within BERT_FOLDER (from project_settings.py)
    :param texts: list of texts
    :param features: 'predict' (class probabilities and labels), 'transformer' (transformer states)
    :return:
    '''
    data_dir = Path(BERT_FOLDER)
    model_folder = data_dir / bert_folder
    if features == 'transformer':
        feats = features_finetuned_model(texts, labels=None, fine_tuned_model=model_folder,
                                         max_len=max_len, torch_device=torch_device)
        feats = [f[0] for f in feats]
        #for f in feats: print(f.shape, f.dtype)
        res = np.array(feats)
        #print(res.shape)
        return res
    if features == 'predict':
        results = predict_fn(model_folder, texts=texts, max_len=max_len, torch_device=torch_device)
        probs = [r['probs'] for r in results]
        labels = [r['label'] for r in results]
        probs = np.array(probs)
        labels = np.array(labels)
        return probs, labels

def bert_feature_loader(dataset, split, bert, features, label='', max_len=128, torch_device='cpu'):
    '''
    Creates BERT features for a specific dataset and configuration and saves them.
     If saved features exist, return saved.
    :param dataset: 'cro' or 'est'
    :param split: 'train', 'dev', or 'test'
    :param label: additional label for designating a specific dataset+split
    :param bert: bert model id, ie folder within BERT_FOLDER
    :param features: 'transformer' or 'predict'
    :return: features
    '''
    from hackashop_datasets.cro_24sata import cro24_load_forclassif
    from hackashop_datasets.est_express import est_load_forclassif
    from pickle import dump, load
    from project_settings import FEAT_EXTRACT_CACHE
    #fname = f'bert_features_dset:{dataset}_split:{split}_label:{label}_features:{features}_bert:[{bert}]'
    #bert_features_dset_est_split_train_label__features_transformer_bert_[crosloengual-bert_42_toxicity_allENdata_2e-05_128]
    fname = f'bert_features_dset_{dataset}_split_{split}_label_{label}_features_{features}_bert_[{bert}]'
    file_path = Path(FEAT_EXTRACT_CACHE) / fname
    if (file_path.exists()):
        return load(open(file_path, 'rb'))
    else:
        if dataset == 'cro': texts, _ = cro24_load_forclassif(split)
        elif dataset == 'est': texts, _ = est_load_forclassif(split)
        result = bert_features(bert, texts, features=features,
                               max_len=max_len, torch_device=torch_device)
        dump(result, open(file_path, 'wb'))
        return result

def bert_feature_test():
    from hackashop_datasets.cro_24sata import cro24_load_forclassif
    bert_folder = BERT_CRO_V0
    texts, labels = cro24_load_forclassif('train')
    #bert_features(bert_folder, texts, features='transformer')
    bert_features(bert_folder, texts, features='predict')

def bert_feature_create(dset='est', bert_folder = BERT_CRO_V1,
                        max_len=128, torch_device='cpu', splits = ['dev', 'train', 'test']):
    for split in splits:
        # bert_feature_loader(dset, split, bert=bert_folder, features='transformer')
        # print(f'{split}-trans-fin')
        bert_feature_loader(dset, split, bert=bert_folder, features='predict',
                            max_len=max_len, torch_device=torch_device)
        print(f'{split}-predict-fin')

if __name__ == '__main__':
    #bert_feature_test()
    #bert_feature_create(dset='est', bert_folder=BERT_EST_V1, splits=['test2'])
    bert_feature_create(dset='cro', bert_folder=BERT_CRO_FINETUNE, splits=['test2'])