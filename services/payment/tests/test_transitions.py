from payment.model import Status

ALLOWED = [
    (Status.AUTHORIZED, Status.CAPTURED),
    (Status.AUTHORIZED, Status.REFUNDED),
    (Status.AUTHORIZED, Status.FAILED),
    (Status.CAPTURED, Status.REFUNDED),
]

FORBIDDEN = [
    (Status.REFUNDED, Status.CAPTURED),
    (Status.REFUNDED, Status.AUTHORIZED),
    (Status.FAILED, Status.CAPTURED),
    (Status.CAPTURED, Status.AUTHORIZED),
]


def test_transitions_allowed_exactly_as_described():
    for current, next_status in ALLOWED:
        assert current.can_move_to(next_status), f"переход {current} -> {next_status} должен быть разрешён"


def test_transitions_terminal_states_lead_nowhere():
    for current, next_status in FORBIDDEN:
        assert not current.can_move_to(next_status), (
            f"переход {current} -> {next_status} должен быть запрещён"
        )


def test_transitions_self_transition_is_not_a_transition():
    for status in Status:
        assert not status.can_move_to(status), (
            f"переход {status} -> {status} не переход: повтор обрабатывается выше, а не в автомате"
        )
