import numpy as np
import scipy.spatial
import sklearn.manifold

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.colors
import matplotlib.patches
import matplotlib.gridspec

import seaborn as sns

import sklearn as skl
import sklearn.metrics

import warnings

from . import utils

class SampleFeatureMatrix(object):
    """
    SampleFeatureMatrix is a (n_samples, n_features) matrix. 
    In this package, we are only interested in float features as measured
    expression levels. 
    Parameters
    ----------
    x : ndarray or list
        data matrix (n_samples, n_features)
    sids : homogenous list of int or string
        sample ids. Should not contain duplicated elements. 
    fids : homogenous list of int or string
        feature ids. Should not contain duplicated elements. 

    Attributes:
    -----------
    _x : ndarray
        data matrix (n_samples, n_features)
    _d : ndarray
        distance matrix (n_samples, n_samples)
    _sids : ndarray
        sample ids.
    _fids : ndarray
        sample ids.

    Methods defined here:
    """
    def __init__(self, x, sids=None, fids=None):
        super(SampleFeatureMatrix, self).__init__()
        if x is None:
            raise ValueError("x cannot be None")
        else:
            try:
                x = np.array(x, dtype="float64")
            except ValueError as e:
                raise ValueError("Features must be float. {}".format(e))
            
            if x.ndim != 2:
                raise ValueError("x has shape (n_samples, n_features)")

            if x.size == 0:
                raise ValueError("size of x cannot be 0")

        if sids is None:
            sids = list(range(x.shape[0]))
        else:
            self.check_is_valid_sfids(sids)
            if len(sids) != x.shape[0]:
                raise ValueError("x has shape (n_samples, n_features)")

        if fids is None:
            fids = list(range(x.shape[1]))
        else:
            self.check_is_valid_sfids(fids)
            if len(fids) != x.shape[1]:
                raise ValueError("x has shape (n_samples, n_features)")

        self._x = x
        self._sids = np.array(sids)
        self._fids = np.array(fids)

    @staticmethod
    def is_valid_sfid(sfid):
        return (type(sfid) == str) or (type(sfid) == int)

    @staticmethod
    def check_is_valid_sfids(sfids):
        if sfids is None:
            raise ValueError("[sf]ids cannot be None")

        if type(sfids) != list:
            raise ValueError("[sf]ids must be a homogenous list of int or str")

        if len(sfids) == 0:
            raise ValueError("[sf]ids must have >= 1 values")

        sid_types = tuple(map(type, sfids))
        if len(set(sid_types)) != 1:
            raise ValueError("[sf]ids must be a homogenous list of int or str")

        if not SampleFeatureMatrix.is_valid_sfid(sfids[0]):
            raise ValueError("[sf]ids must be a homogenous list of int or str")

        sfids = np.array(sfids)
        assert sfids.ndim == 1
        assert sfids.shape[0] > 0
        if not utils.is_uniq_np1darr(sfids):
            raise ValueError("[sf]ids must not contain duplicated values")

    @property
    def sids(self):
        return self._sids.copy()

    @property
    def fids(self):
        return self._fids.copy()

    @property
    def x(self):
        return self._x.copy()


