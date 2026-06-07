from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class AppPhase(Enum):
    INIT              = auto()
    LOADING_JOB       = auto()
    BROWSER_LAUNCH    = auto()
    NAVIGATING        = auto()
    FINDING_BUTTON    = auto()
    MODAL_OPEN        = auto()
    OBSERVING         = auto()
    THINKING          = auto()
    FILLING           = auto()
    VERIFYING         = auto()
    ADVANCING         = auto()
    REVIEWING         = auto()   # ← SubmitGuard checks for this phase
    SUBMITTING        = auto()
    SUCCESS           = auto()
    BLOCKED           = auto()
    PARTIAL           = auto()
    TERMINAL_ERROR    = auto()


@dataclass
class StepRecord:
    step_num:          int
    html_length:       int       = 0
    fields_attempted:  int       = 0
    fields_filled:     int       = 0
    llm_called:        bool      = False
    input_tokens:      int       = 0    # Populated by LangSmith callback
    output_tokens:     int       = 0    # Populated by LangSmith callback
    duration_ms:       int       = 0
    tool_calls_raw:    list      = field(default_factory=list)
    tool_calls_valid:  list      = field(default_factory=list)
    hallucinations_blocked: int  = 0
    retry_count:       int       = 0
    force_advanced:    bool      = False


@dataclass
class ApplicationState:
    job_id:              int
    user_id:             int
    phase:               AppPhase = AppPhase.INIT
    step_num:            int      = 0
    step_history:        list[StepRecord] = field(default_factory=list)
    retry_count:         int      = 0
    total_llm_calls:     int      = 0
    total_fields_filled: int      = 0
    last_html_hash:      str      = ""
    blocked_reason:      Optional[str] = None
    error_message:       Optional[str] = None

    def begin_step(self, step_num: int) -> StepRecord:
        self.step_num = step_num
        self.retry_count = 0
        record = StepRecord(step_num=step_num)
        self.step_history.append(record)
        return record

    def current_record(self) -> StepRecord:
        return self.step_history[-1]

    def snapshot(self) -> dict:
        return {
            "job_id":          self.job_id,
            "step_num":        self.step_num,
            "total_llm_calls": self.total_llm_calls,
            "total_fields":    self.total_fields_filled,
            "phase":           self.phase.name,
        }
