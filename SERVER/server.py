"""웹소켓 중계 서버. 통신과 상태만 담당하고, 계산은 전부 game.py에 맡긴다."""
from typing import Annotated, Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from game import distance_m, interval_ms

MAX_ACCURACY_M = 30  # GPS 오차가 이보다 크면 그 위치는 버린다


# ===== 메시지 모양 (client.html과의 계약) =====
class Join(BaseModel):          # IN: 접속 직후 한 번
    type: Literal["join"]
    role: Literal["hider", "seeker"]


class LocationMsg(BaseModel):   # IN: 1초마다
    type: Literal["location"]
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy: float | None = None
    ts: float


class Beep(BaseModel):          # OUT: 술래한테만
    type: Literal["beep"] = "beep"
    interval_ms: int | None


Message = Annotated[Join | LocationMsg, Field(discriminator="type")]
MessageAdapter = TypeAdapter(Message)


# ===== 게임 상태 (MVP: 숨는 사람 1명, 술래 1명) =====
positions: dict[str, LocationMsg] = {}   # "hider"/"seeker" -> 최신 위치
seeker_ws: WebSocket | None = None        # 삑 보낼 곳

app = FastAPI()


@app.get("/")
async def index():
    return FileResponse("client.html")


async def update_seeker() -> None:
    """현재 두 위치로 삑 간격을 계산해서 술래한테 보낸다."""
    if seeker_ws is None:
        return
    hider = positions.get("hider")
    seeker = positions.get("seeker")
    if hider is None or seeker is None:
        ms = None                         # 한쪽 위치가 없으면 조용
    else:
        d = distance_m(hider.lat, hider.lng, seeker.lat, seeker.lng)
        ms = interval_ms(d)
        print(f"[dist] {d:.1f} m -> {ms} ms")
    await seeker_ws.send_text(Beep(interval_ms=ms).model_dump_json())


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    global seeker_ws
    await websocket.accept()
    role: str | None = None               # 이 연결이 누군지. join 받기 전엔 모름

    try:
        while True:
            raw = await websocket.receive_text()

            # 1. 문자열 -> 검증된 객체. 이상하면 보낸 사람한테만 에러 돌려주고 계속
            try:
                msg = MessageAdapter.validate_json(raw)
            except ValidationError as e:
                await websocket.send_text(e.json())
                continue

            # 2. 종류별 처리
            match msg:
                case Join():
                    role = msg.role
                    if role == "seeker":
                        seeker_ws = websocket
                    print(f"[join] {role}")

                case LocationMsg():
                    if role is None:
                        continue          # join 전에 온 위치는 무시
                    if msg.accuracy is not None and msg.accuracy > MAX_ACCURACY_M:
                        continue          # 너무 부정확한 위치는 버림
                    positions[role] = msg
                    await update_seeker()

    except WebSocketDisconnect:
        # 3. 나간 사람 정리
        print(f"[leave] {role}")
        if role is not None:
            positions.pop(role, None)
        if role == "seeker" and seeker_ws is websocket:
            seeker_ws = None
        if role == "hider":
            await update_seeker()         # 숨는 사람 나가면 술래 삑 멈춤