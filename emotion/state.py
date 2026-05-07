from dataclasses import dataclass, field
from typing import List

@dataclass
class EmotionalState:
    valence: float = 0.0
    arousal: float = 0.0
    label: str = "neutra"
    history: List[dict] = field(default_factory=list)

    def update(self, delta_valence, delta_arousal, reason=""):
        self.history.append({
            "valence": self.valence,
            "arousal": self.arousal,
            "label": self.label,
            "reason": reason,
        })
        if len(self.history) > 20:
            self.history = self.history[-20:]
        self.valence = max(-1.0, min(1.0, self.valence + delta_valence))
        self.arousal = max(-1.0, min(1.0, self.arousal + delta_arousal))
        self.label = self._compute_label()

    def _compute_label(self):
        v = self.valence
        a = self.arousal
        if v > 0.4 and a > 0.4:
            return "euforica"
        elif v > 0.4 and a > 0.0:
            return "animada"
        elif v > 0.4 and a <= 0.0:
            return "serena"
        elif v > 0.1 and a <= -0.3:
            return "relaxada"
        elif -0.1 <= v <= 0.1 and -0.1 <= a <= 0.1:
            return "neutra"
        elif v < -0.4 and a > 0.4:
            return "raiva"
        elif v < -0.4 and a > 0.0:
            return "tensa"
        elif v < -0.4 and a <= 0.0:
            return "triste"
        elif v < -0.1 and a < -0.3:
            return "melancolica"
        elif v > 0.0 and a < -0.4:
            return "sonolenta"
        elif v < -0.2 and a > 0.2:
            return "irritada"
        elif v > 0.2 and a < 0.0:
            return "calma curiosa"
        elif v > 0.3 and a > 0.1:
            return "fofa"
        elif v < -0.3 and a > 0.3:
            return "chorando"
        else:
            return "neutra"

    def to_dict(self):
        return {
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "label": self.label,
        }

    def decay_toward_neutral(self, rate=0.05):
        self.valence *= (1 - rate)
        self.arousal *= (1 - rate)
        if abs(self.valence) < 0.02:
            self.valence = 0.0
        if abs(self.arousal) < 0.02:
            self.arousal = 0.0
        self.label = self._compute_label()
