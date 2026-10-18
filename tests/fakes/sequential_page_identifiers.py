from tests.fakes.document_drafts import page_identifier_at

FIRST_POSITION = 1


class SequentialPageIdentifiers:
    """Page identifier factory for DraftIdentitySource: "0000000000000001", "0000000000000002"...

    The identifiers are the ones of page_identifier_at, so a test names the n-th page that was added.
    """

    def __init__(self) -> None:
        self._next_position = FIRST_POSITION

    def __call__(self) -> str:
        page_identifier = page_identifier_at(self._next_position)
        self._next_position += 1
        return page_identifier
