# move_clf held-out report

corpus: PubMed 20k RCT (Dernoncourt & Lee 2017) · seed 20260814 · sklearn 1.8.0
test accuracy: **0.8255** (30,135 sentences)

```
              precision    recall  f1-score   support

  BACKGROUND      0.656     0.666     0.661      3621
 CONCLUSIONS      0.757     0.754     0.756      4571
     METHODS      0.887     0.924     0.905      9897
   OBJECTIVE      0.669     0.549     0.603      2333
     RESULTS      0.888     0.884     0.886      9713

    accuracy                          0.826     30135
   macro avg      0.771     0.756     0.762     30135
weighted avg      0.823     0.826     0.824     30135
```

## Abstention curve (threshold → coverage, accuracy)

- 0.0 → coverage 100.0%, accuracy 82.5%
- 0.4 → coverage 98.1%, accuracy 83.4%
- 0.5 → coverage 93.1%, accuracy 85.3%
- 0.6 → coverage 84.5%, accuracy 88.3%
- 0.7 → coverage 76.0%, accuracy 90.9%
- 0.8 → coverage 66.0%, accuracy 93.3%
- 0.9 → coverage 52.0%, accuracy 95.8%
