from server.policy import validate_command


def test_unknown_command_is_rejected():
    assert validate_command("SHELL", {}, "admin") == "command is not allow-listed"


def test_operator_cannot_kill_process():
    assert validate_command("KILL_PROCESS", {"pid": 123}, "operator") == "insufficient role"


def test_admin_can_request_process_list():
    assert validate_command("LIST_PROCESSES", {}, "admin") is None