import random, numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.model_selection import GridSearchCV, StratifiedKFold

from classification_experiments.BertFeatureExtractor import BertFeatureExtractor
from classification_experiments.classification_models import build_classifier
from classification_experiments.feature_extraction import *
from hackashop_datasets.cro_24sata import cro24_load_tfidf
from hackashop_datasets.est_express import est_load_tfidf
from classification_experiments.feature_extraction import bert_feature_loader
from scipy.sparse import csr_matrix, hstack


def get_classifier(c):
    '''
    Factory method building scikit-learn classifiers.
    :param c: classifier label
    '''
    if c == 'logreg':
        return LogisticRegression(solver='liblinear', max_iter=1000, penalty='l1', C=1.0)
    elif c == 'svm':
        return SVC()

def build_and_test_classifier(data, features="bert", classifier="logreg",
                              subsample=None, rseed=572):
    '''
    Build and test binary classifier -
     subsample data if specified, create train/test split, train and test.
    :param data: (texts, labels) pair - list of texts, list of binary labels
    :param features: 'bert' of 'tfidf'
    :param subsample: if not False, first subsample data to given size
    :return:
    '''
    classif = create_classifier(features, classifier)
    # prepare data
    texts, labels = subsample_data(data, subsample, rseed)
    N = len(texts); print(f'Dataset size: {N}')
    texts_train, texts_test, labels_train, labels_test = \
        train_test_split(texts, labels, test_size=0.33, random_state=rseed)
    # train
    classif.fit(texts_train, labels_train)
    labels_predict = classif.predict(texts_test)
    # calculate
    test_classifier(classif, (texts_test, labels_test), subsample=False)

from sklearn.pipeline import FeatureUnion
class IndexTransformer():
    def __init__(self, features):
        self._feats = features
    def fit(self, X): pass
    def transform(self, ix):
        if isinstance(ix, list): return [self._feats[i] for i in ix]
        else: return self._feats[ix]

def build_and_test_classifier_split(train, test, classifier='logreg', balanced=False,
                                    features='bert', bigrams=False, binary=True,
                                    label = '', rseed=572, opt_metrics='f1',
                                    bert_loader =
                                    {'dset':'', 'train_label':'', 'test_label':'', 'bert':'',
                                     'features':'predict'}):
    '''
    Build and test binary classifier on a train/test split data.
    :param train: (texts, labels) pair - list of texts, list of binary labels
    :param test: (texts, labels) pair - list of texts, list of binary labels
    :param features: 'bert' of 'tfidf'
    :return:
    '''
    texts_train, labels_train  = train
    texts_test, labels_test = test
    N = len(texts_train);
    print(f'classification {label}: {classifier}, bal:{balanced}, '
          f'feats:{features}, bigrams:{bigrams}, binary:{binary}, opt:{opt_metrics}, '
          f'seed:{rseed}, train size: {N}')
    np.random.seed(rseed)
    # prepare data
    # feature extraction
    transform = True
    if features == 'bert': fextr = BertFeatureExtractor();
    elif features == 'tfidf': # fit tfidf on train+test texts
        fextr = tfidf_features(bigrams=bigrams)
        all_texts = []; all_texts.extend(texts_train); all_texts.extend(texts_test)
        fextr.fit(all_texts)
    elif features == 'tfidf+bert' or features == 'wcount+bert':
        transform = False
        if features.startswith('tfidf'):
            count_extr = tfidf_features(bigrams=bigrams)
        else:
            count_extr = wcount_features(bigrams=bigrams, binary=binary)
        all_texts = []; all_texts.extend(texts_train); all_texts.extend(texts_test)
        count_extr.fit(all_texts)
        cnt_train = count_extr.transform(texts_train); n_train = cnt_train.shape[0]
        cnt_test = count_extr.transform(texts_test); n_test = cnt_test.shape[0]
        #print(type(cnt_train), cnt_train.shape)
        bert, dset, bert_feats = bert_loader['bert'], bert_loader['dset'], bert_loader['features']
        trans_train = bert_feature_loader(dataset=dset, bert=bert, split=bert_loader['train_label'],
                                          features=bert_feats)
        if bert_feats == 'predict': trans_train, _ = trans_train
        #trans_train = np.ones((n_train, 700))
        trans_train = csr_matrix(trans_train)
        final_train = hstack([cnt_train, trans_train])
        #print(type(final_train), final_train.shape)
        trans_test = bert_feature_loader(dataset=dset, bert=bert, split=bert_loader['test_label'],
                                          features=bert_feats)
        if bert_feats == 'predict': trans_test, _ = trans_test
        trans_test = csr_matrix(trans_test)
        final_test = hstack([cnt_test, trans_test])
        feats_train = final_train
        feats_test = final_test
    elif features == 'wcount':
        fextr = wcount_features(bigrams=bigrams, binary=binary)
        all_texts = []; all_texts.extend(texts_train); all_texts.extend(texts_test)
        fextr.fit(all_texts)
    elif features == 'tfidf-cro': fextr = cro24_load_tfidf()
    elif features == 'tfidf-est': fextr = est_load_tfidf()
    if transform:
        feats_train = fextr.transform(texts_train)
        feats_test = fextr.transform(texts_test)
    # train model
    classif = create_classifier_grid(classifier, balanced=balanced, opt_metrics=opt_metrics)
    classif.fit(feats_train, labels_train)
    if ('grid' in classifier): print(classif.best_params_, classif.best_score_)
    # calculate
    test_classifier(classif, (feats_test, labels_test), subsample=False)

