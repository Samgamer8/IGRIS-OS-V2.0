"""Sistema de aprendizaje continuo para IGRIS OS."""

from igris_os.learning.continuous_learner import ContinuousLearner
from igris_os.learning.skill_evolution import SkillEvolutionManager
from igris_os.learning.user_model import UserModel

__all__ = [
    "ContinuousLearner",
    "SkillEvolutionManager",
    "UserModel",
]
