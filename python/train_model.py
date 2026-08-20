"""
train_model.py
==============

Trains the fuel quality classifier and exports it as a plain
JSON weight file (model_weights.json) that the on-device
inference module (fuelQualityModel.py) can run with numpy only.
No sklearn / TFLite runtime needed on the UNO Q.

Model: MLP 6 -> 16 -> 16 -> 3 (softmax), ~450 parameters.
Inference cost on a Cortex-A53: microseconds. Trivially real-time.

Run:  python3 train_model.py
Outputs:
  model_weights.json   (weights + scaler, ship this to the board)
  metrics.txt          (accuracy, confusion matrix, report)
"""

import json
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import (accuracy_score, confusion_matrix,
                             classification_report)

from fuel_simulator import generate_dataset, LABELS
from features import extract_batch, FEATURE_NAMES

# ------------------------------------------------------------------
# 1. Data
# ------------------------------------------------------------------
print("Generating physics-based dataset ...")
rows, y = generate_dataset(n_per_class=6000)
X = extract_batch(rows)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, stratify=y, random_state=7
)

scaler = StandardScaler().fit(X_train)
X_train_s = scaler.transform(X_train)
X_test_s = scaler.transform(X_test)

# ------------------------------------------------------------------
# 2. Model
# ------------------------------------------------------------------
print("Training MLP (6-16-16-3) ...")
clf = MLPClassifier(
    hidden_layer_sizes=(16, 16),
    activation="relu",
    alpha=1e-4,
    max_iter=600,
    random_state=7,
)
clf.fit(X_train_s, y_train)

# ------------------------------------------------------------------
# 3. Evaluation
# ------------------------------------------------------------------
y_pred = clf.predict(X_test_s)
acc = accuracy_score(y_test, y_pred)
cm = confusion_matrix(y_test, y_pred)
report = classification_report(
    y_test, y_pred, target_names=[LABELS[i] for i in range(3)]
)

print(f"\nTest accuracy: {acc:.4f}")
print("Confusion matrix (rows=true, cols=pred):")
print(cm)
print(report)

with open("metrics.txt", "w") as fp:
    fp.write(f"Test accuracy: {acc:.4f}\n\n")
    fp.write("Confusion matrix (rows=true, cols=pred):\n")
    fp.write(str(cm) + "\n\n")
    fp.write(report)

# ------------------------------------------------------------------
# 4. Export to portable JSON (numpy-only inference on device)
# ------------------------------------------------------------------
export = {
    "feature_names": FEATURE_NAMES,
    "labels": LABELS,
    "scaler_mean": scaler.mean_.tolist(),
    "scaler_scale": scaler.scale_.tolist(),
    "layers": [
        {"W": W.tolist(), "b": b.tolist()}
        for W, b in zip(clf.coefs_, clf.intercepts_)
    ],
    "activation": "relu",
    "test_accuracy": acc,
}

with open("model_weights.json", "w") as fp:
    json.dump(export, fp)

n_params = sum(W.size + b.size
               for W, b in zip(clf.coefs_, clf.intercepts_))
print(f"\nExported model_weights.json ({n_params} parameters)")
