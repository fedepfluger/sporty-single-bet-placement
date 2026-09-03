"""App Actions for the failure modal (Feature Specification 2.5).

`Rebet` and `Close` have deliberately different semantics - one retries, the
other discards the selection and stake - so they are separate methods here
rather than one `dismiss()`.
"""

from __future__ import annotations

from tests.app_actions.ui.base_actions import BaseActions
from tests.app_actions.ui.locators import ErrorModalLocators


class ErrorModalActions(BaseActions):
    def is_visible(self) -> bool:
        return self.is_present(ErrorModalLocators.MODAL)

    def title(self) -> str:
        modal = self.wait_for_visible(ErrorModalLocators.MODAL)
        return self.text_of(ErrorModalLocators.TITLE, context=modal) or modal.text
