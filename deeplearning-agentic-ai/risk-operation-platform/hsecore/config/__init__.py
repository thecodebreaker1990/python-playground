# HSE Config Module - Carga y gestión de configuración

from .loader import (
    load_matrix_config,
    get_escalation_matrix,
    get_remediation_tasks,
    get_label,
    get_tooltip,
    get_cell_tooltip,
    get_cell_action,
    set_language,
    get_current_language,
    get_all_labels_for_ui,
    validate_config,
    print_matrix_summary,
    SUPPORTED_LANGUAGES,
)

__all__ = [
    "load_matrix_config",
    "get_escalation_matrix",
    "get_remediation_tasks",
    "get_label",
    "get_tooltip",
    "get_cell_tooltip",
    "get_cell_action",
    "set_language",
    "get_current_language",
    "get_all_labels_for_ui",
    "validate_config",
    "print_matrix_summary",
    "SUPPORTED_LANGUAGES",
]
