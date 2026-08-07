import math


class ConfidenceManager:
    def __init__(self, threshold=0.7):
        self.threshold = threshold

    def score(self, source, translated, back_similarity):
        # Simple heuristic combining length ratio and back-translation similarity.
        if not translated:
            return 0.0
        if not source:
            return 0.0
        length_ratio = min(len(translated), len(source)) / max(len(translated), len(source))
        confidence = 0.5 * back_similarity + 0.5 * length_ratio
        return round(min(max(confidence, 0.0), 1.0), 3)

    def is_confident(self, confidence):
        return confidence >= self.threshold
