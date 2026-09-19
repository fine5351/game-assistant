import time
from typing import Optional, Tuple, List, Dict
import mss
from PIL import Image
from config import MAX_IMAGE_SIZE


class ScreenCapturer:
    """
    超低延遲畫面擷取服務
    使用 mss 與 Pillow 進行螢幕快照擷取與預處理縮放
    """

    def __init__(self):
        pass

    @staticmethod
    def get_monitors() -> List[Dict[str, int]]:
        """
        取得系統所有顯示器資訊
        """
        mss_cls = getattr(mss, "MSS", mss.mss)
        with mss_cls() as sct:
            return sct.monitors

    @staticmethod
    def capture(
        monitor_index: int = 1,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        max_size: Optional[Tuple[int, int]] = MAX_IMAGE_SIZE
    ) -> Tuple[Image.Image, float]:
        """
        擷取畫面並返回 PIL Image 物件與耗時 (毫秒)
        :param monitor_index: 顯示器編號 (預設 1 為主顯示器，0 為全屏幕總合)
        :param bbox: 可選自訂擷取區域 (left, top, width, height)
        :param max_size: 最大限制尺寸 (width, height)
        :return: (PIL Image 物件 (RGB), 擷取耗時 ms)
        """
        start_time = time.perf_counter()

        try:
            mss_cls = getattr(mss, "MSS", mss.mss)
            with mss_cls() as sct:
                if bbox:
                    left, top, width, height = bbox
                    region = {"left": left, "top": top, "width": width, "height": height}
                else:
                    monitors = sct.monitors
                    if monitor_index < 0 or monitor_index >= len(monitors):
                        monitor_index = 1
                    region = monitors[monitor_index]

                sct_img = sct.grab(region)
                # mss 回傳 BGRA, 轉為 PIL Image (RGB)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                if max_size:
                    target_w, target_h = max_size
                    orig_w, orig_h = img.size
                    if orig_w > target_w or orig_h > target_h:
                        img.thumbnail((target_w, target_h), Image.Resampling.BILINEAR)

                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return img, elapsed_ms
        except Exception as e:
            # 在無螢幕授權、螢幕鎖定或伺服器遠端會話下，提供安全降級畫面，防止迴圈崩潰
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            fallback_w, fallback_h = max_size if max_size else (1280, 720)
            fallback_img = Image.new("RGB", (fallback_w, fallback_h), color=(15, 18, 25))
            return fallback_img, elapsed_ms


if __name__ == "__main__":
    # 單元測試擷取功能與效能
    capturer = ScreenCapturer()
    print("Monitors:", capturer.get_monitors())
    img, cost_ms = capturer.capture(monitor_index=1)
    print(f"Captured screen size: {img.size}, Time cost: {cost_ms:.2f} ms")
