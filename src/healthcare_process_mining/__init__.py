"""Healthcare process mining: reusable analysis code for the discharge capstone.

Modules, in pipeline order: ``data_loader`` -> ``data_validation`` ->
``data_preparation`` -> ``process_discovery`` / ``variant_analysis`` ->
``performance_analysis`` -> ``conformance_checking`` -> ``visualization`` /
``reporting``. ``pipeline.run_analysis`` runs them all.
"""

import os

# PM4Py prints tqdm progress bars during replay, which clutter notebooks and
# reports. It reads this variable when first imported. setdefault keeps any
# value the user has set themselves.
os.environ.setdefault("PM4PY_SHOW_PROGRESS_BAR", "False")
