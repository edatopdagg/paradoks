from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock


MAX_CONVERSATIONS = 256
MAX_TURNS_PER_CONVERSATION = 6


@dataclass(frozen=True)
class ConversationTurn:
    user_message: str
    assistant_message: str


_lock = RLock()

_conversations: OrderedDict[
    str,
    list[ConversationTurn],
] = OrderedDict()


def _clean(
    value: str,
) -> str:
    return (
        value
        or ""
    ).strip()


def get_recent_turns(
    conversation_id: str,
    *,
    limit: int = 2,
) -> list[ConversationTurn]:
    clean_id = _clean(
        conversation_id
    )

    if (
        not clean_id
        or limit <= 0
    ):
        return []

    with _lock:
        turns = _conversations.get(
            clean_id
        )

        if not turns:
            return []

        # Aktif konuşmayı LRU sonuna taşı.
        _conversations.move_to_end(
            clean_id
        )

        return list(
            turns[-limit:]
        )


def append_turn(
    conversation_id: str,
    *,
    user_message: str,
    assistant_message: str,
) -> None:
    clean_id = _clean(
        conversation_id
    )

    clean_user = _clean(
        user_message
    )

    clean_assistant = _clean(
        assistant_message
    )

    if (
        not clean_id
        or not clean_user
    ):
        return

    turn = ConversationTurn(
        user_message=clean_user,
        assistant_message=clean_assistant,
    )

    with _lock:
        turns = _conversations.setdefault(
            clean_id,
            [],
        )

        turns.append(
            turn
        )

        if (
            len(turns)
            > MAX_TURNS_PER_CONVERSATION
        ):
            del turns[
                :-MAX_TURNS_PER_CONVERSATION
            ]

        _conversations.move_to_end(
            clean_id
        )

        while (
            len(_conversations)
            > MAX_CONVERSATIONS
        ):
            _conversations.popitem(
                last=False
            )


def clear_conversation_memory(
    conversation_id: str | None = None,
) -> None:
    with _lock:
        if conversation_id is None:
            _conversations.clear()
            return

        clean_id = _clean(
            conversation_id
        )

        if clean_id:
            _conversations.pop(
                clean_id,
                None,
            )
