# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/20_interpret.ipynb (unless otherwise specified).


from __future__ import annotations


__all__ = ['plot_top_losses', 'Interpretation', 'ClassificationInterpretation', 'SegmentationInterpretation']

# Cell
#nbdev_comment from __future__ import annotations
from .data.all import *
from .optimizer import *
from .learner import *
from .tabular.core import *
import sklearn.metrics as skm

# Cell
@typedispatch
def plot_top_losses(x, y, *args, **kwargs):
    raise Exception(f"plot_top_losses is not implemented for {type(x)},{type(y)}")

# Cell
#nbdev_comment _all_ = ["plot_top_losses"]

# Cell
class Interpretation():
    "Interpretation base class, can be inherited for task specific Interpretation classes"
    def __init__(self,
        learn:Learner,
        dl:DataLoader, # `DataLoader` to run inference over
        losses:TensorBase, # Losses calculated from `dl`
        act=None # Activation function for prediction
    ):
        store_attr()

    def __getitem__(self, idxs):
        "Return inputs, preds, targs, decoded outputs, and losses at `idxs`"
        if isinstance(idxs, Tensor): idxs = idxs.tolist()
        if not is_listy(idxs): idxs = [idxs]
        items = getattr(self.dl.items, 'iloc', L(self.dl.items))[idxs]
        tmp_dl = self.learn.dls.test_dl(items, with_labels=True, process=not isinstance(self.dl, TabDataLoader))
        inps,preds,targs,decoded = self.learn.get_preds(dl=tmp_dl, with_input=True, with_loss=False,
                                                        with_decoded=True, act=self.act, reorder=False)
        return inps, preds, targs, decoded, self.losses[idxs]

    @classmethod
    def from_learner(cls,
        learn, # Model used to create interpretation
        ds_idx:int=1, # Index of `learn.dls` when `dl` is None
        dl:DataLoader=None, # `Dataloader` used to make predictions
        act=None # Override default or set prediction activation function
    ):
        "Construct interpretation object from a learner"
        if dl is None: dl = learn.dls[ds_idx].new(shuffle=False, drop_last=False)
        _,_,losses = learn.get_preds(dl=dl, with_input=False, with_loss=True, with_decoded=False,
                                     with_preds=False, with_targs=False, act=act)
        return cls(learn, dl, losses, act)

    def top_losses(self,
        k:(int,None)=None, # Return `k` losses, defaults to all
        largest:bool=True, # Sort losses by largest or smallest
        items:bool=False # Whether to return input items
    ):
        "`k` largest(/smallest) losses and indexes, defaulting to all losses."
        losses, idx = self.losses.topk(ifnone(k, len(self.losses)), largest=largest)
        if items: return losses, idx, getattr(self.dl.items, 'iloc', L(self.dl.items))[idx]
        else:     return losses, idx

    def plot_top_losses(self,
        k:(int,list), # Number of losses to plot
        largest:bool=True, # Sort losses by largest or smallest
        **kwargs
    ):
        "Show `k` largest(/smallest) preds and losses. Implementation based on type dispatch"
        if is_listy(k) or isinstance(k, range):
            losses, idx = (o[k] for o in self.top_losses(None, largest))
        else:
            losses, idx = self.top_losses(k, largest)
        inps, preds, targs, decoded, _ = self[idx]
        inps, targs, decoded = tuplify(inps), tuplify(targs), tuplify(decoded)
        x, y, its = self.dl._pre_show_batch(inps+targs, max_n=len(idx))
        x1, y1, outs = self.dl._pre_show_batch(inps+decoded, max_n=len(idx))
        if its is not None:
            plot_top_losses(x, y, its, outs.itemgot(slice(len(inps), None)), preds, losses, **kwargs)
        #TODO: figure out if this is needed
        #its None means that a batch knows how to show itself as a whole, so we pass x, x1
        #else: show_results(x, x1, its, ctxs=ctxs, max_n=max_n, **kwargs)

    def show_results(self,
        idxs:list, # Indices of predictions and targets
        **kwargs
    ):
        "Show predictions and targets of `idxs`"
        if isinstance(idxs, Tensor): idxs = idxs.tolist()
        if not is_listy(idxs): idxs = [idxs]
        inps, _, targs, decoded, _ = self[idxs]
        b = tuplify(inps)+tuplify(targs)
        self.dl.show_results(b, tuplify(decoded), max_n=len(idxs), **kwargs)

# Cell
class ClassificationInterpretation(Interpretation):
    "Interpretation methods for classification models."

    def __init__(self,
        learn:Learner,
        dl:DataLoader, # `DataLoader` to run inference over
        losses:TensorBase, # Losses calculated from `dl`
        act=None # Activation function for prediction
    ):
        super().__init__(learn, dl, losses, act)
        self.vocab = self.dl.vocab
        if is_listy(self.vocab): self.vocab = self.vocab[-1]

    def confusion_matrix(self):
        "Confusion matrix as an `np.ndarray`."
        x = torch.arange(0, len(self.vocab))
        _,targs,decoded = self.learn.get_preds(dl=self.dl, with_decoded=True, with_preds=True,
                                               with_targs=True, act=self.act)
        d,t = flatten_check(decoded, targs)
        cm = ((d==x[:,None]) & (t==x[:,None,None])).long().sum(2)
        return to_np(cm)

    def plot_confusion_matrix(self,
        normalize:bool=False, # Whether to normalize occurrences
        title:str='Confusion matrix', # Title of plot
        cmap:str="Blues", # Colormap from matplotlib
        norm_dec:int=2, # Decimal places for normalized occurrences
        plot_txt:bool=True, # Display occurrence in matrix
        **kwargs
    ):
        "Plot the confusion matrix, with `title` and using `cmap`."
        # This function is mainly copied from the sklearn docs
        cm = self.confusion_matrix()
        if normalize: cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        fig = plt.figure(**kwargs)
        plt.imshow(cm, interpolation='nearest', cmap=cmap)
        plt.title(title)
        tick_marks = np.arange(len(self.vocab))
        plt.xticks(tick_marks, self.vocab, rotation=90)
        plt.yticks(tick_marks, self.vocab, rotation=0)

        if plot_txt:
            thresh = cm.max() / 2.
            for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
                coeff = f'{cm[i, j]:.{norm_dec}f}' if normalize else f'{cm[i, j]}'
                plt.text(j, i, coeff, horizontalalignment="center", verticalalignment="center", color="white"
                         if cm[i, j] > thresh else "black")

        ax = fig.gca()
        ax.set_ylim(len(self.vocab)-.5,-.5)

        plt.tight_layout()
        plt.ylabel('Actual')
        plt.xlabel('Predicted')
        plt.grid(False)

    def most_confused(self, min_val=1):
        "Sorted descending largest non-diagonal entries of confusion matrix (actual, predicted, # occurrences"
        cm = self.confusion_matrix()
        np.fill_diagonal(cm, 0)
        res = [(self.vocab[i],self.vocab[j],cm[i,j]) for i,j in zip(*np.where(cm>=min_val))]
        return sorted(res, key=itemgetter(2), reverse=True)

    def print_classification_report(self):
        "Print scikit-learn classification report"
        _,targs,decoded = self.learn.get_preds(dl=self.dl, with_decoded=True, with_preds=True,
                                               with_targs=True, act=self.act)
        d,t = flatten_check(decoded, targs)
        names = [str(v) for v in self.vocab]
        print(skm.classification_report(t, d, labels=list(self.vocab.o2i.values()), target_names=names))

# Cell
class SegmentationInterpretation(Interpretation):
    "Interpretation methods for segmentation models."
    pass