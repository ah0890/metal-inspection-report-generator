"""Load and save the report defaults.

On first use, the defaults are taken from the most recent non-sample report
in the history, so the configuration of the inspector's last real report
becomes the starting point. After that they only change when the inspector
saves them on the Settings page — never silently.
"""

from __future__ import annotations

from database.database import ReportRepository
from models.defaults import ReportDefaults, defaults_from_report

SETTINGS_KEY = "report_defaults"


def load_defaults(repo: ReportRepository) -> ReportDefaults:
    stored = repo.get_setting(SETTINGS_KEY)
    if stored is not None:
        return ReportDefaults.from_dict(stored)

    latest = repo.latest(include_samples=False)
    defaults = defaults_from_report(latest) if latest else ReportDefaults()
    if latest:
        # Persist immediately so later reports cannot change the defaults implicitly.
        save_defaults(repo, defaults)
    return defaults


def save_defaults(repo: ReportRepository, defaults: ReportDefaults) -> None:
    repo.set_setting(SETTINGS_KEY, defaults.to_dict())
