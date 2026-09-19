import speech_recognition as sr
from config import STT_LANGUAGE, STT_TIMEOUT, STT_PHRASE_TIME_LIMIT


class STTEngine:
    """
    SpeechRecognition 麥克風擷取與語音轉文字 (STT) 引擎
    支援繁體中文 (zh-TW) 辨識與硬體/網路異常捕獲
    """

    def __init__(
        self,
        language: str = STT_LANGUAGE,
        timeout: int = STT_TIMEOUT,
        phrase_time_limit: int = STT_PHRASE_TIME_LIMIT
    ):
        self.language = language
        self.timeout = timeout
        self.phrase_time_limit = phrase_time_limit
        self.recognizer = sr.Recognizer()

    def listen_and_recognize(self) -> tuple[bool, str]:
        """
        開啟麥克風擷取語音並進行辨識
        :return: (is_success, recognized_text_or_error_message)
        """
        try:
            with sr.Microphone() as source:
                # 自動校正背景噪音門檻
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                # 擷取音訊
                audio = self.recognizer.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=self.phrase_time_limit
                )

            # 使用 Google Speech Recognition 進行中文語音轉文字
            recognized_text = self.recognizer.recognize_google(
                audio,
                language=self.language
            )

            if recognized_text and recognized_text.strip():
                return True, recognized_text.strip()
            else:
                return False, "⚠️ 未辨識到有效的語音內容。"

        except sr.WaitTimeoutError:
            return False, "⏳ 聆聽逾時：未在規定時間內發聲。"
        except sr.UnknownValueError:
            return False, "🤔 無法辨識語音內容，請試著說得更清楚一些。"
        except sr.RequestError as e:
            return False, f"🌐 語音辨識服務請求失敗 ({str(e)})，請檢查網路連線。"
        except OSError as e:
            return False, f"🎙️ 麥克風硬體錯誤：未檢測到可用麥克風設備或裝置已被佔用 ({str(e)})。"
        except Exception as e:
            return False, f"❌ 語音辨識發生異常：{str(e)}"


if __name__ == "__main__":
    stt = STTEngine()
    print("STT 引擎初始化，準備測試（如無麥克風將提示硬體錯誤）...")
    success, text = stt.listen_and_recognize()
    print(f"結果: success={success}, content='{text}'")