class SampleDistanceMatrix(SampleFeatureMatrix):
    """
    SampleDistanceMatrix: data with pairwise distance matrix

    Parameters
    ----------
    x : ndarray or list
        data matrix (n_samples, n_features)
    d : ndarray or list or None
        distance matrix (n_samples, n_samples)
        If is None, d will be computed with x, metric, and nprocs.
    metric : string
        distance metric
    sids : homogenous list of int or string
        sample ids. Should not contain duplicated elements. 
    fids : homogenous list of int or string
        feature ids. Should not contain duplicated elements. 
    nprocs : int
        the number of processes for computing pairwise distance matrix

    Attributes:
    -----------
    _x : ndarray
        data matrix (n_samples, n_features)
    _d : ndarray
        distance matrix (n_samples, n_samples)
    _metric : string
        distance metric
    _sids : ndarray
        sample ids.
    _fids : ndarray
        sample ids.
    """
    def __init__(self, x, d=None, metric=None, sids=None, fids=None, nprocs=None):
        super(SampleDistanceMatrix, self).__init__(x=x, sids=sids, fids=fids)

        if d is None:
            if metric is None:
                raise ValueError("If d is None, metric must be provided.")
            elif type(metric) != str:
                raise ValueError("metric must be string")

            if nprocs is None:
                nprocs = 1
            else:
                nprocs = max(int(nprocs), 1)

            d = skl.metrics.pairwise.pairwise_distances(x, metric=metric, 
                                                        n_jobs=nprocs)
        else:
            try:
                d = np.array(d, dtype="float64")
            except ValueError as e:
                raise ValueError("d must be float. {}".format(e))
            
            if ((d.ndim != 2) 
                or (d.shape[0] != d.shape[1]) 
                or (d.shape[0] != self._x.shape[0])):
                raise ValueError("d should have shape (n_samples, n_samples)")
        
        d = self.num_correct_dist_mat(d)
        self._d = d
        self._tsne_lut = {}
        self._metric = metric

    # numerically correct dmat
    @staticmethod
    def num_correct_dist_mat(dmat, upper_bound=None):
        if ((not isinstance(dmat, np.ndarray))
            or (dmat.ndim != 2)
            or (dmat.shape[0] != dmat.shape[1])):
            raise ValueError("dmat must be a 2D (n_samples, n_samples)"
                             " np array")

        try:
            # Distance matrix diag vals should be close to 0.
            np.testing.assert_allclose(dmat[np.diag_indices(dmat.shape[0])], 0,
                                       atol=1e-10)
        except AssertionError as e:
            warnings.warn("distance matrix might not be numerically "
                          "correct. diag vals should be close to 0. {}".format(e))
        
        try:
            # distance matrix should be approximately symmetric
            np.testing.assert_allclose(dmat[np.triu_indices_from(dmat)], 
                                       dmat.T[np.triu_indices_from(dmat)])
        except AssertionError as e:
            warnings.warn("distance matrix might not be numerically "
                          "correct. should be approximately symmetric. {}".format(e))
        
        dmat[dmat < 0] = 0
        dmat[np.diag_indices(dmat.shape[0])] = 0
        if upper_bound is not None:
            upper_bound = float(upper_bound)
            dmat[dmat > upper_bound] = upper_bound

        dmat[np.triu_indices_from(dmat)] = dmat.T[np.triu_indices_from(dmat)]
        return dmat

    # store_res : bool. Wheter to keep the tsne results in a dictionalry keyed
    # by the parameters. 
    def tsne(self, store_res=True, **kwargs):
        if ("metric" in kwargs) and (kwargs["metric"] not in ("precomputed", self._metric)):
            raise ValueError("If you want to calculate t-SNE of a different "
                             "metric than the instance metric, create another "
                             "instance of the desired metric.")
        else:
            kwargs["metric"] = "precomputed"

        tsne_res = tsne(self._d, **kwargs)

        if store_res:
            curr_store_ind = len(self._tsne_lut) + 1
            self._tsne_lut[str(kwargs)
                           + " stored run {}".format(curr_store_ind)] = tsne_res
        
        return tsne_res

    @property
    def d(self):
        return self._d.copy()

    @property
    def metric(self):
        return self._metric

    @property
    def tsne_lut(self):
        return dict((key, val) for key, val in self._tsne_lut.items())
    

# x : (n_samples, n_features) or (n_samples, n_samples)
# If metric is 'precomputed', x must be a pairwise distance matrix
def tsne(x, n_components=2, perplexity=30.0, early_exaggeration=12.0, 
         learning_rate=200.0, n_iter=1000, n_iter_without_progress=300, 
         min_grad_norm=1e-07, metric="euclidean", init="random", verbose=0, 
         random_state=None, method="barnes_hut", angle=0.5):
    x_tsne = sklearn.manifold.TSNE(n_components=n_components, 
                                   perplexity=perplexity, 
                                   early_exaggeration=early_exaggeration, 
                                   learning_rate=learning_rate, n_iter=n_iter, 
                                   n_iter_without_progress=n_iter_without_progress, 
                                   min_grad_norm=min_grad_norm, metric=metric, 
                                   init=init, verbose=verbose, 
                                   random_state=random_state, method=method, 
                                   angle=angle).fit_transform(x)
    return x_tsne



