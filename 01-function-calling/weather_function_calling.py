"""Minh hoạ FUNCTION CALLING thuần với Google Gemini SDK.

Tool `get_weather` được định nghĩa schema thủ công VÀ thực thi ngay trong
chính file app này. Model chỉ QUYẾT ĐỊNH gọi tool nào; app mới là nơi chạy.

Được cấu hình Round-Robin luân phiên giữa 2 model:
- gemini-3.1-flash-lite
- gemini-3.5-flash-lite

Cách chạy:
    pip install -r ../requirements.txt
    python weather_function_calling.py
"""

from __future__ import annotations

import itertools
import json
import os
import sys

# Đảm bảo in tiếng Việt & emoji chuẩn trên mọi OS (đặc biệt là Windows)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from google import genai
from google.genai import types

# Cấu hình API Key từ biến môi trường
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=API_KEY) if API_KEY else genai.Client()

# Danh sách 2 model chạy Round-Robin
MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
_model_cycle = itertools.cycle(MODELS)

SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý thời tiết thân thiện, trả lời bằng tiếng Việt tự nhiên. "
    "Dùng emoji phù hợp (🌧️ 🌤️ 💨 💧). "
    "Tóm tắt ngắn gọn, dễ hiểu, và đưa ra lời khuyên thực tế "
    "(ví dụ: mang ô, mặc áo mỏng, ...)."
)

# 1. App tự định nghĩa schema của tool
get_weather_declaration = types.FunctionDeclaration(
    name="get_weather",
    description="Lấy thời tiết hiện tại của một thành phố",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(
                type=types.Type.STRING, description="Tên thành phố"
            )
        },
        required=["city"],
    ),
)

TOOLS = [types.Tool(function_declarations=[get_weather_declaration])]


# 2. App tự thực thi tool (trong thực tế sẽ gọi API thời tiết thật)
def get_weather(city: str) -> str:
    """Trả về thời tiết (mock) của *city*. Dùng làm tool cho model."""
    mock_data = {
        "Hà Nội": {
            "nhiệt_độ": "29°C",
            "thời_tiết": "trời mưa nhẹ",
            "độ_ẩm": "82%",
            "gió": {"hướng": "Đông Nam", "tốc_độ": "12 km/h"},
        },
        "Hồ Chí Minh": {
            "nhiệt_độ": "33°C",
            "thời_tiết": "mưa rào",
            "độ_ẩm": "75%",
            "gió": {"hướng": "Tây Nam", "tốc_độ": "15 km/h"},
        },
        "Đà Nẵng": {
            "nhiệt_độ": "30°C",
            "thời_tiết": "nhiều mây",
            "độ_ẩm": "78%",
            "gió": {"hướng": "Đông", "tốc_độ": "10 km/h"},
        },
    }

    # Chuẩn hóa tìm kiếm theo tên không dấu / gần đúng nếu cần
    city_lookup = city.strip()
    if city_lookup.lower() in ["hanoi", "ha noi"]:
        city_lookup = "Hà Nội"
    elif city_lookup.lower() in ["danang", "da nang"]:
        city_lookup = "Đà Nẵng"
    elif city_lookup.lower() in ["hcm", "ho chi minh", "saigon"]:
        city_lookup = "Hồ Chí Minh"

    default = {"nhiệt_độ": "28°C", "thời_tiết": "nắng nhẹ, thời tiết dễ chịu"}
    return json.dumps({"city": city, **mock_data.get(city_lookup, default)}, ensure_ascii=False)


def run(prompt: str, model: str | None = None) -> str:
    """Gửi *prompt* tới Gemini, tự động xử lý function calling và trả về câu trả lời cuối."""
    # Chọn model theo cơ chế round-robin nếu không chỉ định rõ
    chosen_model = model or next(_model_cycle)
    print(f"🤖 [Model đang xử lý]: {chosen_model}")

    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
    ]

    # 3. Gọi model — model quyết định có gọi tool hay không
    resp = client.models.generate_content(
        model=chosen_model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=TOOLS,
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )

    # 4. Vòng lặp: nếu model yêu cầu tool, app TỰ THỰC THI rồi đưa kết quả trả lại
    while resp.function_calls:
        # Thêm phản hồi của model vào lịch sử hội thoại
        contents.append(resp.candidates[0].content)

        function_responses = []
        for fc in resp.function_calls:
            print(f"  [model yêu cầu] {fc.name}({fc.args})")
            result = get_weather(**fc.args)  # <-- app chạy, không phải model
            print(f"  [app thực thi]  -> {result}")
            function_responses.append(
                types.Part.from_function_response(
                    name=fc.name, response={"result": result}
                )
            )

        # Gửi kết quả tool trả về cho model
        contents.append(types.Content(role="user", parts=function_responses))
        resp = client.models.generate_content(
            model=chosen_model,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=TOOLS,
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )

    # 5. Model tổng hợp câu trả lời cuối
    return resp.text


if __name__ == "__main__":
    print("=== DEMO FUNCTION CALLING VỚI ROUND-ROBIN 2 MODELS ===")
    print(f"Danh sách models: {MODELS}\n")

    questions = [
        "Thời tiết Hà Nội hôm nay thế nào?",
        "Thời tiết Đà Nẵng và Hồ Chí Minh hôm nay có mưa không?",
    ]

    for i, q in enumerate(questions, 1):
        print(f"--- Lượt {i} ---")
        print(f"User: {q}")
        answer = run(q)
        print(f"Trả lời:\n{answer}\n")
