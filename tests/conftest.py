import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-key",
            "DATABASE_PATH": str(tmp_path / "data" / "test.sqlite3"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "SEED_TEACHER_PASSWORD": "teacher-test-password",
            "SEED_STUDENT_A_PASSWORD": "student-a-test-password",
            "SEED_STUDENT_B_PASSWORD": "student-b-test-password",
            "MAX_UPLOAD_BYTES": 1024,
            "MAX_CONTENT_LENGTH": 1024 + 16384,
        }
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username="teacher_a", password="teacher-test-password"):
    return client.post("/api/login", json={"username": username, "password": password})