class SingleLabelClassifiedSamples(SampleDistanceMatrix):
    """docstring for SingleLabelClassifiedSamples"""
    # sid, lab, fid, x
    def __init__(self, x, labs, sids=None, fids=None, 
                 d=None, metric="correlation", nprocs=None):
        # sids: sample IDs. String or int.
        # labs: sample classified labels. String or int. 
        # x: (n_samples, n_features)
        super(SingleLabelClassifiedSamples, self).__init__(x=x, d=d, 
                                                           metric=metric, 
                                                           sids=sids, fids=fids,
                                                           nprocs=nprocs)
        self.check_is_valid_labs(labs)
        labs = np.array(labs)
        if self._sids.shape[0] != labs.shape[0]:
            raise ValueError("sids must have the same length as labs")
        self._labs = labs

        sid_lut = {}
        for uniq_lab in np.unique(labs):
            sid_lut[uniq_lab] = self._sids[labs == uniq_lab]
        self._sid_lut = sid_lut

        lab_lut = {}
        # sids only contain unique values
        for i in range(self._sids.shape[0]):
            lab_lut[self._sids[i]] = labs[i]
        self._lab_lut = lab_lut
        return

    @staticmethod
    def is_valid_lab(lab):
        return (type(lab) == str) or (type(lab) == int)

    @staticmethod
    def check_is_valid_labs(labs):
        if labs is None:
            raise ValueError("labs cannot be None")

        if type(labs) != list:
            raise ValueError("labs must be a homogenous list of int or str")
        
        if len(labs) == 0:
            raise ValueError("labs cannot be empty")

        if len(set(map(type, labs))) != 1:
            raise ValueError("labs must be a homogenous list of int or str")

        if not SingleLabelClassifiedSamples.is_valid_lab(labs[0]):
            raise ValueError("labs must be a homogenous list of int or str")

        labs = np.array(labs)
        assert labs.ndim == 1, "Labels must be 1D"
        assert labs.shape[0] > 0
        
    def filter_min_class_n(self, min_class_n):
        uniq_lab_cnts = np.unique(self._labs, return_counts=True)
        nf_sid_ind = np.in1d(self._labs, 
                             (uniq_lab_cnts[0])[uniq_lab_cnts[1] >= min_class_n])
        return (self._sids[nf_sid_ind], self._labs[nf_sid_ind])

    def labs_to_sids(self, labs):
        return tuple(tuple(self._sid_lut[y].copy()) for y in labs)

    def sids_to_labs(self, sids):
        return np.array([self._lab_lut[x] for x in sids])
    
    @property
    def labs(self):
        return self._labs.copy()
    
    # Sort the clustered sample_ids with the reference order of another. 
    # 
    # Sort sids according to labs
    # If ref_sid_order is not None:
    #   sort sids further according to ref_sid_order
    def lab_sorted_sids(self, ref_sid_order=None):
        sep_lab_sid_list = []
        sep_lab_list = []
        for iter_lab in sorted(self._sid_lut.keys()):
            iter_sid_arr = self._sid_lut[iter_lab]
            sep_lab_sid_list.append(iter_sid_arr)
            sep_lab_list.append(np.repeat(iter_lab, len(iter_sid_arr)))

        if ref_sid_order is not None:
            self.check_is_valid_sfids(ref_sid_order)
            ref_sid_order = np.array(ref_sid_order)
            # sort r according to q
            # assumes:
            # - r contains all elements in q
            # - r is 1d np array
            def sort_flat_sids(query_sids, ref_sids):
                return ref_sids[np.in1d(ref_sids, query_sids)]

            # sort inner sid list but maintains the order as sep_lab_list
            sep_lab_sid_list = [sort_flat_sids(x, ref_sid_order)
                                for x in sep_lab_sid_list]
            sep_lab_min_sid_list = [x[0] for x in sep_lab_sid_list]
            sorted_sep_lab_min_sid_list = list(sort_flat_sids(sep_lab_min_sid_list,
                                                              ref_sid_order))
            min_sid_sorted_sep_lab_ind_list = [sep_lab_min_sid_list.index(x)
                                               for x in sorted_sep_lab_min_sid_list]
            sep_lab_list = [sep_lab_list[i] for i in min_sid_sorted_sep_lab_ind_list]
            sep_lab_sid_list = [sep_lab_sid_list[i] for i in min_sid_sorted_sep_lab_ind_list]

        lab_sorted_sid_arr = np.concatenate(sep_lab_sid_list)
        lab_sorted_lab_arr = np.concatenate(sep_lab_list)
        
        # check sorted sids are the same set as original    
        np.testing.assert_array_equal(np.sort(lab_sorted_sid_arr), np.sort(self._sids))
        # check sorted labs are the same set as original
        np.testing.assert_array_equal(np.sort(lab_sorted_lab_arr), np.sort(self._labs))
        # check sorted (sid, lab) matchings are the same set as original
        np.testing.assert_array_equal(lab_sorted_lab_arr[np.argsort(lab_sorted_sid_arr)], 
                                      self._labs[np.argsort(self._sids)])

        return (lab_sorted_sid_arr, lab_sorted_lab_arr)

    # See how two clustering criteria match with each other.
    # When given q_slc_samples is not None, sids and labs are ignored. 
    # When q_slc_samples is None, sids and labs must be provided
    def cross_labs(self, q_slc_samples):
        if not isinstance(q_slc_samples, SingleLabelClassifiedSamples):
            raise TypeError("Query should be an instance of "
                            "SingleLabelClassifiedSamples")
        
        try:
            ref_labs = np.array([self._lab_lut[x] 
                                 for x in q_slc_samples.sids])
        except KeyError as e:
            raise ValueError("query sid {} is not in ref sids.".format(e))

        query_labs = q_slc_samples.labs
        
        uniq_rlabs, uniq_rlab_cnts = np.unique(ref_labs, return_counts=True)
        cross_lab_lut = {}
        for i in range(len(uniq_rlabs)):
            # ref cluster i. query unique labs.
            ref_ci_quniq = tuple(map(list, np.unique(
                query_labs[np.where(np.array(ref_labs) == uniq_rlabs[i])],
                return_counts=True)))
            cross_lab_lut[uniq_rlabs[i]] = (uniq_rlab_cnts[i], tuple(map(tuple, ref_ci_quniq)))

        return cross_lab_lut

    def labs_to_cmap(self, return_lut=False):
        uniq_lab_arr = np.unique(self._labs)
        num_uniq_labs = len(uniq_lab_arr)

        uniq_lab_lut = dict(zip(range(num_uniq_labs), uniq_lab_arr))
        uniq_ind_lut = dict(zip(uniq_lab_arr, range(num_uniq_labs)))
        
        lab_ind_arr = np.array([uniq_ind_lut[x] for x in self._labs])

        lab_col_list = sns.hls_palette(num_uniq_labs)
        lab_cmap = mpl.colors.ListedColormap(lab_col_list)

        lab_col_lut = dict(zip([uniq_lab_lut[i] for i in range(len(uniq_lab_arr))],
                               lab_col_list))

        if return_lut:
            return (lab_cmap, lab_ind_arr, lab_col_lut, uniq_lab_lut)
        else:
            return lab_cmap


