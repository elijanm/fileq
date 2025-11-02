"""
MLflow + MinIO Integration Test Suite
Tests all functionality of MLflow with MinIO as artifact storage backend
"""

import mlflow
import mlflow.sklearn
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
import tempfile
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

MLFLOW_TRACKING_URI = "http://95.110.228.29:8813"
MINIO_ENDPOINT = "http://95.110.228.29:8811"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "e2l0+kTypkeJyLYkrfZ5o1WprOgzK26nmVTccP4GH20=" 

# Set environment variables for MinIO S3 integration
os.environ['AWS_ACCESS_KEY_ID'] = MINIO_ACCESS_import os
import json
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import mlflow
import mlflow.pytorch
from minio import Minio
from minio.error import S3Error
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import io
from datetime import datetime
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, confusion_matrix, classification_report
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'your_database',
    'user': 'your_user',
    'password': 'your_password'
}

MLFLOW_TRACKING_URI = "http://95.110.228.29:8813"
MINIO_ENDPOINT = "95.110.228.29:8811"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "your_secret_key"
MINIO_BUCKET = "corn-images"
ARTIFACTS_BUCKET = "mlflow-artifacts"

# Set MLflow tracking URI
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

# GPU Configuration
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")


class MinIOClient:
    """MinIO client for image storage and artifact management"""
    
    def __init__(self):
        self.client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False
        )
        self._ensure_buckets()
    
    def _ensure_buckets(self):
        """Create buckets if they don't exist"""
        for bucket in [MINIO_BUCKET, ARTIFACTS_BUCKET]:
            try:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
                    print(f"Created bucket: {bucket}")
            except S3Error as e:
                print(f"Error creating bucket {bucket}: {e}")
    
    def upload_file(self, file_path, object_name, bucket=ARTIFACTS_BUCKET):
        """Upload file to MinIO"""
        try:
            self.client.fput_object(bucket, object_name, file_path)
            url = f"http://{MINIO_ENDPOINT}/{bucket}/{object_name}"
            print(f"Uploaded: {object_name} -> {url}")
            return url
        except S3Error as e:
            print(f"Error uploading {file_path}: {e}")
            return None
    
    def upload_from_memory(self, data, object_name, length, content_type='application/octet-stream', bucket=ARTIFACTS_BUCKET):
        """Upload data from memory to MinIO"""
        try:
            self.client.put_object(
                bucket,
                object_name,
                data,
                length,
                content_type=content_type
            )
            url = f"http://{MINIO_ENDPOINT}/{bucket}/{object_name}"
            print(f"Uploaded: {object_name} -> {url}")
            return url
        except S3Error as e:
            print(f"Error uploading from memory: {e}")
            return None
    
    def upload_plot(self, fig, object_name, bucket=ARTIFACTS_BUCKET):
        """Upload matplotlib figure to MinIO"""
        try:
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            
            url = self.upload_from_memory(
                buf,
                object_name,
                buf.getbuffer().nbytes,
                content_type='image/png',
                bucket=bucket
            )
            buf.close()
            return url
        except Exception as e:
            print(f"Error uploading plot: {e}")
            return None


