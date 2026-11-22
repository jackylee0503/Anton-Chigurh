"""게임 규칙 계산. 상태 없음, 네트워크 모름."""
from geopy.distance import distance

MAX_RANGE_M = 300        # 이 거리 밖이면 조용
MIN_INTERVAL_MS = 80     # 붙어 있을 때 (거의 연속음)
MAX_INTERVAL_MS = 1500   # 범위 끝에 있을 때


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 위경도 사이 거리 (미터)."""
    return distance((lat1, lng1), (lat2, lng2)).meters


def interval_ms(d: float) -> int | None:
    """거리(m) -> 삑 간격(ms). 범위 밖이면 None."""
    if d < 0:
        raise ValueError(f"distance must be >= 0, got {d}")
    if d > MAX_RANGE_M:
        return None
    interval = MIN_INTERVAL_MS + (MAX_INTERVAL_MS - MIN_INTERVAL_MS) * (d / MAX_RANGE_M)
    return round(interval)