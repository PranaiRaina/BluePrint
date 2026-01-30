"""
Test the sentiment model against the FiQA-PhraseBank dataset (CC0 licensed).
This evaluates how well our model performs on professionally-labeled financial sentences.
"""

import os
import pandas as pd
from transformers import pipeline
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# File paths
MODEL_PATH = os.path.join(os.path.dirname(__file__), "sentiment_model")
TEST_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "training_data", "FiQA-PhraseBank.csv"
)


def load_model():
    """Load the sentiment classification model."""
    print(f"Loading model from: {MODEL_PATH}")
    try:
        classifier = pipeline(
            "text-classification", model=MODEL_PATH, tokenizer=MODEL_PATH
        )
        print("✓ Model loaded successfully!")
        return classifier
    except OSError as e:
        print(f"✗ Failed to load model: {e}")
        return None


def load_test_data():
    """Load the FiQA-PhraseBank test dataset."""
    print(f"Loading test data from: {TEST_DATA_PATH}")
    df = pd.read_csv(TEST_DATA_PATH)

    # Drop any rows with null values
    df = df.dropna(subset=["Sentence", "Sentiment"])

    # Standardize sentiment labels to lowercase
    df["Sentiment"] = df["Sentiment"].str.strip().str.lower()

    # Filter to only valid sentiments
    valid_sentiments = {"positive", "negative", "neutral"}
    df = df[df["Sentiment"].isin(valid_sentiments)]

    print(f"✓ Loaded {len(df)} test samples")
    print(f"  Distribution: {df['Sentiment'].value_counts().to_dict()}")
    return df


def map_model_output(label):
    """Map model output labels to standardized sentiment."""
    label = label.upper()
    if label in ["NEGATIVE", "LABEL_0"]:
        return "negative"
    elif label in ["NEUTRAL", "LABEL_1"]:
        return "neutral"
    elif label in ["POSITIVE", "LABEL_2"]:
        return "positive"
    else:
        return label.lower()


def run_evaluation(sample_size=None):
    """Run the full evaluation."""
    classifier = load_model()
    if classifier is None:
        return

    df = load_test_data()

    # Optionally sample for faster testing
    if sample_size and sample_size < len(df):
        df = df.sample(n=sample_size, random_state=42)
        print(f"  Sampled {sample_size} rows for faster evaluation")

    print("\n" + "=" * 60)
    print("RUNNING SENTIMENT ANALYSIS EVALUATION")
    print(f"Testing on {len(df)} samples from FiQA-PhraseBank")
    print("=" * 60)

    y_true = []
    y_pred = []
    results = []

    total = len(df)
    for idx, (_, row) in enumerate(df.iterrows()):
        sentence = row["Sentence"]
        true_label = row["Sentiment"].lower()

        if (idx + 1) % 500 == 0:
            print(f"  Processing {idx + 1}/{total}...")

        try:
            # Run prediction (truncate to 512 chars for model)
            result = classifier(sentence[:512])[0]
            pred_label = map_model_output(result["label"])
            confidence = result["score"]

            y_true.append(true_label)
            y_pred.append(pred_label)

            results.append(
                {
                    "sentence": sentence[:60] + "..."
                    if len(sentence) > 60
                    else sentence,
                    "true_label": true_label,
                    "pred_label": pred_label,
                    "confidence": confidence,
                    "correct": true_label == pred_label,
                }
            )

        except Exception as e:
            print(f"Error processing: {sentence[:50]}... - {e}")

    # Calculate metrics
    accuracy = accuracy_score(y_true, y_pred)

    print("\n" + "=" * 60)
    print(f"OVERALL ACCURACY: {accuracy * 100:.2f}%")
    print("=" * 60)

    print("\n📊 Classification Report:")
    print(
        classification_report(
            y_true,
            y_pred,
            target_names=["negative", "neutral", "positive"],
            zero_division=0,
        )
    )

    print("\n📈 Confusion Matrix:")
    cm = confusion_matrix(y_true, y_pred, labels=["negative", "neutral", "positive"])
    print("                Predicted:")
    print("                neg    neu    pos")
    print(f"True negative  {cm[0][0]:4d}  {cm[0][1]:4d}  {cm[0][2]:4d}")
    print(f"True neutral   {cm[1][0]:4d}  {cm[1][1]:4d}  {cm[1][2]:4d}")
    print(f"True positive  {cm[2][0]:4d}  {cm[2][1]:4d}  {cm[2][2]:4d}")

    # Show some incorrect predictions
    incorrect = [r for r in results if not r["correct"]]
    if incorrect:
        print(f"\n❌ Sample Incorrect Predictions ({len(incorrect)}/{len(results)}):")
        print("-" * 80)
        for r in incorrect[:8]:  # Show first 8
            print(f"Sentence: {r['sentence']}")
            print(
                f"  True: {r['true_label']:8s} | Pred: {r['pred_label']:8s} (conf: {r['confidence']:.2f})"
            )
            print()

    # Show some correct predictions
    correct = [r for r in results if r["correct"]]
    if correct:
        print(f"\n✅ Sample Correct Predictions ({len(correct)}/{len(results)}):")
        print("-" * 80)
        for r in correct[:5]:  # Show first 5
            print(f"Sentence: {r['sentence']}")
            print(f"  Label: {r['true_label']:8s} (conf: {r['confidence']:.2f})")
            print()

    return accuracy, y_true, y_pred


if __name__ == "__main__":
    # Run on full dataset
    run_evaluation()