def create_classifier(features='bert', classifier='logreg'):
    '''
    Compose a scikit-learn classifier ready for training.
    :param features: 'bert' of 'tfidf'
    :parameter classifier: 'logreg' or 'svm'
    :return:
    '''
    if features == 'bert': fextr = BertFeatureExtractor();
    elif features == 'tfidf': fextr = TfidfVectorizer()
    classifier = get_classifier(classifier)
    pipe = [('fextr', fextr),
            ('classifier', classifier)]
    pipe = Pipeline(pipe)
    return pipe

def create_classifier_grid(classifier='logreg', balanced=False, opt_metrics='f1'):
    '''
    Factory method building scikit-learn classifiers, possibly
     wrapped in a crossvalidation fitter using grid search.
    :param c: classifier label
    '''
    #if features == 'bert': fextr = BertFeatureExtractor();
    #elif features == 'tfidf': fextr = TfidfVectorizer()
    if 'grid' in classifier:
        model, paramgrid = build_classifier(classifier)
        if balanced: paramgrid['class_weight'] = ['balanced']
        # model_label = 'classifier'
        # pipe = [('feature_extr', fextr),
        #         (model_label, model)]
        # pipe = Pipeline(pipe)
        # grid = {'%s__%s' % (model_label, k): v for k, v in paramgrid.items()}
        # cvFitter = GridSearchCV(estimator=pipe, param_grid=grid, cv=5,
        #                         scoring='f1', verbose=True, n_jobs=3)
        cvFitter = GridSearchCV(estimator=model, param_grid=paramgrid, cv=5,
                                scoring=opt_metrics, verbose=True, n_jobs=3)
        return cvFitter
    else:
        return build_classifier(classifier, balanced)

def create_train_classifier(train, features='bert', classifier='logreg', subsample=False, rseed=883):
    '''
    Create classifier, fit to data, possibly with subsampling
    :param train: texts, labels
    '''
    classif = create_classifier(features, classifier)
    train = subsample_data(train, subsample=subsample, rseed=rseed)
    texts, data = train
    classif.fit(texts, data)
    return classif


def subsample_data(data, subsample, rseed=572):
    '''
    :param data: texts, labels
    :param subsample: subsample size
    :return: subsampled texts, labels
    '''
    if not subsample: return data
    texts, labels = data; N = len(texts)
    if subsample >= N or subsample < 0: return data
    random.seed(rseed)
    ids = random.sample(range(N), subsample)
    texts, labels = [texts[i] for i in ids], [labels[i] for i in ids]
    return texts, labels


def test_classifier(c, data, subsample=False, rseed=883):
    '''
    Compare predictions of classifier with correct labels
    :param c: trained sklearn classifier
    :param data: text, labels - reference (correct) labeling
    :param subsample: if true, test on a subsample of data
    :return:
    '''
    if subsample: texts, labels = subsample_data(data, subsample, rseed)
    else: texts, labels = data
    labels_predict = c.predict(texts)
    # calculate
    evaluate_predictions(labels_predict, labels)

def evaluate_predictions(labels_predict, labels_correct):
    f1 = f1_score(labels_correct, labels_predict)
    precision = precision_score(labels_correct, labels_predict)
    recall = recall_score(labels_correct, labels_predict)
    acc = accuracy_score(labels_correct, labels_predict)
    print(f"f1: {f1:1.3f}, precision: {precision:1.3f}, recall: {recall:1.3f}, acc: {acc:1.3f}")
    return [f1, precision, recall]

def calculate_baseline_f1(minority):
    '''
    Calculate f1 scores of several baseline binary classifiers.
    :param minority: proportion of the minorty class, in <0, 1> range
    '''
    min, maj = minority, 1.0 - minority
    # alway choose minority class
    min_always = 2*min/(min+1)
    print(f'always min F1: {min_always:1.3f}')
    # predict minority with 50% chance
    min_50 = 2*min*0.5/(min+0.5)
    print(f'min 50% F1: {min_50:1.3f}')
    # pridict minority with chance min (orig. proportion)
    min_min = min
    print(f'min min F1: {min_min:1.3f}')

