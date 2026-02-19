"""
DeepSeek Processor - Secondary AI
Exact implementation from reference: uses requests + AES cookie challenge
Wrapped in asyncio for bot compatibility
"""

import re
import json
import time
import asyncio
import requests
import io
import base64
from typing import List, Dict, Optional
from Crypto.Cipher import AES
from prompts import get_extraction_prompt, get_generation_prompt

DEEPSEEK_MODELS = [
    "DeepSeek-V1",
    "DeepSeek-V2",
    "DeepSeek-V2.5",
    "DeepSeek-V3",
    "DeepSeek-V3-0324",
    "DeepSeek-V3.1",
    "DeepSeek-V3.2",
    "DeepSeek-R1",
    "DeepSeek-R1-0528",
    "DeepSeek-R1-Distill",
    "DeepSeek-Prover-V1",
    "DeepSeek-Prover-V1.5",
    "DeepSeek-Prover-V2",
    "DeepSeek-VL",
    "DeepSeek-Coder",
    "DeepSeek-Coder-V2",
    "DeepSeek-Coder-6.7B-base",
    "DeepSeek-Coder-6.7B-instruct",
]

BASE_URL = "https://asmodeus.free.nf"


class DeepSeekSession:
    """
    Exact implementation from reference file.
    Uses requests.Session + AES cookie challenge.
    """

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._initialized = False

    def _init_session(self):
        """
        Mirror of reference code:
            s = requests.Session()
            s.headers.update({'User-Agent': 'Mozilla/5.0 (Android)'})
            r = s.get('https://asmodeus.free.nf/')
            nums = re.findall(r'toNumbers\("([a-f0-9]+)"\)', r.text)
            key, iv, data = [bytes.fromhex(n) for n in nums[:3]]
            s.cookies.set('__test', AES.new(key, AES.MODE_CBC, iv).decrypt(data).hex(), ...)
            s.get('https://asmodeus.free.nf/index.php?i=1')
            time.sleep(0.5)
        """
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0 (Android)"})
        s.verify = False  # free host may have self-signed cert

        # Step 1: Fetch challenge page
        r = s.get(BASE_URL + "/", timeout=30)
        nums = re.findall(r'toNumbers\("([a-f0-9]+)"\)', r.text)
        if len(nums) < 3:
            raise Exception("Could not parse AES challenge — site may be down")

        key, iv, data = [bytes.fromhex(n) for n in nums[:3]]

        # Step 2: Solve AES-CBC challenge and set cookie
        test_value = AES.new(key, AES.MODE_CBC, iv).decrypt(data).hex()
        s.cookies.set("__test", test_value, domain="asmodeus.free.nf")

        # Step 3: Confirm session
        s.get(f"{BASE_URL}/index.php?i=1", timeout=30)
        time.sleep(0.5)

        self._session = s
        self._initialized = True
        print("✅ DeepSeek session initialized")

    def query_sync(self, model: str, prompt: str) -> str:
        """
        Mirror of reference code:
            r = s.post('https://asmodeus.free.nf/deepseek.php',
                       params={'i': '1'},
                       data={'model': model, 'question': msg})
            reply = re.search(r'<div class="response-content">(.*?)</div>', r.text, re.DOTALL)
            response_text = reply.group(1) if reply else '...'
        """
        if not self._initialized:
            self._init_session()

        r = self._session.post(
            f"{BASE_URL}/deepseek.php",
            params={"i": "1"},
            data={"model": model, "question": prompt},
            timeout=120,
        )

        reply = re.search(
            r'<div class="response-content">(.*?)</div>', r.text, re.DOTALL
        )
        if reply:
            return reply.group(1).strip()
        raise Exception(f"No response-content in reply. HTTP {r.status_code}")

    def reset(self):
        """Force re-authentication on next call"""
        if self._session:
            self._session.close()
        self._session = None
        self._initialized = False
        print("🔄 DeepSeek session reset")


class DeepSeekProcessor:
    """
    Secondary AI processor — mirrors PDFProcessor interface.
    Uses synchronous requests wrapped with run_in_executor so
    it doesn't block the asyncio event loop.
    """

    def __init__(self, model: str = "DeepSeek-R1"):
        self.model = model if model in DEEPSEEK_MODELS else "DeepSeek-R1"
        self.session = DeepSeekSession()

    def set_model(self, model: str):
        if model in DEEPSEEK_MODELS:
            self.model = model
        else:
            raise ValueError(f"Unknown DeepSeek model: {model}")

    def _build_prompt(self, image, image_idx: int, mode: str) -> str:
        """
        Build the full prompt combining base instructions + image description.
        Since the free API is text-only, we encode the image as base64 and
        embed it directly in the prompt so DeepSeek can reason about it.
        """
        base_prompt = (
            get_extraction_prompt() if mode == "extraction"
            else get_generation_prompt()
        )

        # Convert PIL image to base64 PNG
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return (
            f"{base_prompt}\n\n"
            f"The following is image #{image_idx} encoded as base64 PNG.\n"
            f"Analyze it and extract/generate MCQ questions.\n"
            f"Image data (base64): {img_b64}\n\n"
            f"Return ONLY the JSON array. No explanation, no markdown, no preamble."
        )

    def _process_one_sync(self, image, image_idx: int, mode: str, retry_count: int = 3):
        """Synchronous processing for one image (called from executor)"""
        prompt = self._build_prompt(image, image_idx, mode)

        for attempt in range(retry_count):
            try:
                raw = self.session.query_sync(self.model, prompt)

                # Clean JSON fences
                text = raw.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]

                questions = json.loads(text.strip())
                print(f"✅ DeepSeek image {image_idx}: {len(questions)} questions")
                return (image_idx, questions)

            except json.JSONDecodeError as e:
                print(f"⚠️ JSON error image {image_idx} attempt {attempt + 1}: {e}")
                if attempt == retry_count - 1:
                    return (image_idx, None)
                if attempt == 1:
                    self.session.reset()
                time.sleep(2)

            except Exception as e:
                print(f"⚠️ DeepSeek error image {image_idx} attempt {attempt + 1}: {e}")
                if attempt == retry_count - 1:
                    return (image_idx, None)
                self.session.reset()
                time.sleep(3)

        return (image_idx, None)

    async def process_single_image(
        self, image, image_idx: int, mode: str, retry_count: int = 3
    ) -> Optional[tuple]:
        """Async wrapper — runs sync requests in thread executor"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._process_one_sync,
            image,
            image_idx,
            mode,
            retry_count,
        )

    async def process_images_parallel(
        self,
        images: List,
        mode: str,
        progress_callback=None,
    ) -> List[Dict]:
        """
        Process images sequentially (DeepSeek free API is rate-limited).
        Matches the PDFProcessor interface expected by ContentProcessor.
        """
        all_questions = []
        total = len(images)

        print(f"🔵 DeepSeek processing {total} images | model: {self.model}")

        for idx, image in enumerate(images, 1):
            result = await self.process_single_image(image, idx, mode)

            if progress_callback:
                await progress_callback(idx, total)

            if result and result[1]:
                all_questions.extend(result[1])

            # Rate limiting — be gentle with free API
            if idx < total:
                await asyncio.sleep(2)

        return all_questions
