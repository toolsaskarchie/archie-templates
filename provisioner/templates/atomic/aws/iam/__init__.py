"""
AWS IAM Atomic Templates
"""
from .iam_role_atomic import IAMRoleAtomicTemplate
from .iam_instance_profile_atomic import IAMInstanceProfileAtomicTemplate

__all__ = ['IAMRoleAtomicTemplate', 'IAMInstanceProfileAtomicTemplate']
