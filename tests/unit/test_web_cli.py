from click.testing import CliRunner

from loopflow.presentation.cli import main


def test_web_remote_bind_requires_explicit_opt_in(monkeypatch):
    called = []
    monkeypatch.setattr("loopflow.presentation.web.server.create_server", lambda *args, **kwargs: called.append(args))

    result = CliRunner().invoke(main, ["web", "--host", "0.0.0.0"])

    assert result.exit_code != 0
    assert "--allow-remote" in result.output
    assert called == []


def test_web_remote_opt_in_warns_and_serves(monkeypatch):
    class Server:
        server_address = ("0.0.0.0", 9000)
        served = False
        closed = False

        def serve_forever(self):
            self.served = True

        def server_close(self):
            self.closed = True

    server = Server()
    monkeypatch.setattr("loopflow.presentation.web.server.create_server", lambda *args, **kwargs: server)

    result = CliRunner().invoke(main, ["web", "--host", "0.0.0.0", "--port", "9000", "--allow-remote"])

    assert result.exit_code == 0
    assert "Warning" in result.output and "http://0.0.0.0:9000" in result.output
    assert server.served and server.closed
