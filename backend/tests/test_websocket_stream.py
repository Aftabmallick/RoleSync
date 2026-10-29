import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.tasks.tailor_tasks import task_store, _emit_task_progress


class TestWebSocketStream(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_websocket_task_stream_lifecycle(self):
        task_id = "test_ws_task_001"
        task_store[task_id] = {"status": "PROCESSING", "stage": "PARSING_JD"}

        # Connect WebSocket to /ws/v1/tasks/{task_id}
        with self.client.websocket_connect(f"/ws/v1/tasks/{task_id}") as websocket:
            # 1. First frame receives current task state
            data = websocket.receive_json()
            self.assertEqual(data["task_id"], task_id)
            self.assertEqual(data["status"], "PROCESSING")
            self.assertEqual(data["stage"], "PARSING_JD")

            # 2. Ping-Pong test
            websocket.send_text("PING")
            pong = websocket.receive_text()
            self.assertEqual(pong, "PONG")

    def test_websocket_stream_new_task(self):
        task_id = "test_ws_fresh_task"
        with self.client.websocket_connect(f"/ws/v1/tasks/{task_id}") as websocket:
            websocket.send_text("PING")
            pong = websocket.receive_text()
            self.assertEqual(pong, "PONG")


if __name__ == "__main__":
    unittest.main()

