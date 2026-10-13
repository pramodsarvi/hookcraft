import asyncio
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import aiofiles
except ImportError:
    aiofiles = None  # type: ignore


try:
    import cv2
    import numpy as np
    from PIL import Image
except ImportError:
    cv2 = Any  # type: ignore
    np = Any  # type: ignore
    Image = Any  # type: ignore

try:
    from playwright.async_api import Page, Response
except ImportError:
    Page = Any  # type: ignore
    Response = Any  # type: ignore


logger = logging.getLogger("StreamInterceptor")


class StreamInterceptor:
    """
    Captures live media streams from X, Instagram Reels, and short-form video.
    Primary strategy: Intercepts raw video bytes (.mp4 / .m3u8 fragments) via Playwright Network listeners.
    Secondary fallback: High-framerate Canvas/Viewport frame buffer capture using OpenCV.
    """

    def __init__(self, media_storage_dir: Optional[Path] = None):
        self.storage_dir = media_storage_dir or Path("./data/captured_media")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.intercepted_video_urls: Set[str] = set()
        self.captured_files: Dict[str, Path] = {}
        self._listener_active = False

    def attach_network_interceptor(self, page: Page, post_id: str) -> None:
        """Attaches dynamic XHR/Fetch response listeners to capture video stream payloads."""
        self._listener_active = True

        async def _response_handler(response: Response):
            if not self._listener_active:
                return

            url = response.url.lower()
            content_type = response.headers.get("content-type", "").lower()

            is_video = (
                "video/mp4" in content_type
                or "video/webm" in content_type
                or "application/x-mpegurl" in content_type
                or url.endswith(".mp4")
                or ".mp4?" in url
            )

            # Avoid tiny preview avatars or thumbnail sprites
            if is_video and url not in self.intercepted_video_urls:
                self.intercepted_video_urls.add(url)
                logger.info("Detected dynamic media stream for post [%s]: %s", post_id, url[:80])

                try:
                    body = await response.body()
                    if len(body) > 100_000:  # Minimum 100KB for real video content
                        out_file = self.storage_dir / f"{post_id}_stream.mp4"
                        if aiofiles:
                            async with aiofiles.open(out_file, "wb") as f:
                                await f.write(body)
                        else:
                            with open(out_file, "wb") as f:
                                f.write(body)
                        self.captured_files[post_id] = out_file
                        logger.info("Successfully intercepted video stream saved to: %s", out_file)

                except Exception as e:
                    logger.debug("Failed buffering video stream bytes: %s", e)

        page.on("response", _response_handler)

    def detach_network_interceptor(self) -> None:
        """Disables active response listener."""
        self._listener_active = False

    async def capture_canvas_stream_fallback(
        self,
        page: Page,
        element_selector: str,
        post_id: str,
        duration_sec: float = 4.0,
        target_fps: int = 20,
    ) -> Optional[Path]:
        """
        Fallback mechanism: If network stream is encrypted or blocked via DRM,
        continuously captures DOM element/canvas screenshots and encodes them
        into an MP4 video container via OpenCV VideoWriter.
        """
        logger.warning(
            "Invoking OpenCV Canvas/Viewport stream capture fallback for post [%s] (%s sec @ %d fps)...",
            post_id,
            duration_sec,
            target_fps,
        )

        locator = page.locator(element_selector).first
        if await locator.count() == 0:
            logger.error("Target video locator '%s' not found for fallback capture.", element_selector)
            return None

        frames: List[np.ndarray] = []
        frame_interval = 1.0 / target_fps
        start_time = asyncio.get_event_loop().time()
        box = await locator.bounding_box()

        if not box or box["width"] <= 0 or box["height"] <= 0:
            return None

        # Capture rapid frame buffer
        while (asyncio.get_event_loop().time() - start_time) < duration_sec:
            cycle_start = asyncio.get_event_loop().time()
            try:
                screenshot_bytes = await locator.screenshot(type="jpeg", quality=85)
                # Decode JPEG byte stream into OpenCV BGR numpy array
                img_array = cv2.imdecode(np.frombuffer(screenshot_bytes, np.uint8), cv2.IMREAD_COLOR)
                if img_array is not None:
                    frames.append(img_array)
            except Exception as e:
                logger.debug("Frame buffer read error: %s", e)

            elapsed = asyncio.get_event_loop().time() - cycle_start
            sleep_time = max(0.0, frame_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        if not frames:
            logger.error("Canvas fallback captured 0 frames for [%s].", post_id)
            return None

        # Encode captured frames into MP4 video file
        height, width, _ = frames[0].shape
        # Ensure dimensions are even numbers for H.264 / MP4V encoders
        width = width if width % 2 == 0 else width - 1
        height = height if height % 2 == 0 else height - 1

        out_path = self.storage_dir / f"{post_id}_canvas_fallback.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(str(out_path), fourcc, target_fps, (width, height))

        for frame in frames:
            resized_frame = cv2.resize(frame, (width, height))
            video_writer.write(resized_frame)

        video_writer.release()
        logger.info("OpenCV Canvas fallback compiled %d frames to: %s", len(frames), out_path)
        self.captured_files[post_id] = out_path
        return out_path
