"""Validated static/adaptive policy; no measurements imply performance claims."""
import os
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SchedulerSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    mode: Literal['static', 'adaptive'] = 'static'
    max_attempts: int = Field(default=3, ge=1, le=100)
    metrics_max_age: float = Field(default=8, gt=0)
    fairness_max_skips: int = Field(default=5, ge=1)
    history_min_samples: int = Field(default=3, ge=1)
    min_available_ram_mb: float = Field(default=128, ge=0)
    ram_target_mb: float = Field(default=1024, gt=0)
    cpu_weight: float = Field(default=.35, ge=0)
    ram_weight: float = Field(default=.20, ge=0)
    available_weight: float = Field(default=.15, ge=0)
    load_weight: float = Field(default=.15, ge=0)
    history_weight: float = Field(default=.15, ge=0)

    @model_validator(mode='after')
    def valid_weights(self):
        if sum(getattr(self, key) for key in type(self).model_fields if key.endswith('_weight')) <= 0:
            raise ValueError('At least one scheduling weight must be positive')
        return self

    @classmethod
    def from_environment(cls):
        names = {'mode':'SCHEDULER_MODE','max_attempts':'MAX_TASK_ATTEMPTS',
                 'metrics_max_age':'METRICS_MAX_AGE','fairness_max_skips':'FAIRNESS_MAX_SKIPS','history_min_samples':'HISTORY_MIN_SAMPLES',
                 'min_available_ram_mb':'MIN_AVAILABLE_RAM_MB','ram_target_mb':'RAM_TARGET_MB'}
        names.update({key:'SCHEDULER_'+key.upper() for key in cls.model_fields if key.endswith('_weight')})
        return cls(**{key:os.environ[name] for key,name in names.items() if name in os.environ})


def resource_score(worker, load: int, average_seconds: float | None, settings: SchedulerSettings) -> float:
    values = {'cpu_weight':1-worker.cpu_percent/100, 'ram_weight':1-worker.ram_percent/100,
              'available_weight':min(worker.available_ram_mb/settings.ram_target_mb,1),
              'load_weight':1/(1+load), 'history_weight':.5 if average_seconds is None else 1/(1+average_seconds)}
    total = sum(getattr(settings,key) for key in values)
    return sum(getattr(settings,key)*value for key,value in values.items())/total