class DatabaseManager:
    """PostgreSQL database manager"""
    
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(**DB_CONFIG)
    
    def get_white_light_images(self, limit=None):
        """Fetch all WHITE light type images for training"""
        query = """
            SELECT 
                i.id,
                i.guid,
                i.sample_test_id,
                i.path,
                i.focus_exposure_metadata,
                i.sensor_details,
                i.image_quality_metadata,
                i.camera_properties,
                i.created_at,
                i.meta,
                i.cluster,
                ts.crop_type,
                ts.detected_crop,
                ts.prediction_data
            FROM images i
            JOIN test_samples ts ON i.sample_test_id = ts.id
            WHERE LOWER(i.light_type) = 'white'
        """
        if limit:
            query += f" LIMIT {limit}"
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()
    
    def update_image_cluster(self, image_id, cluster_id):
        """Update cluster assignment for image"""
        query = "UPDATE images SET cluster = %s WHERE id = %s"
        with self.conn.cursor() as cur:
            cur.execute(query, (cluster_id, image_id))
            self.conn.commit()
    
    def create_notification(self, image_id, message, notification_type='new_image'):
        """Create notification for manual labeling"""
        query = """
            INSERT INTO notifications (image_id, message, type, created_at, status)
            VALUES (%s, %s, %s, %s, 'pending')
            RETURNING id
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (image_id, message, notification_type, datetime.now()))
            self.conn.commit()
            return cur.fetchone()[0]
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


class CornImageDataset(Dataset):
    """Custom dataset for corn images from disk"""
    
    def __init__(self, image_records, transform=None):
        self.records = image_records
        self.transform = transform or self.default_transform()
    
    def default_transform(self):
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    def __len__(self):
        return len(self.records)
    
    def __getitem__(self, idx):
        record = self.records[idx]
        img_path = record['path']
        
        try:
            img = Image.open(img_path).convert('RGB')
        except Exception as e:
            print(f"Error loading image {img_path}: {e}")
            # Return black image if loading fails
            img = Image.new('RGB', (224, 224), color='black')
        
        if self.transform:
            img = self.transform(img)
        
        return img, record['id']


class ValidImageClassifier(nn.Module):
    """Binary classifier: Valid corn image vs Empty box"""
    
    def __init__(self, pretrained=True):
        super(ValidImageClassifier, self).__init__()
        # Use ResNet18 as backbone
        self.backbone = models.resnet18(pretrained=pretrained)
        num_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(num_features, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 2)  # Binary: valid vs empty
        )
    
    def forward(self, x):
        return self.backbone(x)


class FeatureExtractor(nn.Module):
    """Extract features for clustering"""
    
    def __init__(self, pretrained=True):
        super(FeatureExtractor, self).__init__()
        self.backbone = models.resnet18(pretrained=pretrained)
        self.backbone.fc = nn.Identity()  # Remove final layer
    
    def forward(self, x):
        return self.backbone(x)


class CornPurityPipeline:
    """Main pipeline for corn image purity detection"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.minio = MinIOClient()
        self.device = device
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def create_visualization(self, data, plot_type, title, **kwargs):
        """Create and upload visualization to MinIO"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if plot_type == 'loss':
            ax.plot(data['epochs'], data['train_loss'], label='Train Loss', marker='o')
            ax.plot(data['epochs'], data['val_loss'], label='Val Loss', marker='s')
            ax.set_xlabel('Epoch')
            ax.set_ylabel('Loss')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
        elif plot_type == 'accuracy':
            ax.plot(data['epochs'], data['train_acc'], label='Train Accuracy', marker='o')
            ax.plot(data['epochs'], data['val_acc'], label='Val Accuracy', marker='s')
            ax.set_xlabel('Epoch')
            ax.set_ylabel('Accuracy (%)')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
        elif plot_type == 'confusion_matrix':
            sns.heatmap(data['cm'], annot=True, fmt='d', cmap='Blues', ax=ax)
            ax.set_xlabel('Predicted')
            ax.set_ylabel('Actual')
            
        elif plot_type == 'cluster_distribution':
            ax.bar(range(len(data['counts'])), data['counts'])
            ax.set_xlabel('Cluster ID')
            ax.set_ylabel('Number of Images')
            ax.grid(True, alpha=0.3)
            
        elif plot_type == 'silhouette':
            ax.plot(data['k_values'], data['scores'], marker='o')
            ax.set_xlabel('Number of Clusters (k)')
            ax.set_ylabel('Silhouette Score')
            ax.axvline(data['best_k'], color='r', linestyle='--', label=f'Best k={data["best_k"]}')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        ax.set_title(title)
        plt.tight_layout()
        
        # Upload to MinIO
        object_name = f"experiments/{self.run_id}/{plot_type}_{self.run_id}.png"
        url = self.minio.upload_plot(fig, object_name)
        plt.close(fig)
        
        return url
    
    def extract_features(self, images, batch_size=32):
        """Extract features from images for clustering"""
        print(f"Extracting features from {len(images)} images...")
        feature_extractor = FeatureExtractor().to(self.device)
        feature_extractor.eval()
        
        dataset = CornImageDataset(images)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=4)
        
        features = []
        image_ids = []
        
        with torch.no_grad():
            for batch_idx, (imgs, ids) in enumerate(dataloader):
                imgs = imgs.to(self.device)
                feats = feature_extractor(imgs)
                features.append(feats.cpu().numpy())
                image_ids.extend(ids)
                
                if (batch_idx + 1) % 10 == 0:
                    print(f"Processed {(batch_idx + 1) * batch_size}/{len(images)} images")
        
        return np.vstack(features), image_ids
    
    def perform_clustering(self, features, k_range=(3, 10)):
        """Perform K-means clustering with optimal k selection"""
        print(f"\nTesting clustering with k from {k_range[0]} to {k_range[1]}...")
        
        k_values = []
        silhouette_scores = []
        best_score = -1
        best_k = k_range[0]
        best_model = None
        best_labels = None
        
        for k in range(k_range[0], k_range[1] + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(features)
            score = silhouette_score(features, labels)
            
            k_values.append(k)
            silhouette_scores.append(score)
            
            print(f"k={k}: silhouette_score={score:.4f}")
            
            if score > best_score:
                best_score = score
                best_k = k
                best_model = kmeans
                best_labels = labels
        
        # Create silhouette plot
        silhouette_url = self.create_visualization(
            {'k_values': k_values, 'scores': silhouette_scores, 'best_k': best_k},
            'silhouette',
            'Silhouette Score vs Number of Clusters'
        )
        
        # Create cluster distribution plot
        unique, counts = np.unique(best_labels, return_counts=True)
        dist_url = self.create_visualization(
            {'counts': counts},
            'cluster_distribution',
            f'Cluster Distribution (k={best_k})'
        )
        
        return {
            'model': best_model,
            'labels': best_labels,
            'k': best_k,
            'silhouette_score': best_score,
            'silhouette_plot_url': silhouette_url,
            'distribution_plot_url': dist_url,
            'all_scores': dict(zip(k_values, silhouette_scores))
        }
    
    def train_valid_image_classifier(self, train_loader, val_loader, epochs=20):
        """Train binary classifier for valid image detection"""
        
        experiment_name = f"valid_image_classifier_{self.run_id}"
        
        with mlflow.start_run(run_name=experiment_name):
            model = ValidImageClassifier().to(self.device)
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
            scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=3)
            
            # Log parameters
            mlflow.log_param("model_type", "ResNet18_Binary")
            mlflow.log_param("epochs", epochs)
            mlflow.log_param("optimizer", "Adam")
            mlflow.log_param("initial_lr", 0.001)
            mlflow.log_param("device", str(self.device))
            mlflow.log_param("batch_size", train_loader.batch_size)
            
            # Training history
            history = {
                'epochs': [],
                'train_loss': [],
                'val_loss': [],
                'train_acc': [],
                'val_acc': []
            }
            
            best_val_acc = 0.0
            best_model_state = None
            
            for epoch in range(epochs):
                # Training
                model.train()
                train_loss = 0.0
                train_correct = 0
                train_total = 0
                
                for imgs, labels in train_loader:
                    imgs, labels = imgs.to(self.device), labels.to(self.device)
                    
                    optimizer.zero_grad()
                    outputs = model(imgs)
                    loss = criterion(outputs, labels)
                    loss.backward()
                    optimizer.step()
                    
                    train_loss += loss.item()
                    _, predicted = outputs.max(1)
                    train_total += labels.size(0)
                    train_correct += predicted.eq(labels).sum().item()
                
                avg_train_loss = train_loss / len(train_loader)
                train_acc = 100.0 * train_correct / train_total
                
                # Validation
                model.eval()
                val_loss = 0.0
                val_correct = 0
                val_total = 0
                all_preds = []
                all_labels = []
                
                with torch.no_grad():
                    for imgs, labels in val_loader:
                        imgs, labels = imgs.to(self.device), labels.to(self.device)
                        outputs = model(imgs)
                        loss = criterion(outputs, labels)
                        
                        val_loss += loss.item()
                        _, predicted = outputs.max(1)
                        val_total += labels.size(0)
                        val_correct += predicted.eq(labels).sum().item()
                        
                        all_preds.extend(predicted.cpu().numpy())
                        all_labels.extend(labels.cpu().numpy())
                
                avg_val_loss = val_loss / len(val_loader)
                val_acc = 100.0 * val_correct / val_total
                
                # Learning rate scheduling
                scheduler.step(avg_val_loss)
                
                # Store history
                history['epochs'].append(epoch + 1)
                history['train_loss'].append(avg_train_loss)
                history['val_loss'].append(avg_val_loss)
                history['train_acc'].append(train_acc)
                history['val_acc'].append(val_acc)
                
                # Log metrics
                mlflow.log_metric("train_loss", avg_train_loss, step=epoch)
                mlflow.log_metric("train_accuracy", train_acc, step=epoch)
                mlflow.log_metric("val_loss", avg_val_loss, step=epoch)
                mlflow.log_metric("val_accuracy", val_acc, step=epoch)
                mlflow.log_metric("learning_rate", optimizer.param_groups[0]['lr'], step=epoch)
                
                print(f"Epoch {epoch+1}/{epochs} - "
                      f"Train Loss: {avg_train_loss:.4f}, Train Acc: {train_acc:.2f}% | "
                      f"Val Loss: {avg_val_loss:.4f}, Val Acc: {val_acc:.2f}%")
                
                if val_acc > best_val_acc:
                    best_val_acc = val_acc
                    best_model_state = model.state_dict().copy()
            
            # Create and upload training plots
            loss_url = self.create_visualization(history, 'loss', 'Training and Validation Loss')
            acc_url = self.create_visualization(history, 'accuracy', 'Training and Validation Accuracy')
            
            mlflow.log_param("loss_plot_url", loss_url)
            mlflow.log_param("accuracy_plot_url", acc_url)
            
            # Create confusion matrix for best model
            model.load_state_dict(best_model_state)
            cm = confusion_matrix(all_labels, all_preds)
            cm_url = self.create_visualization(
                {'cm': cm},
                'confusion_matrix',
                f'Confusion Matrix (Val Acc: {best_val_acc:.2f}%)'
            )
            mlflow.log_param("confusion_matrix_url", cm_url)
            
            # Save classification report
            report = classification_report(all_labels, all_preds, 
                                          target_names=['Empty', 'Valid Corn'])
            report_path = f"/tmp/classification_report_{self.run_id}.txt"
            with open(report_path, 'w') as f:
                f.write(report)
            
            report_url = self.minio.upload_file(
                report_path,
                f"experiments/{self.run_id}/classification_report.txt"
            )
            mlflow.log_param("classification_report_url", report_url)
            
            # Log best model
            mlflow.log_metric("best_val_accuracy", best_val_acc)
            mlflow.pytorch.log_model(model, "model")
            
            # Save model checkpoint to MinIO
            model_path = f"/tmp/best_model_{self.run_id}.pth"
            torch.save(best_model_state, model_path)
            model_url = self.minio.upload_file(
                model_path,
                f"models/classifier_{self.run_id}.pth"
            )
            mlflow.log_param("model_checkpoint_url", model_url)
            
            print(f"\n✓ Training completed! Best Val Accuracy: {best_val_acc:.2f}%")
            print(f"  Loss Plot: {loss_url}")
            print(f"  Accuracy Plot: {acc_url}")
            print(f"  Confusion Matrix: {cm_url}")
            print(f"  Model Checkpoint: {model_url}")
            
            return model, history
    
    def detect_new_images(self, current_images, cluster_model, threshold=0.3):
        """Detect images that don't fit existing clusters"""
        print(f"\nDetecting new/unknown image patterns (threshold={threshold})...")
        features, image_ids = self.extract_features(current_images)
        
        # Get distances to nearest cluster centers
        distances = cluster_model.transform(features)
        min_distances = distances.min(axis=1)
        
        # Images with distance > threshold are considered new/unknown
        new_image_indices = np.where(min_distances > threshold)[0]
        
        notifications_created = 0
        for idx in new_image_indices:
            image_id = image_ids[idx]
            distance = min_distances[idx]
            
            notification_id = self.db.create_notification(
                image_id,
                f"New/unknown image pattern detected. Distance to nearest cluster: {distance:.4f}. "
                f"Please provide manual labeling or request additional training images.",
                notification_type='new_pattern'
            )
            notifications_created += 1
            
            print(f"  Image ID {image_id}: distance={distance:.4f} -> Notification #{notification_id}")
        
        return new_image_indices, image_ids, min_distances
    
    def run_full_pipeline(self):
        """Execute the complete training pipeline"""
        
        print("="*70)
        print("  CORN PURITY DETECTION PIPELINE")
        print("="*70)
        print(f"Run ID: {self.run_id}")
        print(f"Device: {self.device}")
        print(f"MLflow: {MLFLOW_TRACKING_URI}")
        print(f"MinIO: http://{MINIO_ENDPOINT}")
        print("="*70)
        
        # Step 1: Fetch WHITE light images
        print("\n[1/5] Fetching WHITE light images from database...")
        images = self.db.get_white_light_images()
        print(f"✓ Found {len(images)} WHITE light images")
        
        if len(images) == 0:
            print("✗ No images found. Exiting.")
            return None
        
        # Step 2: Extract features and perform clustering
        print("\n[2/5] Extracting features and performing clustering...")
        
        with mlflow.start_run(run_name=f"clustering_analysis_{self.run_id}"):
            features, image_ids = self.extract_features(images)
            mlflow.log_param("total_images", len(images))
            mlflow.log_param("feature_dim", features.shape[1])
            
            clustering_results = self.perform_clustering(features)
            
            # Log clustering results
            mlflow.log_param("best_n_clusters", clustering_results['k'])
            mlflow.log_metric("best_silhouette_score", clustering_results['silhouette_score'])
            mlflow.log_param("silhouette_plot", clustering_results['silhouette_plot_url'])
            mlflow.log_param("distribution_plot", clustering_results['distribution_plot_url'])
            
            for k, score in clustering_results['all_scores'].items():
                mlflow.log_metric(f"silhouette_k{k}", score)
            
            print(f"✓ Best clustering: k={clustering_results['k']} "
                  f"(silhouette={clustering_results['silhouette_score']:.4f})")
            print(f"  Silhouette plot: {clustering_results['silhouette_plot_url']}")
            print(f"  Distribution plot: {clustering_results['distribution_plot_url']}")
            
            # Update database with cluster assignments
            print("\n[3/5] Updating cluster assignments in database...")
            for img_id, cluster_id in zip(image_ids, clustering_results['labels']):
                self.db.update_image_cluster(img_id, int(cluster_id))
            print(f"✓ Updated {len(image_ids)} cluster assignments")
        
        # Step 3: Detect new/unknown images
        print("\n[4/5] Detecting new/unknown image patterns...")
        new_indices, all_ids, distances = self.detect_new_images(
            images, 
            clustering_results['model'],
            threshold=0.3
        )
        print(f"✓ Detected {len(new_indices)} images requiring manual review")
        
        # Step 4: Summary
        print("\n[5/5] Pipeline Summary")
        print("-" * 70)
        
        results = {
            'run_id': self.run_id,
            'total_images': len(images),
            'n_clusters': clustering_results['k'],
            'silhouette_score': clustering_results['silhouette_score'],
            'new_images_detected': len(new_indices),
            'silhouette_plot_url': clustering_results['silhouette_plot_url'],
            'distribution_plot_url': clustering_results['distribution_plot_url'],
            'mlflow_uri': MLFLOW_TRACKING_URI,
            'minio_uri': f"http://{MINIO_ENDPOINT}"
        }
        
        # Save summary to MinIO
        summary_path = f"/tmp/pipeline_summary_{self.run_id}.json"
        with open(summary_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        summary_url = self.minio.upload_file(
            summary_path,
            f"experiments/{self.run_id}/summary.json"
        )
        results['summary_url'] = summary_url
        
        print(f"Total Images Processed: {results['total_images']}")
        print(f"Optimal Clusters: {results['n_clusters']}")
        print(f"Silhouette Score: {results['silhouette_score']:.4f}")
        print(f"New Images Detected: {results['new_images_detected']}")
        print(f"\nArtifacts:")
        print(f"  Summary: {summary_url}")
        print(f"  View all experiments: {MLFLOW_TRACKING_URI}")
        print("-" * 70)
        
        print("\n" + "="*70)
        print("NOTE: Valid image classifier requires labeled data")
        print("Call train_valid_image_classifier() with labeled train/val loaders")
        print("="*70)
        
        return results
    
    def cleanup(self):
        """Clean up resources"""
        self.db.close()
        print("\n✓ Resources cleaned up")


if __name__ == "__main__":
    # Initialize and run pipeline
    pipeline = CornPurityPipeline()
    
    try:
        results = pipeline.run_full_pipeline()
        
        if results:
            print("\n" + "="*70)
            print("PIPELINE COMPLETED SUCCESSFULLY")
            print("="*70)
            print(json.dumps(results, indent=2))
            print("="*70)
            
    except Exception as e:
        print(f"\n✗ Pipeline failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        pipeline.cleanup()KEY
os.environ['AWS_SECRET_ACCESS_KEY'] = MINIO_SECRET_KEY
os.environ['MLFLOW_S3_ENDPOINT_URL'] = MINIO_ENDPOINT
os.environ['MLFLOW_S3_IGNORE_TLS'] = 'true'

# Set MLflow tracking URI
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

# ============================================================================
# TEST SUITE
# ============================================================================

def print_header(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def print_test_header(test_num, test_name):
    """Print formatted test header"""
    print("\n" + "-" * 80)
    print(f"Test {test_num}: {test_name}")
    print("-" * 80)

def test_1_connection():
    """Test MLflow server connection and experiment setup"""
    print_test_header(1, "MLflow Server Connection")
    
    try:
        # Create or get experiment
        experiment_name = "minio-integration-test"
        experiment = mlflow.get_experiment_by_name(experiment_name)
        
        if experiment is None:
            experiment_id = mlflow.create_experiment(experiment_name)
            print(f"✓ Created new experiment: '{experiment_name}'")
        else:
            experiment_id = experiment.experiment_id
            print(f"✓ Found existing experiment: '{experiment_name}'")
        
        mlflow.set_experiment(experiment_name)
        
        print(f"  Experiment ID: {experiment_id}")
        print(f"  MLflow Version: {mlflow.__version__}")
        print(f"  Tracking URI: {MLFLOW_TRACKING_URI}")
        
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_2_parameters():
    """Test parameter logging"""
    print_test_header(2, "Parameter Logging")
    
    try:
        with mlflow.start_run(run_name="test_parameters") as run:
            # Log various parameter types
            mlflow.log_param("model_type", "random_forest")
            mlflow.log_param("n_estimators", 100)
            mlflow.log_param("max_depth", 10)
            mlflow.log_param("learning_rate", 0.01)
            mlflow.log_param("random_state", 42)
            
            print(f"✓ Logged 5 parameters")
            print(f"  Run ID: {run.info.run_id}")
            
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_3_metrics():
    """Test metric logging (single and time-series)"""
    print_test_header(3, "Metric Logging")
    
    try:
        with mlflow.start_run(run_name="test_metrics") as run:
            # Log single metrics
            mlflow.log_metric("accuracy", 0.95)
            mlflow.log_metric("precision", 0.94)
            mlflow.log_metric("recall", 0.96)
            mlflow.log_metric("f1_score", 0.95)
            
            # Log time-series metrics (simulating training epochs)
            for epoch in range(10):
                mlflow.log_metric("train_loss", 1.0 / (epoch + 1), step=epoch)
                mlflow.log_metric("val_loss", 1.2 / (epoch + 1), step=epoch)
                mlflow.log_metric("train_acc", 0.5 + (0.4 * epoch / 10), step=epoch)
            
            print(f"✓ Logged 4 single metrics")
            print(f"✓ Logged 3 time-series metrics (10 steps each)")
            print(f"  Run ID: {run.info.run_id}")
            
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_4_artifacts():
    """Test artifact logging to MinIO"""
    print_test_header(4, "Artifact Upload to MinIO")
    
    try:
        with mlflow.start_run(run_name="test_artifacts") as run:
            with tempfile.TemporaryDirectory() as tmp_dir:
                
                # 1. Text file
                text_file = os.path.join(tmp_dir, "model_info.txt")
                with open(text_file, 'w') as f:
                    f.write(f"Test run at: {datetime.now()}\n")
                    f.write("Model: Random Forest\n")
                    f.write("Status: Training complete\n")
                mlflow.log_artifact(text_file)
                print("  ✓ Text file")
                
                # 2. JSON configuration
                json_file = os.path.join(tmp_dir, "config.json")
                config = {
                    "model": "random_forest",
                    "hyperparameters": {
                        "n_estimators": 100,
                        "max_depth": 10,
                        "min_samples_split": 2
                    },
                    "timestamp": datetime.now().isoformat()
                }
                with open(json_file, 'w') as f:
                    json.dump(config, f, indent=2)
                mlflow.log_artifact(json_file)
                print("  ✓ JSON config")
                
                # 3. CSV data
                csv_file = os.path.join(tmp_dir, "metrics.csv")
                df = pd.DataFrame({
                    'epoch': range(10),
                    'train_loss': np.random.uniform(0.1, 0.5, 10),
                    'val_loss': np.random.uniform(0.15, 0.6, 10)
                })
                df.to_csv(csv_file, index=False)
                mlflow.log_artifact(csv_file)
                print("  ✓ CSV file")
                
                # 4. NumPy array
                npy_file = os.path.join(tmp_dir, "predictions.npy")
                predictions = np.random.random((100, 10))
                np.save(npy_file, predictions)
                mlflow.log_artifact(npy_file)
                print("  ✓ NumPy array")
                
                # 5. Multiple files in directory
                subdir = os.path.join(tmp_dir, "model_weights")
                os.makedirs(subdir)
                for i in range(3):
                    weight_file = os.path.join(subdir, f"layer_{i}.npy")
                    np.save(weight_file, np.random.random((10, 10)))
                mlflow.log_artifacts(subdir, artifact_path="weights")
                print("  ✓ Directory with 3 files")
            
            print(f"\n✓ Uploaded 5 different artifact types to MinIO")
            print(f"  Run ID: {run.info.run_id}")
            print(f"  Artifact URI: {mlflow.get_artifact_uri()}")
            
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_5_download_artifacts():
    """Test downloading artifacts from MinIO"""
    print_test_header(5, "Artifact Download from MinIO")
    
    try:
        # Get the most recent run
        experiment = mlflow.get_experiment_by_name("minio-integration-test")
        runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string="tags.mlflow.runName = 'test_artifacts'",
            max_results=1
        )
        
        if len(runs) == 0:
            print("  ⚠ No artifact runs found, skipping")
            return True
        
        run_id = runs.iloc[0]['run_id']
        client = mlflow.tracking.MlflowClient()
        
        # List artifacts
        artifacts = client.list_artifacts(run_id)
        print(f"  Found {len(artifacts)} artifact(s)")
        
        # Download each artifact
        with tempfile.TemporaryDirectory() as tmp_dir:
            for artifact in artifacts:
                local_path = client.download_artifacts(run_id, artifact.path, dst_path=tmp_dir)
                if os.path.isfile(local_path):
                    size = os.path.getsize(local_path)
                    print(f"  ✓ {artifact.path} ({size:,} bytes)")
                else:
                    print(f"  ✓ {artifact.path} (directory)")
        
        print(f"\n✓ Successfully downloaded all artifacts from MinIO")
        return True
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_6_large_file():
    """Test large file upload (50MB)"""
    print_test_header(6, "Large File Upload (50MB)")
    
    try:
        with mlflow.start_run(run_name="test_large_file") as run:
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Create 50MB file
                large_file = os.path.join(tmp_dir, "large_model.bin")
                size_mb = 50
                
                print(f"  Creating {size_mb}MB file...")
                with open(large_file, 'wb') as f:
                    f.write(b'X' * (size_mb * 1024 * 1024))
                
                print(f"  Uploading to MinIO...")
                start_time = time.time()
                mlflow.log_artifact(large_file)
                upload_time = time.time() - start_time
                
                speed_mbps = size_mb / upload_time
                print(f"\n✓ Uploaded {size_mb}MB in {upload_time:.2f} seconds")
                print(f"  Upload speed: {speed_mbps:.2f} MB/s")
                print(f"  Run ID: {run.info.run_id}")
            
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_7_ml_model():
    """Test ML model logging with signature"""
    print_test_header(7, "ML Model Logging (with signature)")
    
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.datasets import make_classification
        from mlflow.models import infer_signature
        
        # Generate dataset
        X, y = make_classification(
            n_samples=100,
            n_features=4,
            n_classes=2,
            random_state=42
        )
        
        with mlflow.start_run(run_name="test_ml_model") as run:
            # Train model
            model = RandomForestClassifier(n_estimators=10, random_state=42)
            model.fit(X, y)
            
            # Calculate metrics
            train_accuracy = model.score(X, y)
            mlflow.log_metric("train_accuracy", train_accuracy)
            
            # Create signature and input example
            predictions = model.predict(X[:5])
            signature = infer_signature(X, predictions)
            input_example = X[:1]
            
            # Log model with complete metadata
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path="random_forest_model",
                signature=signature,
                input_example=input_example
            )
            
            # Log feature importances
            importance_df = pd.DataFrame({
                'feature': [f'feature_{i}' for i in range(4)],
                'importance': model.feature_importances_
            })
            with tempfile.TemporaryDirectory() as tmp_dir:
                csv_path = os.path.join(tmp_dir, "feature_importance.csv")
                importance_df.to_csv(csv_path, index=False)
                mlflow.log_artifact(csv_path)
            
            print(f"  ✓ Model trained (accuracy: {train_accuracy:.4f})")
            print(f"  ✓ Model logged with signature")
            print(f"  ✓ Input example included")
            print(f"  ✓ Feature importances saved")
            print(f"\n✓ Complete model package uploaded to MinIO")
            print(f"  Run ID: {run.info.run_id}")
            print(f"  Model URI: runs:/{run.info.run_id}/random_forest_model")
            
        return True
        
    except ImportError:
        print("  ⚠ Skipped (scikit-learn not installed)")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_8_search_runs():
    """Test run search and filtering"""
    print_test_header(8, "Run Search & Filtering")
    
    try:
        experiment = mlflow.get_experiment_by_name("minio-integration-test")
        
        # Search all runs
        all_runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id])
        print(f"  ✓ Total runs: {len(all_runs)}")
        
        # Filter by metric
        high_accuracy_runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string="metrics.accuracy > 0.9"
        )
        print(f"  ✓ Runs with accuracy > 0.9: {len(high_accuracy_runs)}")
        
        # Show recent runs
        if len(all_runs) > 0:
            print(f"\n  Recent runs:")
            for idx, run in all_runs.head(5).iterrows():
                run_name = run.get('tags.mlflow.runName', 'unnamed')
                run_id = run['run_id'][:8]
                print(f"    - {run_name} ({run_id}...)")
        
        print(f"\n✓ Search functionality working")
        return True
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_9_tags():
    """Test adding custom tags"""
    print_test_header(9, "Custom Tags")
    
    try:
        with mlflow.start_run(run_name="test_tags") as run:
            # Set various tags
            mlflow.set_tag("team", "ml-engineering")
            mlflow.set_tag("project", "minio-integration")
            mlflow.set_tag("environment", "production")
            mlflow.set_tag("version", "1.0.0")
            
            print(f"✓ Added 4 custom tags")
            print(f"  Run ID: {run.info.run_id}")
            
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_10_nested_runs():
    """Test nested runs (parent-child relationship)"""
    print_test_header(10, "Nested Runs")
    
    try:
        with mlflow.start_run(run_name="parent_run") as parent_run:
            mlflow.log_param("experiment_type", "hyperparameter_tuning")
            
            # Create 3 child runs
            for i in range(3):
                with mlflow.start_run(run_name=f"child_run_{i}", nested=True) as child_run:
                    mlflow.log_param("iteration", i)
                    mlflow.log_metric("score", 0.8 + (i * 0.05))
            
            print(f"✓ Created parent run with 3 child runs")
            print(f"  Parent Run ID: {parent_run.info.run_id}")
            
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Execute all tests and generate summary"""
    
    print_header("MLflow + MinIO Integration Test Suite")
    print(f"MLflow URI: {MLFLOW_TRACKING_URI}")
    print(f"MinIO Endpoint: {MINIO_ENDPOINT}")
    print(f"MLflow Version: {mlflow.__version__}")
    
    tests = [
        ("Server Connection", test_1_connection),
        ("Parameter Logging", test_2_parameters),
        ("Metric Logging", test_3_metrics),
        ("Artifact Upload", test_4_artifacts),
        ("Artifact Download", test_5_download_artifacts),
        ("Large File Upload", test_6_large_file),
        ("ML Model Logging", test_7_ml_model),
        ("Run Search", test_8_search_runs),
        ("Custom Tags", test_9_tags),
        ("Nested Runs", test_10_nested_runs),
    ]
    
    results = []
    start_time = time.time()
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n✗ Test crashed: {e}")
            results.append((test_name, False))
    
    total_time = time.time() - start_time
    
    # Print summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status:8} {test_name}")
    
    print("\n" + "=" * 80)
    print(f"Results: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    print(f"Duration: {total_time:.2f} seconds")
    print("=" * 80)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print(f"\n✓ MLflow UI: {MLFLOW_TRACKING_URI}")
        print(f"✓ MinIO Console: http://95.110.228.29:8812")
        print("\nYour MLflow + MinIO integration is fully functional!")
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        print("Check the output above for details")
    
    print("=" * 80)

if __name__ == "__main__":
    run_all_tests()