"""FastAPI 上传、生成和导出联调测试。"""

from __future__ import annotations

import io
import tempfile
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import create_app


def png_payload() -> bytes:
    image = Image.new("RGB", (32, 20), (240, 80, 70))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.client_context = TestClient(create_app(self.temporary.name))
        self.client = self.client_context.__enter__()
        registered = self.client.post(
            "/api/auth/register",
            json={"username": "test_user", "password": "secure-pass-123"},
        )
        self.assertEqual(registered.status_code, 201, registered.text)
        self.headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary.cleanup()

    def test_health_palettes_and_specifications(self) -> None:
        self.assertEqual(self.client.get("/api/health").json()["status"], "ok")
        palettes = self.client.get("/api/palettes").json()
        specifications = self.client.get("/api/specifications").json()

        self.assertEqual([item["color_count"] for item in palettes], [221, 291])
        self.assertEqual([item["bead_count"] for item in specifications], [2704, 6400, 10816])

    def test_upload_generate_and_download_all_artifacts(self) -> None:
        upload = self.client.post(
            "/api/upload",
            headers=self.headers,
            files={"file": ("sample.png", png_payload(), "image/png")},
        )
        self.assertEqual(upload.status_code, 201, upload.text)
        upload_data = upload.json()

        generated = self.client.post(
            "/api/generate",
            headers=self.headers,
            json={
                "image_id": upload_data["image_id"],
                "size": "52x52",
                "palette": "mard_221",
                "color_mode": "rgb",
                "dithering": False,
                "pattern_type": "number",
                "resize_mode": "fit_pad",
                "content_scale": 0.75,
            },
        )
        self.assertEqual(generated.status_code, 200, generated.text)
        data = generated.json()
        self.assertEqual(data["specification"]["bead_count"], 2704)
        self.assertEqual(data["active_bead_count"], 39 * 39)
        self.assertEqual(sum(item["count"] for item in data["statistics"]), 39 * 39)
        self.assertTrue(self.client.get(data["number_preview_url"]).content.startswith(b"\x89PNG"))

        for key, prefix in (("png_url", b"\x89PNG"), ("pdf_url", b"%PDF"), ("csv_url", b"\xef\xbb\xbf")):
            with self.subTest(key=key):
                response = self.client.get(data[key], headers=self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content.startswith(prefix))

    def test_invalid_upload_and_unknown_image_are_rejected(self) -> None:
        invalid = self.client.post(
            "/api/upload",
            headers=self.headers,
            files={"file": ("bad.png", b"not an image", "image/png")},
        )
        self.assertEqual(invalid.status_code, 400)

        missing = self.client.post(
            "/api/generate",
            headers=self.headers,
            json={"image_id": "00000000-0000-0000-0000-000000000000"},
        )
        self.assertEqual(missing.status_code, 404)

    def test_authentication_history_publish_and_public_download(self) -> None:
        self.assertEqual(self.client.get("/api/auth/me", headers=self.headers).json()["username"], "test_user")
        duplicate = self.client.post(
            "/api/auth/register",
            json={"username": "TEST_USER", "password": "another-pass-123"},
        )
        self.assertEqual(duplicate.status_code, 409)
        wrong_login = self.client.post(
            "/api/auth/login",
            json={"username": "test_user", "password": "wrong-pass-123"},
        )
        self.assertEqual(wrong_login.status_code, 401)
        self.assertEqual(
            self.client.post("/api/upload", files={"file": ("sample.png", png_payload(), "image/png")}).status_code,
            401,
        )

        upload = self.client.post(
            "/api/upload",
            headers=self.headers,
            files={"file": ("sample.png", png_payload(), "image/png")},
        ).json()
        generated_response = self.client.post(
            "/api/generate",
            headers=self.headers,
            json={"image_id": upload["image_id"], "pattern_type": "number"},
        )
        self.assertEqual(generated_response.status_code, 200, generated_response.text)
        generated = generated_response.json()
        history = self.client.get("/api/me/artworks", headers=self.headers).json()
        self.assertEqual(history, [])
        self.assertEqual(self.client.get("/api/community").json(), [])

        publish_before_save = self.client.post(
            f"/api/artworks/{generated['job_id']}/publish",
            headers=self.headers,
            json={"title": "不应发布", "description": ""},
        )
        self.assertEqual(publish_before_save.status_code, 404)
        saved = self.client.post(
            f"/api/artworks/{generated['job_id']}/save",
            headers=self.headers,
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertTrue(saved.json()["is_saved"])
        history = self.client.get("/api/me/artworks", headers=self.headers).json()
        self.assertEqual(len(history), 1)
        self.assertFalse(history[0]["is_public"])

        published = self.client.post(
            f"/api/artworks/{generated['job_id']}/publish",
            headers=self.headers,
            json={"title": "测试作品", "description": "社区接口联调"},
        )
        self.assertEqual(published.status_code, 200, published.text)
        public_artworks = self.client.get("/api/community").json()
        self.assertEqual(public_artworks[0]["title"], "测试作品")
        public_preview = self.client.get(public_artworks[0]["number_preview_url"])
        self.assertEqual(public_preview.status_code, 200)
        self.assertTrue(public_preview.content.startswith(b"\x89PNG"))
        public_pdf = self.client.get(public_artworks[0]["pdf_url"])
        self.assertEqual(public_pdf.status_code, 200)
        self.assertTrue(public_pdf.content.startswith(b"%PDF"))

        unpublished = self.client.post(
            f"/api/artworks/{generated['job_id']}/unpublish",
            headers=self.headers,
        )
        self.assertEqual(unpublished.status_code, 200)
        self.assertEqual(self.client.get("/api/community").json(), [])
        self.assertEqual(self.client.get(public_artworks[0]["number_preview_url"]).status_code, 404)

        deleted = self.client.delete(
            f"/api/artworks/{generated['job_id']}",
            headers=self.headers,
        )
        self.assertEqual(deleted.status_code, 204, deleted.text)
        self.assertEqual(self.client.get("/api/me/artworks", headers=self.headers).json(), [])
        self.assertEqual(self.client.get(generated["pdf_url"], headers=self.headers).status_code, 404)

    def test_private_chat_user_search_and_messages(self) -> None:
        second = self.client.post(
            "/api/auth/register",
            json={"username": "second_user", "password": "secure-pass-456"},
        )
        self.assertEqual(second.status_code, 201, second.text)
        second_data = second.json()
        second_headers = {"Authorization": f"Bearer {second_data['access_token']}"}

        users = self.client.get("/api/chat/users?query=second", headers=self.headers).json()
        self.assertEqual([(item["id"], item["username"]) for item in users], [(second_data["user"]["id"], "second_user")])
        sent = self.client.post(
            f"/api/chat/{second_data['user']['id']}/messages",
            headers=self.headers,
            json={"body": "你好，一起交流拼豆图纸吧"},
        )
        self.assertEqual(sent.status_code, 201, sent.text)

        conversations = self.client.get("/api/chat/conversations", headers=second_headers).json()
        self.assertEqual(conversations[0]["username"], "test_user")
        self.assertEqual(conversations[0]["unread_count"], 1)
        messages = self.client.get(
            f"/api/chat/{self.client.get('/api/auth/me', headers=self.headers).json()['id']}/messages",
            headers=second_headers,
        ).json()
        self.assertEqual(messages[0]["body"], "你好，一起交流拼豆图纸吧")
        conversations = self.client.get("/api/chat/conversations", headers=second_headers).json()
        self.assertEqual(conversations[0]["unread_count"], 0)


if __name__ == "__main__":
    unittest.main()
