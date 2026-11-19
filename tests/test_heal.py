from dnsops.heal import heal


def test_healthy_server_is_left_alone():
    restarted = []
    assert heal(lambda: True, lambda: restarted.append(1), sleep=lambda s: None) == "healthy"
    assert restarted == []


def test_recovers_without_restart_when_it_comes_back():
    answers = iter([False, True])
    assert heal(lambda: next(answers), lambda: 1 / 0, sleep=lambda s: None) == "recovered"


def test_restarts_a_dead_server_once():
    state = {"up": False, "restarts": 0}

    def restart():
        state["restarts"] += 1
        state["up"] = True

    assert heal(lambda: state["up"], restart, sleep=lambda s: None) == "restarted"
    assert state["restarts"] == 1


def test_reports_failure_when_restart_does_not_help():
    assert heal(lambda: False, lambda: None, sleep=lambda s: None) == "failed"
