from __future__ import annotations
import argparse, json, time
from pathlib import Path
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from fir.data.ilsi import load_ilsi
from fir.statute.labels import LabelSpace
from fir.statute.tfidf_baseline import TfidfStatuteClassifier

def scores(model, instances, space):
    y=space.encode(instances)
    p=model.predict_proba([x.text for x in instances])
    return y,p

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--thresholds',default='0.1,0.2,0.3,0.4,0.5,0.6,0.7')
    ap.add_argument('--output',default='artifacts/audit/tfidf_baseline.json')
    ap.add_argument('--model',default='artifacts/models/tfidf_statute.joblib')
    args=ap.parse_args()
    t0=time.perf_counter(); space=LabelSpace.from_vocab()
    train,dev,test=(load_ilsi(s) for s in ('train','dev','test'))
    model=TfidfStatuteClassifier(label_space=space); model.fit(train)
    yd,pd=scores(model,dev,space)
    best=(0.5,-1.0)
    for raw in args.thresholds.split(','):
        th=float(raw); pred=(pd>=th).astype(np.float32); f=float(f1_score(yd,pred,average='micro',zero_division=0))
        if f>best[1]: best=(th,f)
    yt,pt=scores(model,test,space); th=best[0]; pred=(pt>=th).astype(np.float32)
    result={'dataset':{'train':len(train),'dev':len(dev),'test':len(test),'labels':len(space)},'model':model.name,'vectorizer':model.vectorizer_mode,'threshold':th,'train_seconds':model.train_seconds,'total_seconds':time.perf_counter()-t0,'metrics':{'micro_f1':float(f1_score(yt,pred,average='micro',zero_division=0)),'macro_f1':float(f1_score(yt,pred,average='macro',zero_division=0)),'micro_precision':float(precision_score(yt,pred,average='micro',zero_division=0)),'micro_recall':float(recall_score(yt,pred,average='micro',zero_division=0)),'predicted_labels':int(pred.sum()),'gold_labels':int(yt.sum())}}
    out=ROOT/args.output; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8'); model.save(ROOT/args.model); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
