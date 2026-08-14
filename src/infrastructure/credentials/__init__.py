"""Credential resolvers that keep raw credential values inside infrastructure boundaries."""

from .regional_secret_manager import RegionalSecretManagerResolver

__all__ = ["RegionalSecretManagerResolver"]
