"""
Streamlined laughter detection inference wrapper.
Extracts minimal code from experiments/laughter-detection for production use.
"""
import numpy as np
import torch
import librosa
import scipy.signal as signal
from functools import partial


class LaughterDetector:
    """Laughter detection using pretrained ResNet model."""

    def __init__(self, model_path, device='cuda', threshold=0.5, min_length=0.2):
        """
        Args:
            model_path: Path to checkpoint file (best.pth.tar)
            device: 'cuda' or 'cpu'
            threshold: Probability threshold for laugh detection (0-1)
            min_length: Minimum laugh duration in seconds
        """
        self.device = device
        self.threshold = threshold
        self.min_length = min_length
        self.sample_rate = 8000

        # Load model
        from models import ResNetBigger

        # Model config from resnet_with_augmentation
        self.model = ResNetBigger(
            dropout_rate=0.0,  # No dropout at inference
            linear_layer_size=128,
            filter_sizes=[128, 64, 32, 32]
        )
        self.model.set_device(self.device)

        # Load checkpoint
        self._load_checkpoint(model_path)
        self.model.eval()

    def _load_checkpoint(self, checkpoint_path):
        """Load model weights from checkpoint."""
        map_location = torch.device(self.device)
        # PyTorch 2.6+ requires weights_only=False for older checkpoints
        # This checkpoint is from our trusted training (PyTorch 1.3.1)
        checkpoint = torch.load(checkpoint_path, map_location=map_location, weights_only=False)
        self.model.load_state_dict(checkpoint['state_dict'])

    def detect(self, audio_path):
        """
        Run inference on audio file.

        Args:
            audio_path: Path to audio file (mp3, wav, etc.)

        Returns:
            List of (start_time, end_time) tuples in seconds
        """
        # Load audio at 8kHz (model training sample rate)
        y, sr = librosa.load(audio_path, sr=self.sample_rate)

        # Extract mel-spectrogram features
        features = self._extract_features(y, sr)

        # Run inference
        probs = self._predict(features)

        # Calculate FPS (frames per second)
        file_length = len(y) / float(sr)
        fps = len(probs) / file_length

        # Smooth predictions
        probs = self._lowpass(probs)

        # Extract laugh instances
        instances = self._get_laughter_instances(probs, fps)

        return instances

    def _extract_features(self, y, sr):
        """
        Extract mel-spectrogram features from audio.
        Based on audio_utils.featurize_melspec with hop_length=186.
        """
        hop_length = 186

        # Compute mel-spectrogram
        S = librosa.feature.melspectrogram(y=y, sr=sr, hop_length=hop_length).T

        # Convert to dB scale
        S = librosa.amplitude_to_db(S, ref=np.max)

        return S

    def _predict(self, features):
        """
        Run model inference on features.

        Args:
            features: Array of shape (time_steps, n_mels)

        Returns:
            Array of probabilities for each time step
        """
        probs = []
        batch_size = 8

        # Process in batches
        num_batches = int(np.ceil(len(features) / batch_size))

        with torch.no_grad():
            for i in range(num_batches):
                start_idx = i * batch_size
                end_idx = min((i + 1) * batch_size, len(features))
                batch = features[start_idx:end_idx]

                # Add channel dimension and convert to tensor
                batch = np.expand_dims(batch, 1)  # (batch, 1, time, freq)
                x = torch.from_numpy(batch).float().to(self.device)

                # Run inference
                preds = self.model(x).cpu().detach().numpy().squeeze()

                # Handle single prediction case
                if len(preds.shape) == 0:
                    preds = [float(preds)]
                else:
                    preds = list(preds)

                probs.extend(preds)

        return np.array(probs)

    def _lowpass(self, sig, filter_order=2, cutoff=0.01):
        """
        Apply butterworth lowpass filter to smooth predictions.
        From laugh_segmenter.lowpass().
        """
        B, A = signal.butter(filter_order, cutoff, output='ba')
        return signal.filtfilt(B, A, sig)

    def _get_laughter_instances(self, probs, fps):
        """
        Convert probability array to laugh time segments.
        From laugh_segmenter.get_laughter_instances().

        Args:
            probs: Array of probabilities
            fps: Frames per second

        Returns:
            List of (start_time, end_time) tuples
        """
        instances = []
        current_list = []

        for i in range(len(probs)):
            if np.min(probs[i:i+1]) > self.threshold:
                current_list.append(i)
            else:
                if len(current_list) > 0:
                    instances.append(current_list)
                    current_list = []

        if len(current_list) > 0:
            instances.append(current_list)

        # Convert frame indices to time spans
        def collapse_to_start_and_end_frame(instance_list):
            return (instance_list[0], instance_list[-1])

        def frame_span_to_time_span(frame_span, fps):
            return (frame_span[0] / fps, frame_span[1] / fps)

        instances = [
            frame_span_to_time_span(collapse_to_start_and_end_frame(i), fps)
            for i in instances
        ]

        # Filter by minimum length
        instances = [inst for inst in instances if inst[1] - inst[0] > self.min_length]

        return instances
