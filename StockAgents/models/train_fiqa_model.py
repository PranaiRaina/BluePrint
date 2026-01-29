"""
Improved training script for sentiment analysis model using FiQA-PhraseBank dataset.
Includes optimizations for better accuracy:
- Learning rate scheduling with warmup
- More training epochs
- Class weighting for imbalanced data
- Proper train/val/test splits
"""
import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from transformers import (
    DistilBertTokenizerFast, 
    DistilBertForSequenceClassification, 
    Trainer, 
    TrainingArguments,
    EarlyStoppingCallback
)
from datasets import Dataset
import torch

# Paths
SCRIPT_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(SCRIPT_DIR, "training_data", "FiQA-PhraseBank.csv")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "sentiment_model_v2")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "training_results")

# Label mapping
LABEL_MAP = {'negative': 0, 'neutral': 1, 'positive': 2}
ID2LABEL = {0: 'NEGATIVE', 1: 'NEUTRAL', 2: 'POSITIVE'}
LABEL2ID = {'NEGATIVE': 0, 'NEUTRAL': 1, 'POSITIVE': 2}

def load_and_prepare_data():
    """Load and prepare the training data."""
    print(f"Loading data from: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    
    # Clean data
    df = df.dropna(subset=['Sentence', 'Sentiment'])
    df['Sentiment'] = df['Sentiment'].str.strip().str.lower()
    df = df[df['Sentiment'].isin(LABEL_MAP.keys())]
    
    # Rename columns to match expected format
    df = df.rename(columns={'Sentence': 'text', 'Sentiment': 'sentiment'})
    df['label'] = df['sentiment'].map(LABEL_MAP)
    
    print(f"✓ Loaded {len(df)} samples")
    print(f"  Distribution: {df['sentiment'].value_counts().to_dict()}")
    
    return df

def create_datasets(df, test_size=0.15, val_size=0.15):
    """Split into train/val/test sets."""
    # First split off test set
    train_val_df, test_df = train_test_split(
        df, test_size=test_size, random_state=42, stratify=df['label']
    )
    
    # Then split train/val
    val_ratio = val_size / (1 - test_size)
    train_df, val_df = train_test_split(
        train_val_df, test_size=val_ratio, random_state=42, stratify=train_val_df['label']
    )
    
    print(f"✓ Split sizes: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")
    
    return train_df, val_df, test_df

def compute_class_weights(train_df):
    """Compute class weights for imbalanced data."""
    labels = train_df['label'].values
    class_weights = compute_class_weight(
        class_weight='balanced',
        classes=np.unique(labels),
        y=labels
    )
    print(f"✓ Class weights: neg={class_weights[0]:.2f}, neu={class_weights[1]:.2f}, pos={class_weights[2]:.2f}")
    return torch.tensor(class_weights, dtype=torch.float)

class WeightedTrainer(Trainer):
    """Custom trainer with class weights for loss function."""
    def __init__(self, class_weights=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights
    
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        
        if self.class_weights is not None:
            loss_fct = torch.nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device))
        else:
            loss_fct = torch.nn.CrossEntropyLoss()
        
        loss = loss_fct(logits.view(-1, model.config.num_labels), labels.view(-1))
        return (loss, outputs) if return_outputs else loss

def train_model():
    """Main training function."""
    print("\n" + "="*60)
    print("SENTIMENT MODEL TRAINING - FiQA-PhraseBank")
    print("="*60 + "\n")
    
    # Load and prepare data
    df = load_and_prepare_data()
    train_df, val_df, test_df = create_datasets(df)
    
    # Compute class weights
    class_weights = compute_class_weights(train_df)
    
    # Convert to HuggingFace datasets
    train_dataset = Dataset.from_pandas(train_df[['text', 'label']])
    val_dataset = Dataset.from_pandas(val_df[['text', 'label']])
    test_dataset = Dataset.from_pandas(test_df[['text', 'label']])
    
    # Initialize tokenizer and model
    model_name = "distilbert-base-uncased"
    print(f"\nLoading base model: {model_name}")
    tokenizer = DistilBertTokenizerFast.from_pretrained(model_name)
    
    def tokenize_function(examples):
        return tokenizer(
            examples["text"], 
            padding="max_length", 
            truncation=True, 
            max_length=256  # Increased from 128 for longer sentences
        )
    
    print("Tokenizing datasets...")
    train_tokenized = train_dataset.map(tokenize_function, batched=True, remove_columns=['text'])
    val_tokenized = val_dataset.map(tokenize_function, batched=True, remove_columns=['text'])
    test_tokenized = test_dataset.map(tokenize_function, batched=True, remove_columns=['text'])
    
    # Set format for PyTorch
    train_tokenized.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])
    val_tokenized.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])
    test_tokenized.set_format('torch', columns=['input_ids', 'attention_mask', 'label'])
    
    # Load model with label mappings
    model = DistilBertForSequenceClassification.from_pretrained(
        model_name, 
        num_labels=3,
        id2label=ID2LABEL,
        label2id=LABEL2ID
    )
    
    # Training arguments - optimized for better accuracy
    training_args = TrainingArguments(
        output_dir=RESULTS_DIR,
        num_train_epochs=5,                    # More epochs
        per_device_train_batch_size=16,        # Larger batch size
        per_device_eval_batch_size=32,
        learning_rate=2e-5,                    # Standard for BERT fine-tuning
        warmup_ratio=0.1,                      # 10% warmup
        weight_decay=0.01,
        logging_dir=os.path.join(RESULTS_DIR, 'logs'),
        logging_steps=50,
        eval_strategy="steps",
        eval_steps=200,
        save_strategy="steps",
        save_steps=200,
        load_best_model_at_end=True,           # Load best checkpoint
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        save_total_limit=2,
        fp16=torch.cuda.is_available(),        # Use FP16 if GPU available
        report_to="none",                      # Disable wandb/tensorboard
    )
    
    # Compute metrics function
    from sklearn.metrics import accuracy_score, f1_score
    
    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)
        acc = accuracy_score(labels, predictions)
        f1 = f1_score(labels, predictions, average='weighted')
        return {'accuracy': acc, 'f1': f1}
    
    # Create trainer with class weights
    trainer = WeightedTrainer(
        class_weights=class_weights,
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=val_tokenized,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
    )
    
    # Train
    print("\n" + "="*60)
    print("STARTING TRAINING...")
    print("="*60 + "\n")
    
    trainer.train()
    
    # Evaluate on test set
    print("\n" + "="*60)
    print("EVALUATING ON TEST SET...")
    print("="*60 + "\n")
    
    test_results = trainer.evaluate(test_tokenized)
    print(f"Test Results:")
    print(f"  Accuracy: {test_results['eval_accuracy'] * 100:.2f}%")
    print(f"  F1 Score: {test_results['eval_f1'] * 100:.2f}%")
    print(f"  Loss: {test_results['eval_loss']:.4f}")
    
    # Save model
    print(f"\nSaving model to: {OUTPUT_DIR}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    print("\n" + "="*60)
    print("✓ TRAINING COMPLETE!")
    print("="*60)
    
    return test_results

if __name__ == "__main__":
    train_model()
