import streamlit as st
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import requests

# Load API key securely from Streamlit secrets
GROQ_API_URL = "https://api.groq.com/v1/completions"  # Update if needed
API_KEY = "your-api-key-here"

# Handle missing and infinite values
def handle_missing_values(data):
    if 'Label' in data.columns:
        data.dropna(subset=['Label'], inplace=True)
    else:
        st.error("Label column not found in the dataset.")

    data.replace([np.inf, -np.inf], np.nan, inplace=True)
    for col in data.select_dtypes(include=['int', 'float']).columns:
        data[col].fillna(data[col].median(), inplace=True)

    return data

# Optimize memory usage
def optimize_memory_usage(data):
    data = handle_missing_values(data)

    for col in data.select_dtypes(include=['int', 'float']).columns:
        data[col] = pd.to_numeric(data[col], downcast='float')

    for col in data.select_dtypes(include=['object']).columns:
        data[col] = data[col].astype('category')

    return data

# Load and combine CSV files
def load_and_combine_data(uploaded_files):
    combined_data = []
    for uploaded_file in uploaded_files:
        chunk_iter = pd.read_csv(uploaded_file, chunksize=10000)
        for chunk in chunk_iter:
            chunk.columns = chunk.columns.str.strip()

            if 'label' in chunk.columns:
                chunk.rename(columns={'label': 'Label'}, inplace=True)
            elif 'Class' in chunk.columns:
                chunk.rename(columns={'Class': 'Label'}, inplace=True)
            else:
                chunk['Label'] = 'normal'

            chunk = optimize_memory_usage(chunk)
            combined_data.append(chunk)

    return pd.concat(combined_data, ignore_index=True)

# Preprocess data
def preprocess_data(data):
    le = LabelEncoder()
    data['Label'] = le.fit_transform(data['Label'])

    print("Class Distribution After Encoding:", data['Label'].value_counts())

    irrelevant_cols = ['Timestamp', 'ID']
    data.drop(columns=irrelevant_cols, inplace=True, errors='ignore')

    categorical_cols = [col for col in data.columns if data[col].dtype.name == 'category']
    data = pd.get_dummies(data, columns=categorical_cols, drop_first=True)

    X = data.drop(columns=['Label'])
    y = data['Label']

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y), scaler, le

# Train Random Forest Model
def train_model(X_train, y_train, n_estimators=100):
    model = RandomForestClassifier(n_estimators=n_estimators, random_state=42)
    model.fit(X_train, y_train)
    return model

# Train Isolation Forest (Anomaly Detection)
def train_anomaly_detector(X_train):
    contamination_rate = 0.1  # Adjusted dynamically based on anomalies
    anomaly_detector = IsolationForest(contamination=contamination_rate, random_state=42)
    anomaly_detector.fit(X_train)
    return anomaly_detector

# Evaluate model
def evaluate_model(model, X_test, y_test):
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)

    st.write("### Model Performance")
    st.write(f"Accuracy: {accuracy:.4f}")
    st.text(classification_report(y_test, predictions))

    # Display Confusion Matrix
    cm = confusion_matrix(y_test, predictions)
    st.write("#### Confusion Matrix")
    st.write(cm)

# Groq API Inference
def predict_with_groq(input_data):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "qwen-2.5-32b",
        "prompt": f"Analyze the following network traffic data: {input_data}",
        "temperature": 0.6,
        "max_tokens": 100
    }
    response = requests.post(GROQ_API_URL, headers=headers, json=payload)
    return response.json().get("choices", [{}])[0].get("text", "No response")

# Streamlit App
def main():
    st.title("Cybersecurity Intrusion Detection")
    st.image("logo.png", width=700)

    uploaded_files = st.file_uploader("Upload Network Traffic CSV Files", accept_multiple_files=True, type='csv')
    
    if uploaded_files:
        combined_data = load_and_combine_data(uploaded_files)
        st.subheader("Dataset Overview")
        st.dataframe(combined_data.head())

        (X_train, X_test, y_train, y_test), scaler, le = preprocess_data(combined_data)

        st.subheader("Model Training")
        n_estimators = st.slider("Number of Estimators", 50, 300, 100, step=50)
        
        # Train Classifier & Anomaly Detector
        model = train_model(X_train, y_train, n_estimators)
        anomaly_detector = train_anomaly_detector(X_train)

        st.subheader("Model Evaluation")
        evaluate_model(model, X_test, y_test)

        if st.button("Detect Anomalies"):
            anomaly_predictions = anomaly_detector.predict(X_test)
            anomaly_predictions = np.where(anomaly_predictions == -1, "Anomaly", "Normal")

            combined_data['Anomaly Prediction'] = anomaly_predictions.tolist() + [None] * (len(combined_data) - len(anomaly_predictions))
            suspicious = combined_data[combined_data['Anomaly Prediction'] == "Anomaly"]

            st.subheader("Suspicious Activities Detected")
            st.dataframe(suspicious)

            if not suspicious.empty:
                st.error("⚠️ ALERT: Suspicious activities detected!")
            else:
                st.success("✅ No threats detected.")

if __name__ == "__main__":
    main()
