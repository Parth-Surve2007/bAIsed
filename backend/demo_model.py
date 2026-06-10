import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
import joblib
import os

# Load the demo credit dataset
DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'demo_credit.csv'))

def load_data(path=DATA_PATH):
    df = pd.read_csv(path)
    # Encode categorical variables
    df_encoded = pd.get_dummies(df, drop_first=True)
    X = df_encoded.drop('Loan Approved', axis=1)
    y = df_encoded['Loan Approved']
    return X, y

def train_model():
    X, y = load_data()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    # Save model
    model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'demo_credit_model.pkl'))
    joblib.dump(model, model_path)
    print(f"Model trained and saved to {model_path}")
    # Print basic accuracy
    acc = model.score(X_test, y_test)
    print(f"Test Accuracy: {acc:.3f}")

if __name__ == '__main__':
    train_model()