# TODO: tsne graph, heatmap. Test graph existence only. 

def cluster_scatter(tsne, labels=None, title=None, xlab=None, ylab=None, 
                 figsize=(20, 20), add_legend=True, n_txt_per_cluster=3, alpha=1, 
                 s=0.5, random_state=None, **kwargs):
    tsne = np.array(tsne, dtype="float")

    if (tsne.ndim != 2) or (tsne.shape[1] != 2):
        raise ValueError("tsne matrix should have shape (n_samples, 2)."
                         " {}".format(tsne))

    fig, ax = plt.subplots(figsize=figsize)

    if labels is not None:
        SingleLabelClassifiedSamples.check_is_valid_labs(labels)
        labels = np.array(labels)
        if labels.shape[0] != tsne.shape[0]:
            raise ValueError("nrow(tsne matrix) should be equal to len(labels)")

        uniq_labels = np.unique(labels)
        color_lut = dict(zip(uniq_labels, 
                             sns.color_palette("hls", len(uniq_labels))))

        ax.scatter(tsne[:, 0], tsne[:, 1], 
                   c=tuple(map(lambda cl: color_lut[cl], labels)),
                   s=s, alpha = alpha, **kwargs)
        # randomly select labels for annotation
        if random_state is not None:
            np.random.seed(random_state)
        
        anno_ind = np.concatenate([np.random.choice(np.where(labels == ulab)[0], 
                                                    n_txt_per_cluster) 
                                   for ulab in uniq_labels])

        for i in map(int, anno_ind):
            ax.annotate(labels[i], (tsne[i, 0], tsne[i, 1]))
        # Add legend
        # Shrink current axis by 20%
        if add_legend:
            box = ax.get_position()
            ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])        
            ax.legend(handles=tuple(mpl.patches.Patch(color=color_lut[ulab], label=ulab)
                                    for ulab in uniq_labels), 
                      bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    else:
        ax.scatter(tsne[:, 0], tsne[:, 1], s=s, alpha = alpha, **kwargs)

    if title is not None:
        ax.set_title(title)
    
    if xlab is not None:
        ax.set_xlabel(xlab)

    if ylab is not None:
        ax.set_ylabel(ylab)
            
    return ax

