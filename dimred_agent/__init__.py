"""Input inspection for a dimension-reduction agent."""

from .data import Dataset, InputError, load_dataset
from .profile import profile_dataset

__all__ = ["Dataset", "InputError", "load_dataset", "profile_dataset"]
